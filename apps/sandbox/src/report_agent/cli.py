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


@app.command("generate-section")
def generate_section(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    section: str = typer.Option(..., "--section", "-s", help="Section ID to generate"),
    output: Path = typer.Option(..., "--output", "-O", help="Output file path"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level: low, medium, high"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """Generate a single section draft."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    output_dir = output.parent

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
            output_dir=output_dir,
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
                output_dir=output_dir,
            )

    section_obj = orchestrator.get_section(section)
    if section_obj is None:
        console.print(f"[red]Error:[/red] Section '{section}' not found")
        available = [s.id for s in orchestrator.sections]
        console.print(f"[dim]Available sections: {', '.join(available)}[/dim]")
        raise typer.Exit(1)

    if dry_run:
        result = orchestrator.generate_section(section)
        console.print("[bold]Prompt that would be sent:[/bold]")
        console.print()
        console.print(result.prompt)
        console.print()
        console.print(f"[dim]Charts: {', '.join(result.charts_used) or 'none'}[/dim]")
        console.print(f"[dim]Model: {model}[/dim]")
    else:
        with console.status(f"[bold blue]Generating section '{section}'...[/bold blue]", spinner="dots") as status:
            orchestrator._on_progress = _make_progress_callback(status)
            result = orchestrator.generate_section(section)

        output.write_text(result.content)
        console.print(f"[green]✓[/green] Generated section written to {output}")
        console.print(f"[dim]Charts used: {', '.join(result.charts_used) or 'none'}[/dim]")
        console.print(f"[bold cyan]Cost: ${result.usage.cost_usd:.4f}[/bold cyan] ({result.usage.input_tokens:,} in / {result.usage.output_tokens:,} out tokens)")


@app.command("generate-report")
def generate_report(
    outline: Path = typer.Option(..., "--outline", "-o", help="Path to report outline markdown"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    output: Path = typer.Option(..., "--output", "-O", help="Output file path"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level: low, medium, high"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """Generate full report (all sections)."""
    if not outline.exists():
        console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        raise typer.Exit(1)

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    output_dir = output.parent

    if dry_run:
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            model=model,
            thinking_level=thinking,
            dry_run=dry_run,
            on_progress=_make_progress_callback() if verbose else None,
            output_dir=output_dir,
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
        console.print(f"[dim]Output: {output}[/dim]")
        console.print(f"[dim]Figures: {output_dir / 'figures'}[/dim]")
    else:
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                output_dir=output_dir,
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

        output.write_text(report_content)
        console.print(f"[green]✓[/green] Report written to {output}")
        figures_dir = output_dir / "figures"
        if figures_dir.exists():
            figure_count = len(list(figures_dir.glob("*.png")))
            console.print(f"[green]✓[/green] {figure_count} figure(s) copied to {figures_dir}")
        sections_dir = output_dir / "_sections"
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
