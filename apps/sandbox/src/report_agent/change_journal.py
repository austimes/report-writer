"""
Change journal system for tracking CLI operations with full traceability.

Logs every CLI operation BEFORE git commit, so commits can reference
journal entries and we maintain rich operation history.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid


@dataclass
class JournalEntry:
    """A single journal entry recording a CLI operation."""

    id: str
    timestamp: str
    command: str
    arguments: dict
    model: str | None = None
    thinking_level: str | None = None
    cost_usd: float | None = None
    sections_affected: list[str] = field(default_factory=list)
    review_notes: str | None = None
    review_author: str | None = None
    success: bool = True
    error_message: str | None = None
    duration_seconds: float | None = None


def get_journal_dir(output_root: Path) -> Path:
    """Returns the journal directory, creating if needed."""
    journal_dir = output_root / "_report_log"
    journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir


def create_entry(
    command: str,
    arguments: dict,
    *,
    model: str | None = None,
    thinking_level: str | None = None,
    sections_affected: list[str] | None = None,
    review_notes: str | None = None,
    review_author: str | None = None,
) -> JournalEntry:
    """Create a new journal entry with generated UUID and timestamp."""
    return JournalEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        command=command,
        arguments=arguments,
        model=model,
        thinking_level=thinking_level,
        sections_affected=sections_affected or [],
        review_notes=review_notes,
        review_author=review_author,
    )


def save_entry(output_root: Path, entry: JournalEntry) -> Path:
    """Save entry to journal directory. Returns the path."""
    journal_dir = get_journal_dir(output_root)

    ts = datetime.fromisoformat(entry.timestamp)
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    short_id = entry.id[:8]
    filename = f"{ts_str}_{entry.command}_{short_id}.json"

    path = journal_dir / filename
    path.write_text(json.dumps(asdict(entry), indent=2))
    return path


def update_entry(
    output_root: Path,
    entry: JournalEntry,
    success: bool,
    error_message: str | None = None,
    cost_usd: float | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Update an existing entry with completion status."""
    entry.success = success
    entry.error_message = error_message
    if cost_usd is not None:
        entry.cost_usd = cost_usd
    if duration_seconds is not None:
        entry.duration_seconds = duration_seconds

    save_entry(output_root, entry)


def load_entry(path: Path) -> JournalEntry:
    """Load entry from JSON file."""
    data = json.loads(path.read_text())
    return JournalEntry(**data)


def list_entries(output_root: Path, limit: int = 50) -> list[JournalEntry]:
    """List recent entries, most recent first."""
    journal_dir = get_journal_dir(output_root)

    json_files = sorted(journal_dir.glob("*.json"), reverse=True)

    entries = []
    for path in json_files[:limit]:
        try:
            entries.append(load_entry(path))
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    return entries


def format_entry_for_commit(entry: JournalEntry) -> str:
    """Format entry into a readable commit message body."""
    lines = []

    ts = datetime.fromisoformat(entry.timestamp)
    lines.append(f"Command: {entry.command}")
    lines.append(f"Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Journal ID: {entry.id}")

    if entry.sections_affected:
        lines.append(f"Sections: {', '.join(entry.sections_affected)}")

    if entry.model:
        lines.append(f"Model: {entry.model}")

    if entry.thinking_level:
        lines.append(f"Thinking: {entry.thinking_level}")

    if entry.review_notes:
        notes = entry.review_notes
        if len(notes) > 200:
            notes = notes[:197] + "..."
        lines.append(f"Review notes: {notes}")

    if entry.review_author:
        lines.append(f"Reviewer: {entry.review_author}")

    if entry.cost_usd is not None:
        lines.append(f"Cost: ${entry.cost_usd:.4f}")

    if entry.duration_seconds is not None:
        lines.append(f"Duration: {entry.duration_seconds:.1f}s")

    if not entry.success:
        lines.append(f"Status: FAILED")
        if entry.error_message:
            lines.append(f"Error: {entry.error_message}")

    return "\n".join(lines)
