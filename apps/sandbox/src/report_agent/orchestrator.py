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
from .prompts import get_system_prompt, load_prompt
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
        """Copy chart PNGs and CSVs to figures directory, return list of copied PNG filenames."""
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
            if chart.path_csv and chart.path_csv.exists():
                csv_filename = f"{chart.id}.csv"
                csv_dest_path = self._figures_dir / csv_filename
                shutil.copy2(chart.path_csv, csv_dest_path)
                self._emit(f"Copied CSV: {csv_filename}")
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
            mapping_path = self._find_mapping_file()
            self._mapper = SectionMapper(
                self._catalog,
                mapping_path,
            )
            self._chart_reader = ChartReader(self._catalog)
            self._emit(f"Loaded {len(self._catalog.list_charts())} charts")

    def _find_mapping_file(self) -> Path | None:
        """Find section_chart_map.json in data dir or outline dir."""
        data_mapping = self.data_root / "section_chart_map.json"
        if data_mapping.exists():
            self._emit(f"Using mapping file: {data_mapping}")
            return data_mapping

        outline_mapping = self.outline_path.parent / "section_chart_map.json"
        if outline_mapping.exists():
            self._emit(f"Using mapping file: {outline_mapping}")
            return outline_mapping

        self._emit("No section_chart_map.json found, using auto-mapping")
        return None

    def _get_section_index(self, section: Section) -> int:
        """Get 1-based index of section in outline order."""
        return self._sections.index(section) + 1

    def _get_section_path(self, section: Section) -> Path:
        """Get the canonical path for a section file in _sections/."""
        if self._output_dir is None:
            raise ValueError("output_dir must be set to get section path")
        sections_dir = self._output_dir / "_sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        idx = self._get_section_index(section)
        filename = f"{idx:02d}_{section.id}.md"
        return sections_dir / filename

    def _load_existing_section_body(self, section: Section) -> str:
        """Load existing section content, preferring _sections/ file over outline.
        
        This allows manual edits in section files to be preserved and fed into
        subsequent LLM operations.
        
        Returns:
            The content from the section file if it exists, otherwise
            the content from the outline, or empty string if neither has content.
        """
        if self._output_dir:
            try:
                path = self._get_section_path(section)
                if path.exists():
                    return path.read_text()
            except ValueError:
                pass  # output_dir not set, fall through to outline content
        return section.content or ""

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
        """Build the prompt for generating a section.
        
        Uses the template from prompts/section_generation.md with dynamic blocks
        for parent section, instructions, existing content, and chart data.
        """
        parent_section_line = ""
        if section.parent_id:
            parent = self.get_section(section.parent_id)
            if parent:
                parent_section_line = f"- **Parent Section**: {parent.title}"

        instructions_block = ""
        if section.instructions:
            instructions_block = f"## Instructions\n{section.instructions}"

        existing_content_block = ""
        existing_body = self._load_existing_section_body(section)
        if existing_body:
            truncated = existing_body[:2000] + ("..." if len(existing_body) > 2000 else "")
            existing_content_block = f"## Existing Content\nThe section currently contains:\n```\n{truncated}\n```"

        available_data_block = self._build_available_data_block(charts)

        template = load_prompt("section_generation")
        return template.format(
            section_title=section.title,
            heading_markers="#" * section.level,
            section_level=section.level,
            parent_section_line=parent_section_line,
            instructions_block=instructions_block,
            existing_content_block=existing_content_block,
            available_data_block=available_data_block,
        )

    def _build_available_data_block(self, charts: list[ChartMeta]) -> str:
        """Build the available data block for prompts."""
        if not charts:
            return ""

        lines = [
            "## Available Data",
            f"The following {len(charts)} chart(s) are available for this section:",
            "",
        ]
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
                if summary.years:
                    lines.append(f"- **Years**: {summary.years[0]} to {summary.years[-1]}")
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
        return "\n".join(lines)

    def build_section_revision_prompt(
        self,
        section: Section,
        charts: list[ChartMeta],
        extra_revision_notes: str | None = None,
    ) -> str:
        """Build the prompt for revising a section based on review comments.

        Uses the template from prompts/section_revision.txt with dynamic blocks
        for existing content, review feedback, and chart data.
        """
        parent_section_line = ""
        if section.parent_id:
            parent = self.get_section(section.parent_id)
            if parent:
                parent_section_line = f"- **Parent Section**: {parent.title}"

        instructions_block = section.instructions or "(No specific instructions)"

        existing_content = self._load_existing_section_body(section)
        if len(existing_content) > 4000:
            existing_content = existing_content[:4000] + "\n\n[...content truncated for length...]"

        review_lines = ["### Current Review Feedback"]
        if section.review_author:
            review_lines.append(f"- **Reviewer**: {section.review_author}")
        if section.review_ratings:
            rating_str = ", ".join(f"{k}={v}" for k, v in section.review_ratings.items())
            review_lines.append(f"- **Ratings**: {rating_str}")
        if section.review_notes:
            review_lines.append("\n**Review Notes** (address these explicitly):")
            review_lines.append(f"```\n{section.review_notes}\n```")
        if extra_revision_notes:
            review_lines.append("\n**Additional Revision Instructions**:")
            review_lines.append(extra_revision_notes)
        if not section.review_notes and not extra_revision_notes:
            review_lines.append("(No specific feedback provided)")
        review_block = "\n".join(review_lines)

        available_data_block = self._build_available_data_block(charts)

        template = load_prompt("section_revision")
        return template.format(
            section_title=section.title,
            heading_markers="#" * section.level,
            parent_section_line=parent_section_line,
            instructions_block=instructions_block,
            existing_content=existing_content,
            review_block=review_block,
            available_data_block=available_data_block,
        )

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

    def update_section(
        self,
        section_id: str,
        extra_revision_notes: str | None = None,
    ) -> GenerationResult:
        """Revise a section based on its review comments.
        
        Reads the existing section file, builds a revision prompt including
        review feedback, calls the LLM, and returns the revised content.
        
        Args:
            section_id: ID of the section to update
            extra_revision_notes: Optional additional revision instructions
            
        Returns:
            GenerationResult with the revised content
            
        Raises:
            ValueError: If section not found or no existing content
        """
        self._setup_figures_dir()
        
        section = self.get_section(section_id)
        if section is None:
            return GenerationResult(
                section_id=section_id,
                section_title="Unknown",
                content=f"Error: Section '{section_id}' not found",
                dry_run=self.dry_run,
            )

        self._current_section_id = section_id

        existing_body = self._load_existing_section_body(section)
        if not existing_body.strip():
            raise ValueError(
                f"No existing content for section '{section_id}'. "
                "Run generate-section first."
            )

        self._emit(f"Getting charts for section '{section.title}'")
        charts = self.get_charts_for_section(section)
        self._emit(f"Found {len(charts)} charts for section")
        
        self._copy_chart_figures(charts)

        self._emit("Building revision prompt")
        prompt = self.build_section_revision_prompt(
            section=section,
            charts=charts,
            extra_revision_notes=extra_revision_notes,
        )

        if self.dry_run:
            return GenerationResult(
                section_id=section.id,
                section_title=section.title,
                content=f"[DRY RUN] Would revise section based on review feedback",
                charts_used=[c.id for c in charts],
                prompt=prompt,
                dry_run=True,
            )

        png_charts = [c for c in charts if c.path_png and c.path_png.exists()]
        if png_charts:
            self._emit(f"Sending {len(png_charts)} PNG(s) to LLM:")
            for c in png_charts:
                self._emit(f"  - {c.id}: {c.path_png}")

        self._emit(f"Calling {self.model} to revise content...")
        raw_content, usage = self._call_llm(prompt, charts)
        self._emit(f"LLM response received (${usage.cost_usd:.4f})")

        formatted_content = self._format_section_output(section, raw_content)

        section_path = self._get_section_path(section)
        section_path.write_text(formatted_content)
        self._emit(f"Updated section file: {section_path.name}")

        self._current_section_id = None

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

            if self._output_dir and not result.dry_run:
                self._write_section_file(result)

        self._emit("Assembling final report from section files")
        report_content = self._build_report_from_sections()
        return report_content, total_usage

    def update_report(
        self, extra_revision_notes: str | None = None
    ) -> tuple[str, UsageCost, dict[str, str]]:
        """Update existing sections and generate missing ones.
        
        For each section:
        - If section file exists: update it (using review feedback if present)
        - If section file doesn't exist: generate fresh content
        
        Args:
            extra_revision_notes: Additional instructions for updating sections.
        
        Returns:
            Tuple of (report_content, total_usage, action_map) where action_map
            is a dict mapping section_id to "generated" or "updated".
        """
        self._setup_figures_dir()
        self._setup_sections_dir()

        results: list[GenerationResult] = []
        total_usage = UsageCost()
        action_map: dict[str, str] = {}
        total = len(self._sections)

        for i, section in enumerate(self._sections, 1):
            section_path = self._get_section_path(section)
            
            if section_path.exists():
                self._emit(f"Updating section {i}/{total}: {section.title}")
                result = self.update_section(section.id, extra_revision_notes)
                action_map[section.id] = "updated"
            else:
                self._emit(f"Generating section {i}/{total}: {section.title}")
                result = self.generate_section(section.id)
                if self._output_dir and not result.dry_run:
                    self._write_section_file(result)
                action_map[section.id] = "generated"
            
            results.append(result)
            total_usage = total_usage + result.usage

        self._emit("Assembling final report from section files")
        report_content = self._build_report_from_sections()
        return report_content, total_usage, action_map

    def _setup_sections_dir(self) -> Path | None:
        """Create _sections directory if output_dir is set."""
        if self._output_dir:
            sections_dir = self._output_dir / "_sections"
            sections_dir.mkdir(parents=True, exist_ok=True)
            return sections_dir
        return None

    def _write_section_file(self, result: GenerationResult) -> None:
        """Write a section result to its canonical markdown file."""
        section = self.get_section(result.section_id)
        if section is None:
            self._emit(f"Warning: Could not find section {result.section_id} to write")
            return
        filepath = self._get_section_path(section)
        filepath.write_text(result.content)
        self._emit(f"Wrote section file: {filepath.name}")

    def _build_report_from_sections(self) -> str:
        """Concatenate section files in outline order to produce report.md content.
        
        Each section is wrapped with BEGIN/END markers for traceability.
        Missing sections get a placeholder comment.
        
        Returns:
            The complete report content as a string.
        """
        if self._output_dir is None:
            raise ValueError("output_dir must be set to build report from sections")
        
        parts = [
            "<!-- GENERATED FILE: Do not edit directly. Edit files in _sections/ instead. -->\n"
        ]
        
        for section in self._sections:
            try:
                path = self._get_section_path(section)
            except ValueError:
                continue
                
            parts.append(f"<!-- BEGIN SECTION: {section.id} ({section.title}) -->")
            
            if path.exists():
                content = path.read_text().strip()
                parts.append(content)
            else:
                parts.append(f"<!-- SECTION MISSING: {section.id} - {section.title} -->")
            
            parts.append(f"<!-- END SECTION: {section.id} -->\n")
        
        return "\n".join(parts)

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

        system_prompt = get_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        thinking_budget = {"low": 2000, "medium": 6000, "high": 10000}.get(self.thinking_level, 6000)
        base_output_tokens = 4000
        max_completion_tokens = base_output_tokens + thinking_budget

        image_count = len([c for c in charts if c.path_png and c.path_png.exists()])
        request_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"[text prompt, {image_count} images]"},
            ],
            "max_completion_tokens": max_completion_tokens,
            "reasoning_effort": self.thinking_level,
            "image_count": image_count,
            "chart_ids": [c.id for c in charts if c.path_png and c.path_png.exists()],
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort=self.thinking_level,
        )

        if not response.choices:
            self._log_llm_call(
                section_id=self._current_section_id or "unknown",
                request_data=request_data,
                response_text="[ERROR: no choices returned from OpenAI]",
                provider="openai",
            )
            raise RuntimeError("OpenAI returned no choices")

        choice = response.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        response_text = choice.message.content or ""

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        reasoning_tokens = 0
        if response.usage and hasattr(response.usage, "completion_tokens_details"):
            details = response.usage.completion_tokens_details
            if details and hasattr(details, "reasoning_tokens"):
                reasoning_tokens = details.reasoning_tokens or 0

        usage_info = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "finish_reason": finish_reason,
        }
        request_data["usage_info"] = usage_info

        if not response_text.strip():
            error_msg = (
                f"[ERROR: OpenAI returned empty content; "
                f"finish_reason={finish_reason}, usage={usage_info}]"
            )
            self._log_llm_call(
                section_id=self._current_section_id or "unknown",
                request_data=request_data,
                response_text=error_msg,
                provider="openai",
            )
            raise RuntimeError(error_msg)

        if finish_reason == "length":
            self._emit(f"Warning: response truncated (finish_reason=length), tokens: {usage_info}")

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
        system_prompt = get_system_prompt()

        request_data = {
            "model": self.model,
            "max_tokens": 4000 + thinking_budget,
            "system": system_prompt,
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
            "image_count": len([c for c in charts if c.path_png and c.path_png.exists()]),
            "chart_ids": [c.id for c in charts if c.path_png and c.path_png.exists()],
            "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
        }

        response = client.messages.create(
            model=self.model,
            max_tokens=4000 + thinking_budget,
            messages=[{"role": "user", "content": user_content}],
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

        template = load_prompt("funny_reviewer")
        prompt = template.format(section_title=section_title)

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

        template = load_prompt("cost_quip")
        prompt = template.format(total_cost=f"{total_cost:.2f}", section_count=section_count)

        response = client.chat.completions.create(
            model=QUIP_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=100,
            temperature=1.2,
        )

        return response.choices[0].message.content or "Money well spent on robot helpers."
