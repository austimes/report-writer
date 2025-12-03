"""Report generation orchestrator."""

import base64
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .chart_reader import ChartReader, ChartSummary
from .data_catalog import ChartMeta, DataCatalog
from .outline_parser import Section, parse_outline
from .section_mapper import SectionMapper

ProgressCallback = Callable[[str], None]

DEFAULT_MODEL = "gpt-5.1-2025-11-13"
DEFAULT_THINKING_LEVEL = "medium"
QUIP_MODEL = "gpt-5-nano-2025-08-07"

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
class GenerationResult:
    """Result of generating a section."""

    section_id: str
    section_title: str
    content: str
    charts_used: list[str] = field(default_factory=list)
    prompt: str = ""
    dry_run: bool = False
    usage: UsageCost = field(default_factory=UsageCost)


class ReportOrchestrator:
    """Orchestrates report generation by coordinating outline, data, and LLM."""

    def __init__(
        self,
        outline_path: Path,
        data_root: Path,
        model: str = DEFAULT_MODEL,
        thinking_level: str = DEFAULT_THINKING_LEVEL,
        dry_run: bool = False,
        on_progress: ProgressCallback | None = None,
        llm_log_dir: Path | None = None,
        output_dir: Path | None = None,
    ):
        self.outline_path = Path(outline_path)
        self.data_root = Path(data_root)
        self.model = model
        self.thinking_level = thinking_level
        self.dry_run = dry_run
        self._on_progress = on_progress
        self._output_dir = Path(output_dir) if output_dir else None
        self._llm_log_dir = (
            Path(llm_log_dir) if llm_log_dir
            else (self._output_dir / "_llm_calls" if self._output_dir else self.data_root / "_llm_calls")
        )
        self._figures_dir: Path | None = None

        self._sections: list[Section] = []
        self._catalog: DataCatalog | None = None
        self._mapper: SectionMapper | None = None
        self._chart_reader: ChartReader | None = None
        self._current_section_id: str | None = None

        self._load()

    def _emit(self, message: str) -> None:
        """Emit a progress message if callback is set."""
        if self._on_progress:
            self._on_progress(message)

    def _setup_figures_dir(self) -> None:
        """Create figures directory if output_dir is set."""
        if self._output_dir:
            self._figures_dir = self._output_dir / "figures"
            self._figures_dir.mkdir(parents=True, exist_ok=True)

    def _copy_chart_figures(self, charts: list[ChartMeta]) -> list[str]:
        """Copy chart PNGs to figures directory, return list of copied filenames."""
        if not self._figures_dir:
            return []

        copied: list[str] = []
        for chart in charts:
            if chart.path_png and chart.path_png.exists():
                dest_filename = f"{chart.id}.png"
                dest_path = self._figures_dir / dest_filename
                shutil.copy2(chart.path_png, dest_path)
                copied.append(dest_filename)
                self._emit(f"Copied figure: {dest_filename}")
        return copied

    def _load(self) -> None:
        """Load outline and data catalog."""
        self._emit(f"Loading outline from {self.outline_path}")
        if self.outline_path.exists():
            self._sections = parse_outline(self.outline_path)
            self._emit(f"Loaded {len(self._sections)} sections")

        self._emit(f"Loading data catalog from {self.data_root}")
        if self.data_root.exists():
            self._catalog = DataCatalog(self.data_root)
            mapping_path = self.data_root / "section_chart_map.json"
            self._mapper = SectionMapper(
                self._catalog,
                mapping_path if mapping_path.exists() else None,
            )
            self._chart_reader = ChartReader(self._catalog)
            self._emit(f"Loaded {len(self._catalog.list_charts())} charts")

    @property
    def sections(self) -> list[Section]:
        """Return parsed sections."""
        return self._sections

    @property
    def catalog(self) -> DataCatalog | None:
        """Return data catalog."""
        return self._catalog

    def get_section(self, section_id: str) -> Section | None:
        """Get a section by ID."""
        for section in self._sections:
            if section.id == section_id:
                return section
        return None

    def get_charts_for_section(self, section: Section) -> list[ChartMeta]:
        """Get charts mapped to a section."""
        if self._mapper is None:
            return []
        return self._mapper.get_charts_for_section_obj(section)

    def get_chart_summary(self, chart_id: str) -> ChartSummary | None:
        """Get summary for a chart."""
        if self._chart_reader is None:
            return None
        try:
            return self._chart_reader.get_summary(chart_id)
        except ValueError:
            return None

    def build_section_prompt(self, section: Section, charts: list[ChartMeta]) -> str:
        """Build the prompt for generating a section."""
        lines = [
            f"# Task: Write the '{section.title}' section of the report",
            "",
            "## Section Information",
            f"- **Title**: {section.title}",
            f"- **Level**: {'#' * section.level} (heading level {section.level})",
        ]

        if section.parent_id:
            parent = self.get_section(section.parent_id)
            if parent:
                lines.append(f"- **Parent Section**: {parent.title}")

        if section.instructions:
            lines.extend([
                "",
                "## Instructions",
                section.instructions,
            ])

        if section.content:
            lines.extend([
                "",
                "## Existing Content",
                "The section currently contains:",
                "```",
                section.content[:1000] + ("..." if len(section.content) > 1000 else ""),
                "```",
            ])

        if charts:
            lines.extend([
                "",
                "## Available Data",
                f"The following {len(charts)} chart(s) are available for this section:",
                "",
            ])

            for chart in charts:
                lines.append(f"### {chart.title}")
                lines.append(f"- **ID**: {chart.id}")
                lines.append(f"- **Category**: {chart.category}")
                if chart.path_png and chart.path_png.exists():
                    lines.append(f"- **Figure Path**: `figures/{chart.id}.png`")
                if chart.units:
                    lines.append(f"- **Units**: {chart.units}")
                if chart.dimensions:
                    lines.append(f"- **Dimensions**: {', '.join(chart.dimensions)}")

                summary = self.get_chart_summary(chart.id)
                if summary:
                    lines.append(f"- **Scenarios**: {', '.join(summary.scenarios)}")
                    lines.append(f"- **Years**: {summary.years[0]} to {summary.years[-1]}" if summary.years else "")
                    lines.append(f"- **Rows**: {summary.row_count}")

                    if summary.key_insights:
                        lines.append("- **Key Insights**:")
                        for insight in summary.key_insights[:5]:
                            lines.append(f"  - {insight}")

                    if summary.by_scenario:
                        lines.append("- **Scenario Summaries**:")
                        for scen, stats in list(summary.by_scenario.items())[:3]:
                            lines.append(f"  - {scen}: {json.dumps(stats)}")

                lines.append("")

        lines.extend([
            "",
            "## Output Requirements",
            "1. **DO NOT include the section heading** - it will be added automatically",
            "2. Write professional, technical prose suitable for an annual report",
            "3. Reference specific data points from the charts provided",
            "4. Maintain consistency with the parent section context",
            "5. Use appropriate markdown formatting (but no top-level heading)",
            "6. Keep the content focused and concise",
            "7. **Include figures**: For each chart with a figure, include it using markdown image syntax:",
            "   - Use the exact format: `![Chart Title](figures/{chart_id}.png)`",
            "   - Use the chart ID exactly as provided (e.g., `figures/emissions_by_sector.png`)",
            "   - Place figures after relevant discussion of the data",
            "   - Caption format: `*Figure: [description of what the figure shows]*`",
            "",
            "## Scenario Naming Convention",
            "Use these exact scenario names consistently throughout:",
            "- **Ampol-1p5DS** (1.5°C-aligned pathway)",
            "- **Ampol-2p5DS** (2.5°C pathway)", 
            "- **Ampol-House-View** (reference/baseline scenario)",
            "",
            "## Content Guidelines",
            "- Focus on insights specific to this section's scope",
            "- Avoid repeating detailed analysis that belongs in other sections",
            "- Cross-reference other sections where appropriate rather than duplicating content",
            "",
            "Write the section content below (no heading):",
        ])

        return "\n".join(lines)

    def generate_section(self, section_id: str) -> GenerationResult:
        """Generate content for a single section."""
        self._setup_figures_dir()

        section = self.get_section(section_id)
        if section is None:
            return GenerationResult(
                section_id=section_id,
                section_title="Unknown",
                content=f"Error: Section '{section_id}' not found",
                dry_run=self.dry_run,
            )

        self._emit(f"Getting charts for section '{section.title}'")
        charts = self.get_charts_for_section(section)
        self._emit(f"Found {len(charts)} charts for section")

        self._emit("Building prompt")
        prompt = self.build_section_prompt(section, charts)

        if self.dry_run:
            return GenerationResult(
                section_id=section.id,
                section_title=section.title,
                content=f"[DRY RUN] Would generate content for '{section.title}' using {len(charts)} charts",
                charts_used=[c.id for c in charts],
                prompt=prompt,
                dry_run=True,
            )

        png_charts = [c for c in charts if c.path_png and c.path_png.exists()]
        if png_charts:
            self._emit(f"Sending {len(png_charts)} PNG(s) to LLM:")
            for c in png_charts:
                self._emit(f"  - {c.id}: {c.path_png}")

        self._copy_chart_figures(charts)

        self._emit(f"Calling {self.model} to generate content...")
        self._current_section_id = section.id
        raw_content, usage = self._call_llm(prompt, charts)
        self._current_section_id = None
        self._emit(f"LLM response received (${usage.cost_usd:.4f})")

        formatted_content = self._format_section_output(section, raw_content)

        return GenerationResult(
            section_id=section.id,
            section_title=section.title,
            content=formatted_content,
            charts_used=[c.id for c in charts],
            prompt=prompt,
            dry_run=False,
            usage=usage,
        )

    def generate_report(self) -> tuple[str, UsageCost]:
        """Generate content for all sections. Returns (report_content, total_usage)."""
        self._setup_figures_dir()
        sections_dir = self._setup_sections_dir()

        results: list[GenerationResult] = []
        total_usage = UsageCost()
        total = len(self._sections)

        for i, section in enumerate(self._sections, 1):
            self._emit(f"Generating section {i}/{total}: {section.title}")
            result = self.generate_section(section.id)
            results.append(result)
            total_usage = total_usage + result.usage

            if sections_dir and not result.dry_run:
                self._write_section_file(sections_dir, result, i)

        self._emit("Assembling final report")
        return self._assemble_report(results), total_usage

    def _setup_sections_dir(self) -> Path | None:
        """Create _sections directory if output_dir is set."""
        if self._output_dir:
            sections_dir = self._output_dir / "_sections"
            sections_dir.mkdir(parents=True, exist_ok=True)
            return sections_dir
        return None

    def _write_section_file(self, sections_dir: Path, result: GenerationResult, index: int) -> None:
        """Write a section result to a markdown file."""
        filename = f"{index:02d}_{result.section_id}.md"
        filepath = sections_dir / filename
        filepath.write_text(result.content)
        self._emit(f"Wrote section file: {filename}")

    def _format_section_output(self, section: Section, content: str) -> str:
        """Format a section with heading, instructions, review comments, then content."""
        lines = []

        heading = "#" * section.level
        lines.append(f"{heading} {section.title}")
        lines.append("")

        if section.instructions:
            lines.append(f"<!-- Section instructions: {section.instructions} -->")
            lines.append("")

        if section.review_comments:
            lines.append(f"<!-- Review comments:\n{section.review_comments}\n-->")
        else:
            lines.append("""<!-- Review comments:
AUTHOR: [Reviewer Name]
RATING: accuracy=, completeness=, clarity=
NOTES:
-->""")
            lines.append("")
            
            try:
                funny_name, funny_notes = self.generate_funny_reviewer_example(section.title)
            except Exception:
                funny_name = "Skeptical Steve McDoubtface"
                funny_notes = "I've seen better analysis on the back of a cereal box, but at least this one has charts."
            
            lines.append(f"""<!-- EXAMPLE - LLM IGNORE:
AUTHOR: {funny_name}
RATING: accuracy=4, completeness=3, clarity=5
NOTES: {funny_notes}
-->""")
        lines.append("")

        content = content.strip()
        if content.startswith(f"{heading} {section.title}"):
            content = content[len(f"{heading} {section.title}"):].strip()
        elif content.startswith(f"{heading} "):
            first_line_end = content.find("\n")
            if first_line_end > 0:
                content = content[first_line_end:].strip()

        lines.append(content)
        lines.append("")

        return "\n".join(lines)

    def _assemble_report(self, results: list[GenerationResult]) -> str:
        """Assemble generated sections into a full report."""
        parts = []

        for result in results:
            parts.append(result.content)

        return "\n".join(parts)

    def _call_llm(self, prompt: str, charts: list[ChartMeta] | None = None) -> tuple[str, UsageCost]:
        """Call the LLM to generate content. Returns (content, usage_cost)."""
        if self.model.startswith("gpt"):
            return self._call_openai(prompt, charts or [])
        elif self.model.startswith("claude"):
            return self._call_anthropic(prompt, charts or [])
        else:
            raise ValueError(f"Unsupported model: {self.model}")

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage."""
        pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _log_llm_call(
        self,
        section_id: str,
        request_data: dict[str, Any],
        response_text: str,
        provider: str,
    ) -> None:
        """Log an LLM API call to the _llm_calls folder."""
        self._llm_log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{timestamp}_{section_id}_{provider}.json"
        log_path = self._llm_log_dir / log_filename

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "section_id": section_id,
            "provider": provider,
            "model": self.model,
            "request": request_data,
            "response": response_text,
        }

        log_path.write_text(json.dumps(log_entry, indent=2, default=str))
        self._emit(f"Logged LLM call to {log_path.name}")

    def _encode_image(self, image_path: Path) -> str:
        """Encode an image file to base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_image_media_type(self, path: Path) -> str:
        """Get the media type for an image file."""
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

    def _call_openai(self, prompt: str, charts: list[ChartMeta]) -> tuple[str, UsageCost]:
        """Call OpenAI API with optional chart images. Returns (content, usage_cost)."""
        from openai import OpenAI

        client = OpenAI()

        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for chart in charts:
            if chart.path_png and chart.path_png.exists():
                base64_image = self._encode_image(chart.path_png)
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high",
                    },
                })

        messages = [
            {"role": "system", "content": "You are an expert report writer for energy and emissions analysis."},
            {"role": "user", "content": user_content},
        ]

        request_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert report writer for energy and emissions analysis."},
                {"role": "user", "content": f"[text prompt, {len([c for c in charts if c.path_png and c.path_png.exists()])} images]"},
            ],
            "max_tokens": 4000,
            "reasoning_effort": self.thinking_level,
            "image_count": len([c for c in charts if c.path_png and c.path_png.exists()]),
            "chart_ids": [c.id for c in charts if c.path_png and c.path_png.exists()],
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=4000,
            reasoning_effort=self.thinking_level,
        )
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

        self._log_llm_call(
            section_id=self._current_section_id or "unknown",
            request_data=request_data,
            response_text=response_text,
            provider="openai",
        )

        return response_text, usage

    def _call_anthropic(self, prompt: str, charts: list[ChartMeta]) -> tuple[str, UsageCost]:
        """Call Anthropic API with optional chart images. Returns (content, usage_cost)."""
        from anthropic import Anthropic

        client = Anthropic()

        user_content: list[dict[str, Any]] = []

        for chart in charts:
            if chart.path_png and chart.path_png.exists():
                base64_image = self._encode_image(chart.path_png)
                media_type = self._get_image_media_type(chart.path_png)
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_image,
                    },
                })

        user_content.append({"type": "text", "text": prompt})

        thinking_budget = {"low": 5000, "medium": 10000, "high": 20000}.get(self.thinking_level, 10000)

        request_data = {
            "model": self.model,
            "max_tokens": 4000 + thinking_budget,
            "system": "You are an expert report writer for energy and emissions analysis.",
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
            "image_count": len([c for c in charts if c.path_png and c.path_png.exists()]),
            "chart_ids": [c.id for c in charts if c.path_png and c.path_png.exists()],
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }

        response = client.messages.create(
            model=self.model,
            max_tokens=4000 + thinking_budget,
            messages=[{"role": "user", "content": user_content}],
            system="You are an expert report writer for energy and emissions analysis.",
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

        self._log_llm_call(
            section_id=self._current_section_id or "unknown",
            request_data=request_data,
            response_text=response_text,
            provider="anthropic",
        )

        return response_text, usage

    def generate_funny_reviewer_example(self, section_title: str) -> tuple[str, str]:
        """Generate a funny reviewer name and spicy/sarcastic comment using gpt-5-nano.
        
        Returns (name, notes) tuple.
        """
        from openai import OpenAI

        client = OpenAI()

        prompt = f"""Generate a fake reviewer for a technical report section titled "{section_title}".

Create:
1. A funny, creative fake name (can be punny, alliterative, or absurd - like "Skeptical Steve McDoubtface" or "Dr. Actually Well...")
2. A sarcastic/spicy but ultimately helpful review comment (2-3 sentences)

The comment should:
- Be playfully antagonistic or sarcastic in tone
- Still contain a kernel of useful feedback
- Be funny and memorable
- Examples of the vibe: "Oh great, another chart I have to pretend to understand" or "Did the AI learn to write from fortune cookies?"

Respond in this exact format (no other text):
NAME: [funny name here]
NOTES: [spicy comment here]"""

        response = client.chat.completions.create(
            model=QUIP_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=150,
            temperature=1.2,
        )

        result = response.choices[0].message.content or ""
        
        name = "Grumpy McReviewerface"
        notes = "I suppose this technically counts as writing."
        
        for line in result.strip().split("\n"):
            if line.startswith("NAME:"):
                name = line[5:].strip()
            elif line.startswith("NOTES:"):
                notes = line[6:].strip()
        
        return name, notes

    def generate_cost_quip(self, total_cost: float, section_count: int) -> str:
        """Generate a funny quip about the money spent using gpt-5-nano."""
        from openai import OpenAI

        client = OpenAI()

        prompt = f"""You spent ${total_cost:.2f} to generate {section_count} sections of a technical report using AI.

Write a single witty, funny one-liner celebrating this achievement. The tone should be:
- Playful and slightly sarcastic
- Appreciative of how AI saves time vs weeks of manual report writing
- Maybe hint at thanking the robots or being grateful for automation
- Keep it under 50 words

Example tone (don't copy exactly): "Man, that was the best $2.35 we ever spent... saved about 6 weeks of brain-melting report writing. Maybe you should thank the robots?"

Just respond with the quip, nothing else."""

        response = client.chat.completions.create(
            model=QUIP_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=100,
            temperature=1.2,
        )

        return response.choices[0].message.content or "Money well spent on robot helpers."
