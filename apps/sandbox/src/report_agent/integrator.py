"""Report integration pass for deduplicating and cross-referencing sections.

This module provides the ReportIntegrator class that runs an LLM pass over
the complete report to identify duplicates, assign canonical figure/table
numbers, and add cross-references between sections.
"""

from __future__ import annotations

import base64
import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .outline_parser import Section
from .prompts import load_prompt
from .report_state import ReportState, CanonicalFigure, CanonicalTable, SectionStateMeta
from .section_meta import (
    SectionMetaComment,
    IntegrationHints,
    IntegrationNote,
    parse_section_meta,
    inject_section_meta,
    serialize_section_meta,
)

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


@dataclass
class UsageCost:
    """Token usage and cost for an LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "UsageCost") -> "UsageCost":
        return UsageCost(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


@dataclass
class IntegrationResult:
    """Result of running the integration pass."""
    integrated_content: str
    report_state: ReportState
    sections_modified: list[str] = field(default_factory=list)
    duplicates_removed: int = 0
    cross_refs_added: int = 0
    usage: UsageCost = field(default_factory=UsageCost)
    validation_passed: bool = True
    validation_message: str = ""


REPORT_STATE_UPDATE_PATTERN = re.compile(
    r'<!--\s*REPORT_STATE_UPDATE\s*\n(.*?)\n\s*-->',
    re.DOTALL
)


class ReportIntegrator:
    """Runs the integration pass over a complete report.
    
    The integrator takes the assembled report content and report state,
    calls an LLM to identify duplicates and add cross-references, then
    parses the response to extract the updated content and state.
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
        report_state: ReportState,
        sections: list[Section],
        max_change_ratio: float = 0.3,
    ) -> IntegrationResult:
        """Run integration pass on assembled report.
        
        Args:
            report_content: The full report markdown content
            report_state: Current ReportState tracking figures/tables
            sections: List of Section objects from the outline
            max_change_ratio: Maximum allowed change ratio (0.0-1.0)
            
        Returns:
            IntegrationResult with integrated content and updated state
        """
        self._emit("Building integration prompt...")
        prompt = self._build_integration_prompt(report_content, report_state, sections)
        
        if self.dry_run:
            self._emit("[DRY RUN] Would call LLM for integration")
            return IntegrationResult(
                integrated_content=report_content,
                report_state=report_state,
                sections_modified=[],
                duplicates_removed=0,
                cross_refs_added=0,
                usage=UsageCost(),
                validation_passed=True,
                validation_message="Dry run - no changes made",
            )
        
        self._emit(f"Calling {self.model} for integration pass...")
        response_text, usage = self._call_llm(prompt)
        self._emit(f"LLM response received (${usage.cost_usd:.4f})")
        
        self._emit("Parsing integration response...")
        integrated_content, updated_state = self._parse_integration_response(
            response_text, report_state
        )
        
        self._emit("Validating changes...")
        is_valid, validation_msg = self._validate_changes(
            report_content, integrated_content, max_change_ratio
        )
        
        sections_modified = self._detect_modified_sections(
            report_content, integrated_content, sections
        )
        
        duplicates_removed = self._count_pattern_changes(
            report_content, integrated_content, r'!\[.*?\]\(figures/.*?\)'
        )
        
        cross_refs_added = len(re.findall(
            r'(?:see\s+)?(?:Figure|Table)\s+\d+',
            integrated_content,
            re.IGNORECASE
        )) - len(re.findall(
            r'(?:see\s+)?(?:Figure|Table)\s+\d+',
            report_content,
            re.IGNORECASE
        ))
        cross_refs_added = max(0, cross_refs_added)
        
        for section_id in sections_modified:
            updated_state.mark_section_integrated(section_id)
        
        return IntegrationResult(
            integrated_content=integrated_content,
            report_state=updated_state,
            sections_modified=sections_modified,
            duplicates_removed=max(0, duplicates_removed),
            cross_refs_added=cross_refs_added,
            usage=usage,
            validation_passed=is_valid,
            validation_message=validation_msg,
        )
    
    def _build_integration_prompt(
        self,
        report_content: str,
        report_state: ReportState,
        sections: list[Section],
    ) -> str:
        """Build the integration prompt from template."""
        template = load_prompt("report_integration")
        
        state_dict = {
            "report_id": report_state.report_id,
            "figures": [
                {
                    "id": f.id,
                    "semantic_key": f.semantic_key,
                    "owner_section": f.owner_section,
                    "caption": f.caption,
                    "chart_id": f.chart_id,
                }
                for f in report_state.figures
            ],
            "tables": [
                {
                    "id": t.id,
                    "semantic_key": t.semantic_key,
                    "owner_section": t.owner_section,
                    "caption": t.caption,
                }
                for t in report_state.tables
            ],
            "section_meta": {
                k: {
                    "section_id": v.section_id,
                    "version": v.version,
                    "last_integrated_version": v.last_integrated_version,
                }
                for k, v in report_state.section_meta.items()
            },
        }
        
        return template.format(
            section_count=len(sections),
            report_state_json=json.dumps(state_dict, indent=2),
            full_report_content=report_content,
            report_id=report_state.report_id,
        )
    
    def _parse_integration_response(
        self,
        response: str,
        original_state: ReportState,
    ) -> tuple[str, ReportState]:
        """Parse LLM response to extract content and state update.
        
        Args:
            response: Raw LLM response text
            original_state: Original ReportState for fallback
            
        Returns:
            Tuple of (integrated_content, updated_state)
        """
        match = REPORT_STATE_UPDATE_PATTERN.search(response)
        
        integrated_content = response
        updated_state = original_state
        
        if match:
            integrated_content = REPORT_STATE_UPDATE_PATTERN.sub('', response).strip()
            
            state_json_str = match.group(1).strip()
            try:
                state_data = json.loads(state_json_str)
                updated_state = self._parse_state_update(state_data, original_state)
            except json.JSONDecodeError as e:
                self._emit(f"Warning: Could not parse REPORT_STATE_UPDATE: {e}")
        else:
            self._emit("Warning: No REPORT_STATE_UPDATE block found in response")
        
        return integrated_content, updated_state
    
    def _parse_state_update(
        self,
        state_data: dict[str, Any],
        original_state: ReportState,
    ) -> ReportState:
        """Parse a state update dictionary into a ReportState."""
        figures = [
            CanonicalFigure(
                id=f["id"],
                semantic_key=f.get("semantic_key", ""),
                owner_section=f.get("owner_section", ""),
                caption=f.get("caption", ""),
                chart_id=f.get("chart_id"),
            )
            for f in state_data.get("figures", [])
        ]
        
        tables = [
            CanonicalTable(
                id=t["id"],
                semantic_key=t.get("semantic_key", ""),
                owner_section=t.get("owner_section", ""),
                caption=t.get("caption", ""),
            )
            for t in state_data.get("tables", [])
        ]
        
        section_meta = {}
        for k, v in state_data.get("section_meta", {}).items():
            section_meta[k] = SectionStateMeta(
                section_id=v.get("section_id", k),
                version=v.get("version", 1),
                last_integrated_version=v.get("last_integrated_version", 0),
            )
        
        return ReportState(
            report_id=state_data.get("report_id", original_state.report_id),
            figures=figures,
            tables=tables,
            section_meta=section_meta,
            created_at=original_state.created_at,
            updated_at=datetime.now().isoformat(),
        )
    
    def _validate_changes(
        self,
        original: str,
        integrated: str,
        max_change_ratio: float = 0.3,
    ) -> tuple[bool, str]:
        """Check if changes are within acceptable bounds.
        
        Args:
            original: Original content
            integrated: Integrated content
            max_change_ratio: Maximum allowed change ratio
            
        Returns:
            Tuple of (is_valid, message)
        """
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
        sections: list[Section],
    ) -> list[str]:
        """Detect which sections were modified."""
        modified = []
        
        for section in sections:
            original_section = self._extract_section_content(original, section.id)
            integrated_section = self._extract_section_content(integrated, section.id)
            
            if original_section != integrated_section:
                modified.append(section.id)
        
        return modified
    
    def _extract_section_content(self, content: str, section_id: str) -> str:
        """Extract content for a specific section by ID."""
        pattern = rf'<!-- BEGIN SECTION: {re.escape(section_id)} .*?-->(.*?)<!-- END SECTION: {re.escape(section_id)} -->'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def _count_pattern_changes(
        self,
        original: str,
        integrated: str,
        pattern: str,
    ) -> int:
        """Count how many times a pattern was removed."""
        original_count = len(re.findall(pattern, original))
        integrated_count = len(re.findall(pattern, integrated))
        return original_count - integrated_count
    
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
        """Call the LLM to perform integration. Returns (content, usage_cost)."""
        if self.model.startswith("gpt"):
            return self._call_openai(prompt)
        elif self.model.startswith("claude"):
            return self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported model: {self.model}")
    
    def _call_openai(self, prompt: str) -> tuple[str, UsageCost]:
        """Call OpenAI API for integration. Returns (content, usage_cost)."""
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
        base_output_tokens = 8000
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
        """Call Anthropic API for integration. Returns (content, usage_cost)."""
        from anthropic import Anthropic
        
        client = Anthropic()
        
        system_prompt = load_prompt("integration_system")
        
        thinking_budget = {"low": 8000, "medium": 16000, "high": 32000}.get(
            self.thinking_level, 16000
        )
        
        request_data = {
            "model": self.model,
            "max_tokens": 8000 + thinking_budget,
            "thinking_budget": thinking_budget,
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }
        
        response = client.messages.create(
            model=self.model,
            max_tokens=8000 + thinking_budget,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )
        
        response_text = response.content[0].text if response.content else ""
        
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
