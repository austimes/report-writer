"""CLI for the Report Agent."""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .data_catalog import DataCatalog
from .orchestrator import DEFAULT_MODEL, DEFAULT_THINKING_LEVEL, ReportOrchestrator, UsageCost
from .outline_parser import parse_outline

def has_existing_project(output_root: Path) -> bool:
    """Check if output directory contains existing generated content.
    
    Returns True if the directory has section files or a report.md,
    indicating this is an existing project that shouldn't be overwritten
    without --force.
    """
    sections_dir = output_root / "_sections"
    if sections_dir.exists() and any(sections_dir.glob("*.md")):
        return True
    if (output_root / "report.md").exists():
        return True
    return False


app = typer.Typer(
    name="report-agent",
    help="Report Agent CLI for generating and inspecting reports.",
    no_args_is_help=True,
)
console = Console()


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


def _make_progress_callback(status_obj=None):
    """Create a progress callback that updates console or status spinner."""
    def callback(message: str) -> None:
        if status_obj:
            status_obj.update(f"[bold blue]{message}[/bold blue]")
        else:
            console.print(f"[dim]→ {message}[/dim]")
    return callback


def _extract_chart_references(content: str, available_chart_ids: list[str]) -> list[str]:
    """Extract which chart IDs are referenced in the generated content."""
    referenced = []
    for chart_id in available_chart_ids:
        if chart_id in content or f"{chart_id}.png" in content:
            referenced.append(chart_id)
    return referenced


@app.command("generate-section")
def generate_section(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    section: str = typer.Option(..., "--section", "-s", help="Section ID to generate"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing section file"),
) -> None:
    """Generate a single section draft."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    output_root.mkdir(parents=True, exist_ok=True)

    if dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Generating section '{section}'")
        console.print()
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            model=model,
            thinking_level=thinking,
            dry_run=dry_run,
            on_progress=_make_progress_callback() if verbose else None,
            output_dir=output_root,
        )
    else:
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                output_dir=output_root,
            )

    section_obj = orchestrator.get_section(section)
    if section_obj is None:
        console.print(f"[red]Error:[/red] Section '{section}' not found")
        available = [s.id for s in orchestrator.sections]
        console.print(f"[dim]Available sections: {', '.join(available)}[/dim]")
        raise typer.Exit(1)

    section_path = orchestrator._get_section_path(section_obj)

    if section_path.exists() and not force:
        console.print(f"[red]Error:[/red] Section file already exists: {section_path}")
        console.print()
        console.print("Options:")
        console.print("  • Use [cyan]update-section[/cyan] to revise based on review feedback")
        console.print("  • Use [cyan]--force[/cyan] to regenerate from scratch")
        raise typer.Exit(1)

    charts = orchestrator.get_charts_for_section(section_obj)
    chart_ids = [c.id for c in charts]
    png_charts = [c for c in charts if c.path_png and c.path_png.exists()]
    png_chart_ids = [c.id for c in png_charts]

    console.print("[bold cyan]Charts found:[/bold cyan]")
    if chart_ids:
        for cid in chart_ids:
            console.print(f"  [dim]•[/dim] [green]{cid}[/green]")
    else:
        console.print("  [dim]none[/dim]")

    console.print("[bold cyan]Charts with PNGs (sending to LLM):[/bold cyan]")
    if png_chart_ids:
        for cid in png_chart_ids:
            console.print(f"  [dim]•[/dim] [yellow]{cid}[/yellow]")
    else:
        console.print("  [dim]none[/dim]")
    console.print()

    if dry_run:
        result = orchestrator.generate_section(section)
        console.print("[bold]Prompt that would be sent:[/bold]")
        console.print()
        console.print(result.prompt)
        console.print()
        console.print(f"[dim]Charts: {', '.join(result.charts_used) or 'none'}[/dim]")
        console.print(f"[dim]Model: {model}[/dim]")
        console.print(f"[dim]Would write to: {section_path}[/dim]")
    else:
        with console.status(f"[bold blue]Generating section '{section}'...[/bold blue]", spinner="dots") as status:
            orchestrator._on_progress = _make_progress_callback(status)
            result = orchestrator.generate_section(section)

        # Write the section file
        orchestrator._write_section_file(result)

        charts_referenced = _extract_chart_references(result.content, chart_ids)

        report_content = orchestrator._build_report_from_sections()
        report_path = output_root / "report.md"
        report_path.write_text(report_content)
        console.print(f"[green]✓[/green] Updated {report_path}")

        console.print(f"[green]✓[/green] Generated section written to {section_path}")
        console.print("[bold cyan]Charts referenced in output:[/bold cyan]")
        if charts_referenced:
            for cid in charts_referenced:
                console.print(f"  [dim]•[/dim] [magenta]{cid}[/magenta]")
        else:
            console.print("  [dim]none[/dim]")
        console.print(f"[bold cyan]Cost: ${result.usage.cost_usd:.4f}[/bold cyan] ({result.usage.input_tokens:,} in / {result.usage.output_tokens:,} out tokens)")


@app.command("update-section")
def update_section(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    section: str = typer.Option(..., "--section", "-s", help="Section ID to update"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    revision_notes: Optional[Path] = typer.Option(None, "--revision-notes", "-R", help="Additional revision instructions (markdown file)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """Update a section based on review comments."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    if not output_root.exists():
        console.print(f"[red]Error:[/red] Output root not found: {output_root}")
        console.print("[dim]Run generate-section or generate-report first.[/dim]")
        raise typer.Exit(1)

    # Load extra revision notes if provided
    extra_notes = None
    if revision_notes:
        if not revision_notes.exists():
            console.print(f"[red]Error:[/red] Revision notes file not found: {revision_notes}")
            raise typer.Exit(1)
        extra_notes = revision_notes.read_text()

    if dry_run:
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            model=model,
            thinking_level=thinking,
            dry_run=dry_run,
            on_progress=_make_progress_callback() if verbose else None,
            output_dir=output_root,
        )
    else:
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                output_dir=output_root,
            )

    section_obj = orchestrator.get_section(section)
    if section_obj is None:
        console.print(f"[red]Error:[/red] Section '{section}' not found")
        available = [s.id for s in orchestrator.sections]
        console.print(f"[dim]Available sections: {', '.join(available)}[/dim]")
        raise typer.Exit(1)

    # Check section file exists
    section_path = orchestrator._get_section_path(section_obj)
    if not section_path.exists():
        console.print(f"[red]Error:[/red] No existing section file: {section_path}")
        console.print("[dim]Run generate-section first to create the initial draft.[/dim]")
        raise typer.Exit(1)

    # Show review info
    if section_obj.review_author or section_obj.review_notes:
        console.print("[bold cyan]Review feedback:[/bold cyan]")
        if section_obj.review_author:
            console.print(f"  [dim]Author:[/dim] {section_obj.review_author}")
        if section_obj.review_ratings:
            ratings = ", ".join(f"{k}={v}" for k, v in section_obj.review_ratings.items())
            console.print(f"  [dim]Ratings:[/dim] {ratings}")
        if section_obj.review_notes:
            notes_preview = section_obj.review_notes[:100]
            if len(section_obj.review_notes) > 100:
                notes_preview += "..."
            console.print(f"  [dim]Notes:[/dim] {notes_preview}")
        console.print()
    else:
        console.print("[yellow]Warning:[/yellow] No review comments found in outline for this section.")
        if not extra_notes:
            console.print("[dim]Consider adding review comments to the outline or using --revision-notes.[/dim]")
            console.print()

    charts = orchestrator.get_charts_for_section(section_obj)
    chart_ids = [c.id for c in charts]

    console.print("[bold cyan]Charts available:[/bold cyan]")
    if chart_ids:
        for cid in chart_ids:
            console.print(f"  [dim]•[/dim] [green]{cid}[/green]")
    else:
        console.print("  [dim]none[/dim]")
    console.print()

    if dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would update section '{section}'")
        console.print(f"[dim]Section file: {section_path}[/dim]")
        console.print()
        
        # Build and show the prompt
        prompt = orchestrator.build_section_revision_prompt(
            section=section_obj,
            charts=charts,
            extra_revision_notes=extra_notes,
        )
        console.print("[bold]Revision prompt that would be sent:[/bold]")
        console.print()
        console.print(prompt)
    else:
        with console.status(f"[bold blue]Updating section '{section}'...[/bold blue]", spinner="dots") as status:
            orchestrator._on_progress = _make_progress_callback(status)
            result = orchestrator.update_section(section, extra_revision_notes=extra_notes)

        console.print(f"[green]✓[/green] Updated section: {section_path}")
        
        # Rebuild report.md
        report_content = orchestrator._build_report_from_sections()
        report_path = output_root / "report.md"
        report_path.write_text(report_content)
        console.print(f"[green]✓[/green] Rebuilt {report_path}")

        charts_referenced = _extract_chart_references(result.content, chart_ids)
        console.print("[bold cyan]Charts referenced in output:[/bold cyan]")
        if charts_referenced:
            for cid in charts_referenced:
                console.print(f"  [dim]•[/dim] [magenta]{cid}[/magenta]")
        else:
            console.print("  [dim]none[/dim]")
        console.print(f"[bold cyan]Cost: ${result.usage.cost_usd:.4f}[/bold cyan] ({result.usage.input_tokens:,} in / {result.usage.output_tokens:,} out tokens)")


@app.command("generate-report")
def generate_report(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing sections"),
) -> None:
    """Generate full report (all sections)."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    if has_existing_project(output_root) and not force:
        console.print(f"[red]Error:[/red] Output directory already contains generated content.")
        console.print(f"[dim]Found existing sections in {output_root}[/dim]")
        console.print()
        console.print("Options:")
        console.print("  • Use [cyan]update-section[/cyan] to revise specific sections")
        console.print("  • Use [cyan]--force[/cyan] to regenerate all sections")
        raise typer.Exit(1)

    output_root.mkdir(parents=True, exist_ok=True)

    if dry_run:
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            model=model,
            thinking_level=thinking,
            dry_run=dry_run,
            on_progress=_make_progress_callback() if verbose else None,
            output_dir=output_root,
        )

        section_count = len(orchestrator.sections)
        console.print(f"[bold]Generating report with {section_count} sections...[/bold]")
        console.print("[yellow]DRY RUN:[/yellow] Showing what would be generated")
        console.print()

        for section in orchestrator.sections:
            charts = orchestrator.get_charts_for_section(section)
            console.print(f"  {'#' * section.level} {section.title}")
            console.print(f"    [dim]Charts: {', '.join(c.id for c in charts) or 'none'}[/dim]")

        console.print()
        console.print(f"[dim]Model: {model}[/dim]")
        console.print(f"[dim]Thinking: {thinking}[/dim]")
        console.print(f"[dim]Output: {output_root / 'report.md'}[/dim]")
        console.print(f"[dim]Figures: {output_root / 'figures'}[/dim]")
    else:
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                output_dir=output_root,
            )

        section_count = len(orchestrator.sections)
        console.print(f"[bold]Generating report with {section_count} sections...[/bold]")

        def section_progress(message: str) -> None:
            if message.startswith("Generating section"):
                console.print(f"[bold blue]→ {message}[/bold blue]")
            elif message.startswith("LLM response"):
                console.print(f"  [green]✓[/green] {message}")
            elif verbose:
                console.print(f"  [dim]{message}[/dim]")

        orchestrator._on_progress = section_progress
        report_content, total_usage = orchestrator.generate_report()

        report_path = output_root / "report.md"
        report_path.write_text(report_content)
        console.print(f"[green]✓[/green] Report written to {report_path}")
        figures_dir = output_root / "figures"
        if figures_dir.exists():
            figure_count = len(list(figures_dir.glob("*.png")))
            console.print(f"[green]✓[/green] {figure_count} figure(s) copied to {figures_dir}")
        sections_dir = output_root / "_sections"
        if sections_dir.exists():
            section_file_count = len(list(sections_dir.glob("*.md")))
            console.print(f"[green]✓[/green] {section_file_count} section file(s) written to {sections_dir}")

        console.print()
        console.print(f"[bold cyan]Total Cost: ${total_usage.cost_usd:.2f}[/bold cyan]")
        console.print(f"[dim]Tokens: {total_usage.input_tokens:,} in / {total_usage.output_tokens:,} out[/dim]")
        if total_usage.reasoning_tokens > 0:
            console.print(f"[dim]Reasoning tokens: {total_usage.reasoning_tokens:,}[/dim]")

        try:
            quip = orchestrator.generate_cost_quip(total_usage.cost_usd, section_count)
            console.print()
            console.print(f"[italic yellow]{quip}[/italic yellow]")
        except Exception:
            pass


@app.command("update-report")
def update_report(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    revision_notes: Optional[Path] = typer.Option(None, "--revision-notes", "-R", help="Additional revision instructions (markdown file)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """Update existing sections and generate missing ones.
    
    For each section in the outline:
    - If section file exists: update it based on review feedback
    - If section file doesn't exist: generate fresh content
    
    This is useful when you have partially generated a report and want to
    continue generation while also incorporating review feedback on existing sections.
    """
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    if not output_root.exists():
        console.print(f"[red]Error:[/red] Output root not found: {output_root}")
        console.print("[dim]Run generate-section or generate-report first to create initial content.[/dim]")
        raise typer.Exit(1)

    extra_notes = None
    if revision_notes:
        if not revision_notes.exists():
            console.print(f"[red]Error:[/red] Revision notes file not found: {revision_notes}")
            raise typer.Exit(1)
        extra_notes = revision_notes.read_text()

    if dry_run:
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            model=model,
            thinking_level=thinking,
            dry_run=dry_run,
            on_progress=_make_progress_callback() if verbose else None,
            output_dir=output_root,
        )

        console.print("[yellow]DRY RUN:[/yellow] Showing what would be done")
        console.print()

        existing_count = 0
        missing_count = 0

        for section in orchestrator.sections:
            section_path = orchestrator._get_section_path(section)
            charts = orchestrator.get_charts_for_section(section)
            chart_str = f"Charts: {', '.join(c.id for c in charts) or 'none'}"

            if section_path.exists():
                existing_count += 1
                console.print(f"  [cyan]UPDATE[/cyan] {'#' * section.level} {section.title}")
                console.print(f"    [dim]{chart_str}[/dim]")
            else:
                missing_count += 1
                console.print(f"  [green]GENERATE[/green] {'#' * section.level} {section.title}")
                console.print(f"    [dim]{chart_str}[/dim]")

        console.print()
        console.print(f"[dim]Sections to update: {existing_count}[/dim]")
        console.print(f"[dim]Sections to generate: {missing_count}[/dim]")
        console.print(f"[dim]Model: {model}[/dim]")
        console.print(f"[dim]Thinking: {thinking}[/dim]")
        if extra_notes:
            console.print(f"[dim]Revision notes: {len(extra_notes)} chars[/dim]")
    else:
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                output_dir=output_root,
            )

        section_count = len(orchestrator.sections)
        console.print(f"[bold]Processing {section_count} sections...[/bold]")

        def section_progress(message: str) -> None:
            if message.startswith("Updating section") or message.startswith("Generating section"):
                console.print(f"[bold blue]→ {message}[/bold blue]")
            elif message.startswith("LLM response"):
                console.print(f"  [green]✓[/green] {message}")
            elif verbose:
                console.print(f"  [dim]{message}[/dim]")

        orchestrator._on_progress = section_progress
        report_content, total_usage, action_map = orchestrator.update_report(extra_notes)

        report_path = output_root / "report.md"
        report_path.write_text(report_content)
        console.print(f"[green]✓[/green] Report written to {report_path}")

        figures_dir = output_root / "figures"
        if figures_dir.exists():
            figure_count = len(list(figures_dir.glob("*.png")))
            console.print(f"[green]✓[/green] {figure_count} figure(s) in {figures_dir}")

        sections_dir = output_root / "_sections"
        if sections_dir.exists():
            section_file_count = len(list(sections_dir.glob("*.md")))
            console.print(f"[green]✓[/green] {section_file_count} section file(s) in {sections_dir}")

        generated = sum(1 for v in action_map.values() if v == "generated")
        updated = sum(1 for v in action_map.values() if v == "updated")
        console.print()
        console.print(f"[dim]Generated: {generated} sections, Updated: {updated} sections[/dim]")
        console.print(f"[bold cyan]Total Cost: ${total_usage.cost_usd:.2f}[/bold cyan]")
        console.print(f"[dim]Tokens: {total_usage.input_tokens:,} in / {total_usage.output_tokens:,} out[/dim]")
        if total_usage.reasoning_tokens > 0:
            console.print(f"[dim]Reasoning tokens: {total_usage.reasoning_tokens:,}[/dim]")

        try:
            quip = orchestrator.generate_cost_quip(total_usage.cost_usd, section_count)
            console.print()
            console.print(f"[italic yellow]{quip}[/italic yellow]")
        except Exception:
            pass


@app.command("inspect-charts")
def inspect_charts(
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    format: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
) -> None:
    """List available charts."""
    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    catalog = DataCatalog(data_root)
    charts = catalog.list_charts(category=category)

    if format == OutputFormat.json:
        output = []
        for chart in charts:
            output.append({
                "id": chart.id,
                "category": chart.category,
                "title": chart.title,
                "units": chart.units,
                "dimensions": chart.dimensions,
                "has_csv": chart.path_csv is not None,
                "has_png": chart.path_png is not None,
                "has_json": chart.path_json is not None,
            })
        console.print(json.dumps(output, indent=2))
    else:
        if not charts:
            console.print("[dim]No charts found[/dim]")
            return

        table = Table(title=f"Charts in {data_root}" + (f" (category: {category})" if category else ""))
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Title")
        table.add_column("Units")
        table.add_column("Files", style="dim")

        for chart in charts:
            files = []
            if chart.path_csv:
                files.append("csv")
            if chart.path_png:
                files.append("png")
            if chart.path_json:
                files.append("json")

            table.add_row(
                chart.id,
                chart.category,
                chart.title,
                chart.units or "-",
                ", ".join(files),
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(charts)} charts[/dim]")


@app.command("inspect-sections")
def inspect_sections(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Optional[Path] = typer.Option(None, "--data-root", "-d", help="Path to data directory"),
    show_charts: bool = typer.Option(False, "--show-charts", help="Show mapped charts per section"),
) -> None:
    """Show section structure and mappings."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    sections = parse_outline(outline)

    catalog = None
    mapper = None

    if show_charts and data_root:
        if not data_root.exists():
            console.print(f"[yellow]Warning:[/yellow] Data root not found: {data_root}")
        else:
            from .section_mapper import SectionMapper

            catalog = DataCatalog(data_root)
            mapping_path = data_root / "section_chart_map.json"
            if not mapping_path.exists():
                mapping_path = outline.parent / "section_chart_map.json"
            mapper = SectionMapper(catalog, mapping_path if mapping_path.exists() else None)

    table = Table(title=f"Sections in {outline}")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Level", justify="center")
    table.add_column("Parent", style="dim")
    table.add_column("Instructions", max_width=40, overflow="ellipsis")

    if show_charts:
        table.add_column("Charts", style="green")

    for section in sections:
        row = [
            section.id,
            section.title,
            str(section.level),
            section.parent_id or "-",
            section.instructions[:80] + "..." if len(section.instructions) > 80 else section.instructions or "-",
        ]

        if show_charts:
            if mapper:
                charts = mapper.get_charts_for_section_obj(section)
                row.append(", ".join(c.id for c in charts[:3]) + ("..." if len(charts) > 3 else "") or "-")
            else:
                row.append("-")

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(sections)} sections[/dim]")


@app.command("run-eval")
def run_eval(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to reviewed report markdown"),
    run_id: str = typer.Option(..., "--run-id", "-r", help="Unique identifier for this evaluation run"),
    output: Path = typer.Option(..., "--output", "-O", help="Output JSON file path"),
) -> None:
    """Run evaluation on reviewed report."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    sections = parse_outline(outline)

    eval_results = {
        "run_id": run_id,
        "outline_path": str(outline),
        "sections": [],
        "summary": {
            "total_sections": 0,
            "rated_sections": 0,
            "average_ratings": {},
        },
    }

    rating_totals: dict[str, list[int]] = {}

    for section in sections:
        section_result = {
            "id": section.id,
            "title": section.title,
            "level": section.level,
            "has_review": bool(section.review_comments),
            "ratings": section.review_ratings,
            "notes": section.review_notes,
        }
        eval_results["sections"].append(section_result)

        if section.review_ratings:
            eval_results["summary"]["rated_sections"] += 1
            for key, value in section.review_ratings.items():
                if key not in rating_totals:
                    rating_totals[key] = []
                rating_totals[key].append(value)

    eval_results["summary"]["total_sections"] = len(sections)

    for key, values in rating_totals.items():
        eval_results["summary"]["average_ratings"][key] = round(sum(values) / len(values), 2)

    output.write_text(json.dumps(eval_results, indent=2))
    console.print(f"[green]✓[/green] Evaluation results written to {output}")

    table = Table(title="Evaluation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Sections", str(eval_results["summary"]["total_sections"]))
    table.add_row("Rated Sections", str(eval_results["summary"]["rated_sections"]))

    for key, avg in eval_results["summary"]["average_ratings"].items():
        table.add_row(f"Avg {key}", f"{avg:.2f}")

    console.print(table)


if __name__ == "__main__":
    app()
