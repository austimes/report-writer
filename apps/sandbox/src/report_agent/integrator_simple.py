"""Simplified report integration pass.

This module provides a streamlined ReportIntegrator that:
- Takes only the assembled report.md content
- Returns the full integrated markdown (no complex state tracking)
- Stores versions in _integration/ for diffing
- Uses INTEGRATION_HINTS comments instead of report_state.json
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .prompts import load_prompt

ProgressCallback = Callable[[str], None]

DEFAULT_MODEL = "gpt-5.1-2025-11-13"
DEFAULT_THINKING_LEVEL = "medium"

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.1-2025-11-13": {"input": 2.50, "output": 10.00},
    "gpt-5.1-mini-2025-06-30": {"input": 0.40, "output": 1.60},
    "gpt-5-nano-2025-08-07": {"input": 0.10, "output": 0.40},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}

SECTION_BEGIN_RE = re.compile(
    r'<!--\s*BEGIN SECTION:\s*(?P<id>[a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

SECTION_BLOCK_PATTERN = (
    r'<!--\s*BEGIN SECTION:\s*{id}\b.*?-->'
    r'(?P<body>.*?)'
    r'<!--\s*END SECTION:\s*{id}\s*-->'
)


@dataclass
class UsageCost:
    """Token usage and cost for an LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class IntegrationResult:
    """Result of running the integration pass."""
    integrated_content: str
    sections_modified: list[str] = field(default_factory=list)
    duplicates_removed: int = 0
    cross_refs_added: int = 0
    usage: UsageCost = field(default_factory=UsageCost)
    validation_passed: bool = True
    validation_message: str = ""
    run_id: int = 0
    before_path: Path | None = None
    after_path: Path | None = None


class SimpleReportIntegrator:
    """Simplified report integrator - markdown in, markdown out.
    
    This integrator:
    - Reads the full report.md content
    - Sends it to an LLM for integration (dedup, cross-refs, numbering)
    - Returns the integrated markdown
    - Optionally stores before/after snapshots in _integration/
    """
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        thinking_level: str = DEFAULT_THINKING_LEVEL,
        dry_run: bool = False,
        on_progress: ProgressCallback | None = None,
        llm_log_dir: Path | None = None,
    ):
        self.model = model
        self.thinking_level = thinking_level
        self.dry_run = dry_run
        self._on_progress = on_progress
        self._llm_log_dir = llm_log_dir
    
    def _emit(self, message: str) -> None:
        """Emit a progress message if callback is set."""
        if self._on_progress:
            self._on_progress(message)
    
    def integrate(
        self,
        report_content: str,
        output_dir: Path | None = None,
        max_change_ratio: float = 0.3,
    ) -> IntegrationResult:
        """Run integration pass on assembled report.
        
        Args:
            report_content: The full report markdown content
            output_dir: Directory to store _integration/ snapshots (optional)
            max_change_ratio: Maximum allowed change ratio (0.0-1.0)
            
        Returns:
            IntegrationResult with integrated content and stats
        """
        run_id = 0
        before_path = None
        after_path = None
        
        # Setup versioning if output_dir provided
        if output_dir:
            integration_dir = output_dir / "_integration"
            integration_dir.mkdir(parents=True, exist_ok=True)
            run_id = self._get_next_run_id(integration_dir)
            before_path = integration_dir / f"run{run_id:03d}_before.md"
            
            self._emit(f"Saving pre-integration snapshot: {before_path.name}")
            before_path.write_text(report_content)
        
        # Analyze input
        section_ids = self._extract_section_ids(report_content)
        word_count = len(report_content.split())
        figure_count = len(re.findall(r'!\[.*?\]\(.*?\)', report_content))
        
        self._emit(f"Report analysis: {len(section_ids)} sections, ~{word_count} words, {figure_count} figures")
        
        if self.dry_run:
            self._emit("[DRY RUN] Would call LLM for integration")
            self._emit(f"[DRY RUN] Model: {self.model}, thinking: {self.thinking_level}")
            return IntegrationResult(
                integrated_content=report_content,
                sections_modified=[],
                duplicates_removed=0,
                cross_refs_added=0,
                usage=UsageCost(),
                validation_passed=True,
                validation_message="Dry run - no changes made",
                run_id=run_id,
                before_path=before_path,
            )
        
        # Build and send prompt
        self._emit("Building integration prompt...")
        prompt = self._build_prompt(report_content)
        prompt_tokens = len(prompt.split()) * 1.3  # rough estimate
        self._emit(f"Prompt size: ~{int(prompt_tokens)} tokens (estimated)")
        
        self._emit(f"Calling {self.model} for integration pass...")
        self._emit(f"  Thinking level: {self.thinking_level}")
        response_text, usage = self._call_llm(prompt)
        
        self._emit(f"LLM response received:")
        self._emit(f"  Input tokens: {usage.input_tokens:,}")
        self._emit(f"  Output tokens: {usage.output_tokens:,}")
        if usage.reasoning_tokens:
            self._emit(f"  Reasoning tokens: {usage.reasoning_tokens:,}")
        self._emit(f"  Cost: ${usage.cost_usd:.4f}")
        
        # Extract markdown from response
        self._emit("Extracting integrated markdown from response...")
        integrated_content = self._extract_markdown(response_text)
        
        # Validate section markers preserved
        self._emit("Validating section markers preserved...")
        markers_valid, marker_msg = self._validate_section_markers(
            report_content, integrated_content
        )
        if not markers_valid:
            self._emit(f"⚠ Section marker validation failed: {marker_msg}")
        
        # Validate change ratio
        self._emit("Validating change ratio...")
        is_valid, validation_msg = self._validate_changes(
            report_content, integrated_content, max_change_ratio
        )
        self._emit(f"  {validation_msg}")
        
        # Combine validations
        all_valid = is_valid and markers_valid
        combined_msg = validation_msg
        if not markers_valid:
            combined_msg = f"{marker_msg}; {validation_msg}"
        
        # Detect what changed
        self._emit("Analyzing changes...")
        sections_modified = self._detect_modified_sections(
            report_content, integrated_content
        )
        self._emit(f"  Sections modified: {len(sections_modified)}")
        
        duplicates_removed = self._count_figure_removals(
            report_content, integrated_content
        )
        self._emit(f"  Duplicate figures removed: {duplicates_removed}")
        
        cross_refs_added = self._count_cross_refs_added(
            report_content, integrated_content
        )
        self._emit(f"  Cross-references added: {cross_refs_added}")
        
        # Save after snapshot
        if output_dir and all_valid:
            after_path = integration_dir / f"run{run_id:03d}_after.md"
            self._emit(f"Saving post-integration snapshot: {after_path.name}")
            after_path.write_text(integrated_content)
        
        return IntegrationResult(
            integrated_content=integrated_content,
            sections_modified=sections_modified,
            duplicates_removed=max(0, duplicates_removed),
            cross_refs_added=max(0, cross_refs_added),
            usage=usage,
            validation_passed=all_valid,
            validation_message=combined_msg,
            run_id=run_id,
            before_path=before_path,
            after_path=after_path,
        )
    
    def _get_next_run_id(self, integration_dir: Path) -> int:
        """Get the next run ID by scanning existing snapshots."""
        existing = list(integration_dir.glob("run*_before.md"))
        if not existing:
            return 1
        
        run_ids = []
        for p in existing:
            match = re.match(r'run(\d+)_before\.md', p.name)
            if match:
                run_ids.append(int(match.group(1)))
        
        return max(run_ids, default=0) + 1
    
    def _extract_section_ids(self, content: str) -> list[str]:
        """Extract all section IDs from BEGIN SECTION markers."""
        return [m.group("id") for m in SECTION_BEGIN_RE.finditer(content)]
    
    def _build_prompt(self, report_content: str) -> str:
        """Build the integration prompt."""
        template = load_prompt("report_integration_simple")
        return template.format(full_report_content=report_content)
    
    def _extract_markdown(self, response_text: str) -> str:
        """Extract markdown from LLM response, stripping optional fences."""
        # Try to find fenced markdown block
        fence_match = re.search(
            r'```(?:markdown)?\s*(.*?)```',
            response_text,
            re.DOTALL
        )
        if fence_match:
            return fence_match.group(1).strip()
        return response_text.strip()
    
    def _validate_section_markers(
        self,
        original: str,
        integrated: str,
    ) -> tuple[bool, str]:
        """Validate that section markers are preserved."""
        original_ids = set(self._extract_section_ids(original))
        integrated_ids = set(self._extract_section_ids(integrated))
        
        missing = original_ids - integrated_ids
        added = integrated_ids - original_ids
        
        if missing or added:
            problems = []
            if missing:
                problems.append(f"missing sections: {missing}")
            if added:
                problems.append(f"unexpected sections: {added}")
            return (False, "; ".join(problems))
        
        return (True, "All section markers preserved")
    
    def _validate_changes(
        self,
        original: str,
        integrated: str,
        max_change_ratio: float,
    ) -> tuple[bool, str]:
        """Check if changes are within acceptable bounds."""
        original_words = original.split()
        integrated_words = integrated.split()
        
        matcher = difflib.SequenceMatcher(None, original_words, integrated_words)
        ratio = matcher.ratio()
        change_ratio = 1.0 - ratio
        
        if change_ratio > max_change_ratio:
            return (
                False,
                f"Changes exceed threshold: {change_ratio:.1%} changed (max: {max_change_ratio:.1%})"
            )
        
        return (True, f"Changes within bounds: {change_ratio:.1%} changed")
    
    def _detect_modified_sections(
        self,
        original: str,
        integrated: str,
    ) -> list[str]:
        """Detect which sections were modified."""
        original_sections = {}
        for m in SECTION_BEGIN_RE.finditer(original):
            sid = m.group("id")
            pattern = SECTION_BLOCK_PATTERN.format(id=re.escape(sid))
            block = re.search(pattern, original, re.DOTALL)
            if block:
                original_sections[sid] = block.group("body").strip()
        
        modified = []
        for sid, orig_body in original_sections.items():
            pattern = SECTION_BLOCK_PATTERN.format(id=re.escape(sid))
            block = re.search(pattern, integrated, re.DOTALL)
            new_body = block.group("body").strip() if block else ""
            if new_body != orig_body:
                modified.append(sid)
        
        return modified
    
    def _count_figure_removals(self, original: str, integrated: str) -> int:
        """Count how many figure references were removed."""
        pattern = r'!\[.*?\]\(.*?\)'
        original_count = len(re.findall(pattern, original))
        integrated_count = len(re.findall(pattern, integrated))
        return original_count - integrated_count
    
    def _count_cross_refs_added(self, original: str, integrated: str) -> int:
        """Estimate cross-references added."""
        pattern = r'(?:see\s+)?(?:Figure|Table)\s+\d+'
        original_count = len(re.findall(pattern, original, re.IGNORECASE))
        integrated_count = len(re.findall(pattern, integrated, re.IGNORECASE))
        return max(0, integrated_count - original_count)
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage."""
        pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def _log_llm_call(
        self,
        request_data: dict[str, Any],
        response_text: str,
        provider: str,
    ) -> None:
        """Log an LLM API call."""
        if not self._llm_log_dir:
            return
        
        self._llm_log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}_integration_{provider}.json"
        log_path = self._llm_log_dir / log_filename
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": "integration",
            "provider": provider,
            "model": self.model,
            "request": request_data,
            "response_length": len(response_text),
        }
        
        log_path.write_text(json.dumps(log_entry, indent=2, default=str))
        self._emit(f"Logged LLM call to {log_path.name}")
    
    def _call_llm(self, prompt: str) -> tuple[str, UsageCost]:
        """Call the LLM to perform integration."""
        if self.model.startswith("gpt"):
            return self._call_openai(prompt)
        elif self.model.startswith("claude"):
            return self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported model: {self.model}")
    
    def _call_openai(self, prompt: str) -> tuple[str, UsageCost]:
        """Call OpenAI API for integration."""
        from openai import OpenAI
        
        client = OpenAI()
        
        system_prompt = load_prompt("integration_system")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        
        thinking_budget = {"low": 4000, "medium": 8000, "high": 16000}.get(
            self.thinking_level, 8000
        )
        base_output_tokens = 16000  # Larger for full report output
        max_completion_tokens = base_output_tokens + thinking_budget
        
        request_data = {
            "model": self.model,
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": self.thinking_level,
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort=self.thinking_level,
        )
        
        if not response.choices:
            self._log_llm_call(request_data, "[ERROR: no choices]", "openai")
            raise RuntimeError("OpenAI returned no choices")
        
        response_text = response.choices[0].message.content or ""
        
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        reasoning_tokens = 0
        if response.usage and hasattr(response.usage, "completion_tokens_details"):
            details = response.usage.completion_tokens_details
            if details and hasattr(details, "reasoning_tokens"):
                reasoning_tokens = details.reasoning_tokens or 0
        
        usage = UsageCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            cost_usd=self._calculate_cost(self.model, input_tokens, output_tokens),
        )
        
        self._log_llm_call(request_data, response_text, "openai")
        
        return response_text, usage
    
    def _call_anthropic(self, prompt: str) -> tuple[str, UsageCost]:
        """Call Anthropic API for integration."""
        from anthropic import Anthropic
        
        client = Anthropic()
        
        system_prompt = load_prompt("integration_system")
        
        thinking_budget = {"low": 8000, "medium": 16000, "high": 32000}.get(
            self.thinking_level, 16000
        )
        
        request_data = {
            "model": self.model,
            "max_tokens": 16000 + thinking_budget,
            "thinking_budget": thinking_budget,
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }
        
        response = client.messages.create(
            model=self.model,
            max_tokens=16000 + thinking_budget,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )
        
        response_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                response_text = block.text
                break
        
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        
        usage = UsageCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=0,
            cost_usd=self._calculate_cost(self.model, input_tokens, output_tokens),
        )
        
        self._log_llm_call(request_data, response_text, "anthropic")
        
        return response_text, usage
