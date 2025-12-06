"""CLI for the Report Agent."""

import json
import re
import shutil
from enum import Enum
from pathlib import Path
from typing import Optional

import markdown
import typer
from rich.console import Console
from rich.table import Table

from .data_catalog import DataCatalog
from .orchestrator import DEFAULT_MODEL, DEFAULT_THINKING_LEVEL, ReportOrchestrator, UsageCost
from .outline_parser import parse_outline
from .git_integration import (
    require_executable,
    ensure_report_project,
    init_repo,
    auto_commit,
    REPORT_META_FILENAME,
    GITHUB_ORG,
)
from .change_journal import create_entry, save_entry, update_entry, format_entry_for_commit
from .editor_log import update_readme_with_note

OUTLINE_FILENAME = "outline.md"


def get_outline_in_output(output_root: Path) -> Path | None:
    """Get outline path from output_root if it exists."""
    outline_path = output_root / OUTLINE_FILENAME
    return outline_path if outline_path.exists() else None


def resolve_outline(
    outline_arg: Path | None,
    output_root: Path,
    console: Console,
) -> Path | None:
    """Resolve outline path, preferring output_root copy over provided path.
    
    Returns the resolved path, or None if no outline found.
    Prints info message if using output_root outline.
    """
    output_outline = get_outline_in_output(output_root)
    
    if output_outline:
        if outline_arg and outline_arg.exists():
            console.print(f"[dim]Using outline from {output_root} (ignoring --outline)[/dim]")
        return output_outline
    
    if outline_arg and outline_arg.exists():
        return outline_arg
    
    return None


def copy_outline_to_output(outline: Path, output_root: Path) -> Path:
    """Copy outline to output_root, return the destination path."""
    output_root.mkdir(parents=True, exist_ok=True)
    dest = output_root / OUTLINE_FILENAME
    shutil.copy2(outline, dest)
    return dest


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


@app.command("init-report")
def init_report(
    report_name: str = typer.Option(..., "--report-name", "-n", help="Human-readable report name"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Directory to create/use as project root"),
    private: bool = typer.Option(True, "--private/--public", help="GitHub repo visibility"),
    force: bool = typer.Option(False, "--force", "-f", help="Allow using non-empty directory"),
) -> None:
    """Initialize a new report project with git and GitHub integration."""
    try:
        require_executable("git")
        require_executable("gh")
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    
    output_root = output_root.resolve()
    
    # Check if already initialized
    if output_root.exists() and (output_root / ".git").exists() and (output_root / REPORT_META_FILENAME).exists():
        console.print(f"[green]✓[/green] Report project already initialized in {output_root}")
        return
    
    # Check if directory is non-empty without --force
    if output_root.exists() and any(output_root.iterdir()) and not force:
        console.print(f"[red]Error:[/red] Directory is not empty: {output_root}")
        console.print("[dim]Use --force to allow using a non-empty directory[/dim]")
        raise typer.Exit(1)
    
    try:
        metadata = init_repo(output_root, report_name, private)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    
    # Create journal entry for init operation
    entry = create_entry(
        command="init-report",
        arguments={
            "report_name": report_name,
            "output_root": str(output_root),
            "private": private,
        },
    )
    save_entry(output_root, entry)
    
    visibility = "private" if private else "public"
    console.print(f"[green]✓[/green] Initialized report project in {output_root}")
    console.print(f"[green]✓[/green] Created GitHub repo {GITHUB_ORG}/{metadata['slug']} ({visibility})")
    console.print(f"[green]✓[/green] Pushed initial commit")


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


def _summarize_review_notes(notes: str | None, max_len: int = 300) -> str | None:
    """Truncate notes to max_len, adding '...' if truncated."""
    if not notes:
        return None
    notes = notes.strip()
    if not notes:
        return None
    if len(notes) <= max_len:
        return notes
    return notes[:max_len] + "..."


def _build_commit_message(command: str, meta: dict, **kwargs) -> str:
    """Build a structured commit message.
    
    Args:
        command: The command type (e.g., 'generate section', 'update report')
        meta: Report metadata dict containing 'name' key
        **kwargs: Additional fields to include in the body
    """
    lines = [command, ""]
    
    report_name = meta.get("name", "Unknown Report")
    lines.append(f"Report: {report_name}")
    
    review_notes = kwargs.pop("review_notes", None)
    review_author = kwargs.pop("review_author", None)
    
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, list):
            if value:
                lines.append(f"{key.replace('_', ' ').title()}: {', '.join(value)}")
        elif isinstance(value, float):
            lines.append(f"{key.replace('_', ' ').title()}: ${value:.4f}")
        else:
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
    
    if review_notes or review_author:
        lines.append("")
        lines.append("Review feedback addressed:")
        if review_author:
            lines.append(f"Reviewer: {review_author}")
        if review_notes:
            summarized = _summarize_review_notes(review_notes)
            if summarized:
                lines.append(summarized)
    
    return "\n".join(lines)


def _build_commit_message_for_generate_section(
    meta: dict,
    section_id: str,
    section_title: str,
    model: str,
    cost_usd: float,
) -> str:
    """Build commit message for generate-section command."""
    return _build_commit_message(
        f"feat: generate section {section_id} - {section_title}",
        meta,
        model=model,
        cost=cost_usd,
    )


def _build_commit_message_for_update_section(
    meta: dict,
    section_id: str,
    section_title: str,
    model: str,
    cost_usd: float,
    review_notes: str | None,
    review_author: str | None,
) -> str:
    """Build commit message for update-section command."""
    return _build_commit_message(
        f"chore: update section {section_id} - {section_title}",
        meta,
        model=model,
        cost=cost_usd,
        review_notes=review_notes,
        review_author=review_author,
    )


def _build_commit_message_for_generate_report(
    meta: dict,
    section_count: int,
    model: str,
    cost_usd: float,
) -> str:
    """Build commit message for generate-report command."""
    return _build_commit_message(
        f"feat: generate full report ({section_count} sections)",
        meta,
        model=model,
        total_cost=cost_usd,
    )


def _build_commit_message_for_update_report(
    meta: dict,
    updated_sections: list[str],
    generated_sections: list[str],
    model: str,
    cost_usd: float,
    review_notes: str | None,
) -> str:
    """Build commit message for update-report command."""
    return _build_commit_message(
        "chore: update report sections",
        meta,
        sections_updated=updated_sections,
        sections_generated=generated_sections,
        model=model,
        total_cost=cost_usd,
        review_notes=review_notes,
    )


def _build_commit_message_for_integrate_report(
    meta: dict,
    sections_modified: list[str],
    duplicates_removed: int,
    cross_refs_added: int,
    cost_usd: float,
) -> str:
    """Build commit message for integrate-report command."""
    return _build_commit_message(
        "chore: integrate report",
        meta,
        sections_modified=sections_modified,
        duplicates_removed=duplicates_removed,
        cross_references_added=cross_refs_added,
        cost=cost_usd,
    )


@app.command("generate-section")
def generate_section(
    outline: Optional[Path] = typer.Option(None, "--outline", "-o", help="Path to report outline markdown (optional if outline.md exists in output-root)"),
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
    import time
    
    # Validate this is an initialized report project (skip for dry_run)
    meta = None
    if not dry_run:
        try:
            meta = ensure_report_project(output_root)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    resolved_outline = resolve_outline(outline, output_root, console)
    if resolved_outline is None:
        if outline:
            console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        else:
            console.print(f"[red]Error:[/red] No outline found. Provide --outline or ensure {OUTLINE_FILENAME} exists in output-root.")
        raise typer.Exit(1)
    outline = resolved_outline

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
        raise typer.Exit(1)

    if get_outline_in_output(output_root) is None:
        copy_outline_to_output(outline, output_root)
        console.print(f"[dim]Copied outline to {output_root / OUTLINE_FILENAME}[/dim]")

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
        start_time = time.time()
        
        journal_entry = create_entry(
            command="generate-section",
            arguments={"section": section, "model": model, "thinking": thinking, "force": force},
            model=model,
            thinking_level=thinking,
            sections_affected=[section],
        )
        save_entry(output_root, journal_entry)
        
        try:
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
            
            # Update journal with results
            duration = time.time() - start_time
            update_entry(output_root, journal_entry, success=True, cost_usd=result.usage.cost_usd, duration_seconds=duration)
            
            # Build commit message and auto-commit
            commit_msg = _build_commit_message_for_generate_section(
                meta=meta,
                section_id=section_obj.id,
                section_title=section_obj.title,
                model=model,
                cost_usd=result.usage.cost_usd,
            )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print("[green]✓[/green] Changes committed and pushed to GitHub")
            except RuntimeError as e:
                console.print(f"[red]Error:[/red] Git commit failed: {e}")
                raise typer.Exit(1)
        except Exception as e:
            update_entry(output_root, journal_entry, success=False, error_message=str(e))
            raise


@app.command("update-section")
def update_section(
    outline: Optional[Path] = typer.Option(None, "--outline", "-o", help="Path to report outline markdown (optional if outline.md exists in output-root)"),
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
    import time
    
    # Validate this is an initialized report project (skip for dry_run)
    meta = None
    if not dry_run:
        try:
            meta = ensure_report_project(output_root)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    if not output_root.exists():
        console.print(f"[red]Error:[/red] Output root not found: {output_root}")
        console.print("[dim]Run generate-section or generate-report first.[/dim]")
        raise typer.Exit(1)
    
    resolved_outline = resolve_outline(outline, output_root, console)
    if resolved_outline is None:
        if outline:
            console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        else:
            console.print(f"[red]Error:[/red] No outline found. Provide --outline or ensure {OUTLINE_FILENAME} exists in output-root.")
        raise typer.Exit(1)
    outline = resolved_outline

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
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
        start_time = time.time()
        
        # Load extra revision notes for journal
        extra_notes_text = None
        if revision_notes and revision_notes.exists():
            extra_notes_text = revision_notes.read_text()
        
        journal_entry = create_entry(
            command="update-section",
            arguments={"section": section, "model": model, "thinking": thinking},
            model=model,
            thinking_level=thinking,
            sections_affected=[section],
            review_notes=extra_notes_text,
        )
        save_entry(output_root, journal_entry)
        
        try:
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
            
            # Update journal with results
            duration = time.time() - start_time
            update_entry(output_root, journal_entry, success=True, cost_usd=result.usage.cost_usd, duration_seconds=duration)
            
            # Generate editorial note for README
            note = update_readme_with_note(
                output_root,
                journal_entry,
                extra_context={
                    "section_title": section_obj.title,
                    "charts_used": [c.id for c in charts],
                    "charts_referenced": charts_referenced,
                    "review_author": section_obj.review_author,
                },
            )
            if note:
                console.print(f"[green]✓[/green] Updated README editorial log")
            
            # Build commit message with review feedback context
            commit_msg = _build_commit_message_for_update_section(
                meta=meta,
                section_id=section_obj.id,
                section_title=section_obj.title,
                model=model,
                cost_usd=result.usage.cost_usd,
                review_notes=section_obj.review_notes or extra_notes,
                review_author=section_obj.review_author,
            )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print("[green]✓[/green] Changes committed and pushed to GitHub")
            except RuntimeError as e:
                console.print(f"[red]Error:[/red] Git commit failed: {e}")
                raise typer.Exit(1)
        except Exception as e:
            update_entry(output_root, journal_entry, success=False, error_message=str(e))
            raise


@app.command("generate-report")
def generate_report(
    outline: Optional[Path] = typer.Option(None, "--outline", "-o", help="Path to report outline markdown (optional if outline.md exists in output-root)"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing sections"),
    integrate: bool = typer.Option(False, "--integrate", "-I", help="Run integration pass after generation"),
    max_change_ratio: float = typer.Option(0.3, "--max-change", help="Max change ratio for integration (with --integrate)"),
) -> None:
    """Generate full report (all sections)."""
    import time
    
    # Validate this is an initialized report project (skip for dry_run)
    meta = None
    if not dry_run:
        try:
            meta = ensure_report_project(output_root)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    resolved_outline = resolve_outline(outline, output_root, console)
    if resolved_outline is None:
        if outline:
            console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        else:
            console.print(f"[red]Error:[/red] No outline found. Provide --outline or ensure {OUTLINE_FILENAME} exists in output-root.")
        raise typer.Exit(1)
    outline = resolved_outline

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

    if get_outline_in_output(output_root) is None:
        copy_outline_to_output(outline, output_root)
        console.print(f"[dim]Copied outline to {output_root / OUTLINE_FILENAME}[/dim]")

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
        start_time = time.time()
        
        def on_section_complete(result, action: str) -> None:
            """Commit and push after each section is generated."""
            commit_msg = _build_commit_message_for_generate_section(
                meta=meta,
                section_id=result.section_id,
                section_title=result.section_title,
                model=model,
                cost_usd=result.usage.cost_usd,
            )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print(f"  [green]✓[/green] Committed section {result.section_id}")
            except RuntimeError as e:
                console.print(f"  [yellow]Warning:[/yellow] Git commit failed for {result.section_id}: {e}")
        
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                on_section_complete=on_section_complete,
                output_dir=output_root,
            )

        section_count = len(orchestrator.sections)
        console.print(f"[bold]Generating report with {section_count} sections...[/bold]")

        # Get section IDs for journal
        section_ids = [s.id for s in orchestrator.sections]
        
        journal_entry = create_entry(
            command="generate-report",
            arguments={"model": model, "thinking": thinking, "force": force, "integrate": integrate},
            model=model,
            thinking_level=thinking,
            sections_affected=section_ids,
        )
        save_entry(output_root, journal_entry)

        try:
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

            if integrate:
                console.print()
                console.print("[bold]Running integration pass...[/bold]")
                
                result = orchestrator.integrate_report(max_change_ratio=max_change_ratio)
                
                console.print(f"[green]✓[/green] Integration complete")
                console.print(f"  Sections modified: {len(result.sections_modified)}")
                console.print(f"  Duplicates removed: {result.duplicates_removed}")
                console.print(f"  Cross-references added: {result.cross_refs_added}")
                console.print(f"  Integration cost: ${result.usage.cost_usd:.4f}")
                
                if not result.validation_passed:
                    console.print(f"[yellow]Warning:[/yellow] {result.validation_message}")
                
                total_usage = total_usage + result.usage

            # Update journal with results
            duration = time.time() - start_time
            update_entry(output_root, journal_entry, success=True, cost_usd=total_usage.cost_usd, duration_seconds=duration)
            
            # Generate editorial note for README
            figures_dir = output_root / "figures"
            figure_count = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0
            note = update_readme_with_note(
                output_root,
                journal_entry,
                extra_context={
                    "total_sections": section_count,
                    "sections_summary": ", ".join(f"{s.id}" for s in orchestrator.sections[:5]),
                    "figures_copied": figure_count,
                    "integrate_requested": integrate,
                },
            )
            if note:
                console.print(f"[green]✓[/green] Updated README editorial log")
            
            # Final commit for report.md assembly and journal update
            commit_msg = _build_commit_message(
                f"chore: finalize generate-report ({section_count} sections)",
                meta,
                model=model,
                cost=total_usage.cost_usd,
            )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print("[green]✓[/green] Report finalized and pushed to GitHub")
            except RuntimeError as e:
                console.print(f"[red]Error:[/red] Git commit failed: {e}")
                raise typer.Exit(1)

            try:
                quip = orchestrator.generate_cost_quip(total_usage.cost_usd, section_count)
                console.print()
                console.print(f"[italic yellow]{quip}[/italic yellow]")
            except Exception:
                pass
        except Exception as e:
            if 'journal_entry' in locals():
                update_entry(output_root, journal_entry, success=False, error_message=str(e))
            raise


@app.command("update-report")
def update_report(
    outline: Optional[Path] = typer.Option(None, "--outline", "-o", help="Path to report outline markdown (optional if outline.md exists in output-root)"),
    data_root: Path = typer.Option(..., "--data-root", "-d", help="Path to data directory"),
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    revision_notes: Optional[Path] = typer.Option(None, "--revision-notes", "-R", help="Additional revision instructions (markdown file)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sent without calling LLM"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    integrate: bool = typer.Option(False, "--integrate", "-I", help="Run integration pass after update"),
    max_change_ratio: float = typer.Option(0.3, "--max-change", help="Max change ratio for integration (with --integrate)"),
) -> None:
    """Update existing sections and generate missing ones.
    
    For each section in the outline:
    - If section file exists: update it based on review feedback
    - If section file doesn't exist: generate fresh content
    
    This is useful when you have partially generated a report and want to
    continue generation while also incorporating review feedback on existing sections.
    """
    import time
    
    # Validate this is an initialized report project (skip for dry_run)
    meta = None
    if not dry_run:
        try:
            meta = ensure_report_project(output_root)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    if not output_root.exists():
        console.print(f"[red]Error:[/red] Output root not found: {output_root}")
        console.print("[dim]Run generate-section or generate-report first to create initial content.[/dim]")
        raise typer.Exit(1)
    
    resolved_outline = resolve_outline(outline, output_root, console)
    if resolved_outline is None:
        if outline:
            console.print(f"[red]Error:[/red] Outline file not found: {outline}")
        else:
            console.print(f"[red]Error:[/red] No outline found. Provide --outline or ensure {OUTLINE_FILENAME} exists in output-root.")
        raise typer.Exit(1)
    outline = resolved_outline

    if not data_root.exists():
        console.print(f"[red]Error:[/red] Data root not found: {data_root}")
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
        start_time = time.time()
        
        def on_section_complete(result, action: str) -> None:
            """Commit and push after each section is processed."""
            section_obj = orchestrator.get_section(result.section_id)
            
            if action == "updated":
                commit_msg = _build_commit_message_for_update_section(
                    meta=meta,
                    section_id=result.section_id,
                    section_title=result.section_title,
                    model=model,
                    cost_usd=result.usage.cost_usd,
                    review_notes=(section_obj.review_notes if section_obj else None) or extra_notes,
                    review_author=section_obj.review_author if section_obj else None,
                )
            else:
                commit_msg = _build_commit_message_for_generate_section(
                    meta=meta,
                    section_id=result.section_id,
                    section_title=result.section_title,
                    model=model,
                    cost_usd=result.usage.cost_usd,
                )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print(f"  [green]✓[/green] Committed section {result.section_id} ({action})")
            except RuntimeError as e:
                console.print(f"  [yellow]Warning:[/yellow] Git commit failed for {result.section_id}: {e}")
        
        with console.status("[bold blue]Initializing...[/bold blue]", spinner="dots") as status:
            orchestrator = ReportOrchestrator(
                outline_path=outline,
                data_root=data_root,
                model=model,
                thinking_level=thinking,
                dry_run=dry_run,
                on_progress=_make_progress_callback(status),
                on_section_complete=on_section_complete,
                output_dir=output_root,
            )

        section_count = len(orchestrator.sections)
        console.print(f"[bold]Processing {section_count} sections...[/bold]")

        # Get section IDs for journal
        section_ids = [s.id for s in orchestrator.sections]
        
        journal_entry = create_entry(
            command="update-report",
            arguments={"model": model, "thinking": thinking, "integrate": integrate},
            model=model,
            thinking_level=thinking,
            sections_affected=section_ids,
            review_notes=extra_notes[:200] if extra_notes else None,
        )
        save_entry(output_root, journal_entry)

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

        if integrate:
            console.print()
            console.print("[bold]Running integration pass...[/bold]")
            
            result = orchestrator.integrate_report(max_change_ratio=max_change_ratio)
            
            console.print(f"[green]✓[/green] Integration complete")
            console.print(f"  Sections modified: {len(result.sections_modified)}")
            console.print(f"  Duplicates removed: {result.duplicates_removed}")
            console.print(f"  Cross-references added: {result.cross_refs_added}")
            console.print(f"  Integration cost: ${result.usage.cost_usd:.4f}")
            
            if not result.validation_passed:
                console.print(f"[yellow]Warning:[/yellow] {result.validation_message}")
            
            total_usage = total_usage + result.usage

        # Update journal with results
        duration = time.time() - start_time
        update_entry(output_root, journal_entry, success=True, cost_usd=total_usage.cost_usd, duration_seconds=duration)
        
        # Generate editorial note for README
        note = update_readme_with_note(
            output_root,
            journal_entry,
            extra_context={
                "sections_updated": [sid for sid, act in action_map.items() if act == "updated"][:5],
                "sections_generated": [sid for sid, act in action_map.items() if act == "generated"][:5],
                "count_updated": updated,
                "count_generated": generated,
                "integrate_requested": integrate,
            },
        )
        if note:
            console.print(f"[green]✓[/green] Updated README editorial log")
        
        # Final commit for report.md assembly
        commit_msg = _build_commit_message(
            f"chore: finalize update-report ({generated} generated, {updated} updated)",
            meta,
            model=model,
            cost=total_usage.cost_usd,
        )
        
        try:
            auto_commit(output_root, commit_msg)
            console.print("[green]✓[/green] Report finalized and pushed to GitHub")
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] Git commit failed: {e}")
            raise typer.Exit(1)

        try:
            quip = orchestrator.generate_cost_quip(total_usage.cost_usd, section_count)
            console.print()
            console.print(f"[italic yellow]{quip}[/italic yellow]")
        except Exception:
            pass


@app.command("integrate-report")
def integrate_report(
    output_root: Path = typer.Option(..., "--output-root", "-O", help="Output project directory (must contain report.md)"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="LLM model to use"),
    thinking: str = typer.Option(DEFAULT_THINKING_LEVEL, "--thinking", "-t", help="Thinking level"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be integrated without calling LLM"),
    max_change: float = typer.Option(0.3, "--max-change", help="Max allowed content change ratio 0.0-1.0"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
) -> None:
    """Integrate report to remove duplicates and add cross-references.

    This command runs a holistic integration pass over the assembled report.md:
    - Identifies duplicate figures/charts (same image URLs)
    - Assigns consistent figure numbering (F1, F2, ...)
    - Replaces duplicates with cross-references
    - Adds INTEGRATION_HINTS comments for future per-section updates

    Versions are stored in _integration/ for visual diffing (run001_before.md, run001_after.md).
    
    Run this after generate-report or update-report to make the report cohesive.
    """
    import time
    from .integrator_simple import SimpleReportIntegrator
    
    # Validate this is an initialized report project (skip for dry_run)
    meta = None
    if not dry_run:
        try:
            meta = ensure_report_project(output_root)
        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    # Validate output directory exists
    if not output_root.exists():
        console.print(f"[red]Error:[/red] Output root not found: {output_root}")
        console.print("[dim]Run generate-report or update-report first.[/dim]")
        raise typer.Exit(1)
    
    # Validate report.md exists
    report_path = output_root / "report.md"
    if not report_path.exists():
        console.print(f"[red]Error:[/red] report.md not found in {output_root}")
        console.print("[dim]Run generate-report or update-report first to create report.md.[/dim]")
        raise typer.Exit(1)
    
    # Read the report
    console.print(f"[bold]Reading report from {report_path}[/bold]")
    report_content = report_path.read_text()
    
    # Create progress callback for verbose logging
    def progress_callback(message: str) -> None:
        if verbose:
            console.print(f"  [dim]→ {message}[/dim]")
        else:
            # Even in non-verbose mode, show key milestones
            key_phrases = ["Calling", "LLM response", "Validating", "Saving"]
            if any(phrase in message for phrase in key_phrases):
                console.print(f"  [dim]{message}[/dim]")
    
    # Analyze report content
    word_count = len(report_content.split())
    section_count = report_content.count("<!-- BEGIN SECTION:")
    figure_count = len(re.findall(r'!\[.*?\]\(.*?\)', report_content))
    
    console.print()
    console.print("[bold cyan]Report Analysis:[/bold cyan]")
    console.print(f"  Sections: {section_count}")
    console.print(f"  Words: ~{word_count:,}")
    console.print(f"  Figures: {figure_count}")
    console.print()
    
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow] - no changes will be made")
        console.print()
        console.print(f"[dim]Would use model: {model}[/dim]")
        console.print(f"[dim]Thinking level: {thinking}[/dim]")
        console.print(f"[dim]Max change ratio: {max_change:.0%}[/dim]")
        
        # Check for potential duplicates by image URL
        image_urls = re.findall(r'!\[.*?\]\((.*?)\)', report_content)
        url_counts: dict[str, int] = {}
        for url in image_urls:
            url_counts[url] = url_counts.get(url, 0) + 1
        
        duplicates = [(url, count) for url, count in url_counts.items() if count > 1]
        if duplicates:
            console.print()
            console.print("[bold cyan]Potential Duplicate Figures:[/bold cyan]")
            for url, count in sorted(duplicates, key=lambda x: -x[1]):
                console.print(f"  [yellow]{url}[/yellow] appears {count} times")
        else:
            console.print()
            console.print("[dim]No duplicate figure URLs detected.[/dim]")
        
        return
    
    # Create journal entry before integration
    start_time = time.time()
    
    journal_entry = create_entry(
        command="integrate-report",
        arguments={"model": model, "thinking": thinking, "max_change": max_change},
        model=model,
        thinking_level=thinking,
    )
    save_entry(output_root, journal_entry)
    
    try:
        # Run integration
        console.print("[bold]Running integration pass...[/bold]")
        console.print()
        
        integrator = SimpleReportIntegrator(
            model=model,
            thinking_level=thinking,
            dry_run=False,
            on_progress=progress_callback,
            llm_log_dir=output_root / "_logs",
        )
        
        result = integrator.integrate(
            report_content=report_content,
            output_dir=output_root,
            max_change_ratio=max_change,
        )
        
        console.print()
        
        if result.validation_passed:
            # Write the integrated content back to report.md
            console.print(f"[bold]Writing integrated report to {report_path}[/bold]")
            report_path.write_text(result.integrated_content)
            
            console.print()
            console.print(f"[green]✓[/green] Integration complete (run {result.run_id})")
            console.print()
            console.print("[bold cyan]Results:[/bold cyan]")
            console.print(f"  Sections modified: {len(result.sections_modified)}")
            if result.sections_modified:
                for sid in result.sections_modified:
                    console.print(f"    [cyan]• {sid}[/cyan]")
            console.print(f"  Duplicates removed: {result.duplicates_removed}")
            console.print(f"  Cross-references added: {result.cross_refs_added}")
            console.print()
            console.print("[bold cyan]Snapshots:[/bold cyan]")
            if result.before_path:
                console.print(f"  Before: {result.before_path.relative_to(output_root)}")
            if result.after_path:
                console.print(f"  After:  {result.after_path.relative_to(output_root)}")
            console.print(f"  [dim]Use 'diff {result.before_path} {result.after_path}' to see changes[/dim]")
            
            # Update journal with results
            duration = time.time() - start_time
            update_entry(
                output_root, 
                journal_entry, 
                success=True, 
                cost_usd=result.usage.cost_usd, 
                duration_seconds=duration
            )
            # Update sections_affected in journal entry
            journal_entry.sections_affected = result.sections_modified
            save_entry(output_root, journal_entry)
            
            # Generate editorial note for README
            note = update_readme_with_note(
                output_root,
                journal_entry,
                extra_context={
                    "sections_modified": result.sections_modified[:5],
                    "duplicates_removed": result.duplicates_removed,
                    "cross_refs_added": result.cross_refs_added,
                    "validation_passed": result.validation_passed,
                },
            )
            if note:
                console.print(f"[green]✓[/green] Updated README editorial log")
            
            # Build commit message
            commit_msg = _build_commit_message_for_integrate_report(
                meta=meta,
                sections_modified=result.sections_modified,
                duplicates_removed=result.duplicates_removed,
                cross_refs_added=result.cross_refs_added,
                cost_usd=result.usage.cost_usd,
            )
            
            try:
                auto_commit(output_root, commit_msg)
                console.print("[green]✓[/green] Changes committed and pushed to GitHub")
            except RuntimeError as e:
                console.print(f"[red]Error:[/red] Git commit failed: {e}")
                raise typer.Exit(1)
        else:
            console.print(f"[yellow]⚠[/yellow] Integration validation failed")
            console.print(f"  [red]{result.validation_message}[/red]")
            console.print()
            console.print("[dim]The integrated content was NOT written to report.md.[/dim]")
            if result.before_path:
                console.print(f"[dim]Pre-integration snapshot saved at: {result.before_path}[/dim]")
            
            # Update journal with failure (no changes were made, so no commit)
            update_entry(output_root, journal_entry, success=False, error_message=result.validation_message)
        
        console.print()
        console.print(f"[bold cyan]Cost:[/bold cyan] ${result.usage.cost_usd:.4f}")
        console.print(f"  Input tokens:  {result.usage.input_tokens:,}")
        console.print(f"  Output tokens: {result.usage.output_tokens:,}")
        if result.usage.reasoning_tokens:
            console.print(f"  Reasoning:     {result.usage.reasoning_tokens:,}")
    except Exception as e:
        if 'journal_entry' in locals():
            update_entry(output_root, journal_entry, success=False, error_message=str(e))
        raise


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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            color: #1a1a1a;
        }}
        h1 {{ border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em 0;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f5f5f5;
        }}
        code {{
            background-color: #f5f5f5;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        pre {{
            background-color: #f5f5f5;
            padding: 1em;
            border-radius: 4px;
            overflow-x: auto;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 1em 0;
            padding-left: 1em;
            color: #666;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>"""


def _adjust_figure_paths(content: str, source_file: Path, output_root: Path) -> str:
    """Adjust figure paths in markdown to be relative to the HTML output location.
    
    For files in output_root (like report.md), figures/ paths work as-is.
    For files in _sections/, we need ../figures/ paths.
    """
    source_dir = source_file.parent.resolve()
    root_dir = output_root.resolve()
    
    # Determine if source is in a subdirectory
    try:
        rel_path = source_dir.relative_to(root_dir)
        depth = len(rel_path.parts)
    except ValueError:
        depth = 0
    
    prefix = "../" * depth if depth > 0 else ""
    
    # Replace figures/ paths with adjusted relative paths
    # Handle both markdown image syntax and raw paths
    patterns = [
        (r'!\[([^\]]*)\]\(figures/', rf'![\1]({prefix}figures/'),
        (r'src="figures/', f'src="{prefix}figures/'),
        (r"src='figures/", f"src='{prefix}figures/"),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    return content


def _strip_html_comments(content: str) -> str:
    """Remove HTML comments from markdown content."""
    return re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)


def _render_single_file(
    input_file: Path,
    output_root: Path,
    output_file: Path | None,
    strip_comments: bool,
    title: str | None,
) -> None:
    """Render a single markdown file to HTML."""
    content = input_file.read_text()
    
    if strip_comments:
        content = _strip_html_comments(content)
    
    content = _adjust_figure_paths(content, input_file, output_root)
    
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
    html_content = md.convert(content)
    
    if title is None:
        title = input_file.stem.replace("_", " ").replace("-", " ").title()
    
    final_html = HTML_TEMPLATE.format(title=title, content=html_content)
    
    if output_file is None:
        output_file = input_file.with_suffix(".html")
    
    output_file.write_text(final_html)
    return output_file


@app.command("render-html")
def render_html(
    input_path: Path = typer.Argument(..., help="Markdown file or output-root directory to render"),
    output_file: Path = typer.Option(None, "--output", "-o", help="Output HTML file (only for single file input)"),
    strip_comments: bool = typer.Option(True, "--strip-comments/--keep-comments", help="Remove HTML comments from output"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="HTML page title (only for single file input)"),
) -> None:
    """Render markdown to HTML with relative figure paths.
    
    If INPUT_PATH is a directory, renders report.md and all section files.
    If INPUT_PATH is a file, renders just that file.
    """
    if not input_path.exists():
        console.print(f"[red]Error:[/red] Path not found: {input_path}")
        raise typer.Exit(1)
    
    # Directory mode: render all markdown files
    if input_path.is_dir():
        output_root = input_path
        rendered_count = 0
        
        # Render main report.md
        report_md = output_root / "report.md"
        if report_md.exists():
            out = _render_single_file(report_md, output_root, None, strip_comments, "Report")
            console.print(f"[green]✓[/green] {out.name}")
            rendered_count += 1
        
        # Render section files
        sections_dir = output_root / "_sections"
        if sections_dir.exists():
            for section_file in sorted(sections_dir.glob("*.md")):
                out = _render_single_file(section_file, output_root, None, strip_comments, None)
                console.print(f"[green]✓[/green] _sections/{out.name}")
                rendered_count += 1
        
        if rendered_count == 0:
            console.print("[yellow]Warning:[/yellow] No markdown files found to render")
        else:
            console.print(f"\n[dim]Rendered {rendered_count} file(s)[/dim]")
    
    # File mode: render single file
    else:
        # Determine output root for relative path calculation
        if input_path.parent.name == "_sections":
            output_root = input_path.parent.parent
        else:
            output_root = input_path.parent
        
        out = _render_single_file(input_path, output_root, output_file, strip_comments, title)
        console.print(f"[green]✓[/green] Rendered HTML to {out}")


if __name__ == "__main__":
    app()
