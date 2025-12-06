"""Section meta comment parser and serializer.

This module provides utilities to parse and serialize REPORT_SECTION_META HTML
comments that carry integration hints between the integrator and section-level agents.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class IntegrationNote:
    """A note about an integration action taken on a section.
    
    Attributes:
        type: Type of integration action (e.g., 'removed_duplicate_figure', 'replaced_with_ref')
        semantic_key: Optional semantic key of the affected artifact
        reason: Optional explanation of why this action was taken
        replacement: Optional replacement info (e.g., {'type': 'figure_ref', 'id': 'F1'})
    """
    type: str
    semantic_key: str | None = None
    reason: str | None = None
    replacement: dict[str, Any] | None = None


@dataclass
class IntegrationHints:
    """Integration hints for a section.
    
    Attributes:
        avoid_figures: Semantic keys of figures NOT to recreate
        canonical_figures: List of canonical figure info dicts [{id, semantic_key, owner_section}]
        notes: List of IntegrationNote objects describing what was changed
    """
    avoid_figures: list[str] = field(default_factory=list)
    canonical_figures: list[dict[str, Any]] = field(default_factory=list)
    notes: list[IntegrationNote] = field(default_factory=list)


@dataclass
class SectionMetaComment:
    """Parsed REPORT_SECTION_META comment from a section.
    
    Attributes:
        section_id: The section identifier
        version: Version number of the section content
        integration_hints: Optional integration hints from the integrator
    """
    section_id: str
    version: int
    integration_hints: IntegrationHints | None = None


SECTION_META_PATTERN = re.compile(
    r'<!--\s*REPORT_SECTION_META\s*\n(.*?)\n\s*-->',
    re.DOTALL
)


def _integration_hints_from_dict(data: dict[str, Any]) -> IntegrationHints:
    """Convert a dictionary to IntegrationHints."""
    notes = [
        IntegrationNote(
            type=note.get("type", ""),
            semantic_key=note.get("semantic_key"),
            reason=note.get("reason"),
            replacement=note.get("replacement"),
        )
        for note in data.get("notes", [])
    ]
    return IntegrationHints(
        avoid_figures=data.get("avoid_figures", []),
        canonical_figures=data.get("canonical_figures", []),
        notes=notes,
    )


def _integration_hints_to_dict(hints: IntegrationHints) -> dict[str, Any]:
    """Convert IntegrationHints to a dictionary."""
    notes = []
    for note in hints.notes:
        note_dict: dict[str, Any] = {"type": note.type}
        if note.semantic_key is not None:
            note_dict["semantic_key"] = note.semantic_key
        if note.reason is not None:
            note_dict["reason"] = note.reason
        if note.replacement is not None:
            note_dict["replacement"] = note.replacement
        notes.append(note_dict)
    
    return {
        "avoid_figures": hints.avoid_figures,
        "canonical_figures": hints.canonical_figures,
        "notes": notes,
    }


def parse_section_meta(content: str) -> SectionMetaComment | None:
    """Extract and parse REPORT_SECTION_META from section content.
    
    Args:
        content: Section content that may contain a REPORT_SECTION_META comment
        
    Returns:
        Parsed SectionMetaComment or None if no meta comment found or parsing fails
    """
    match = SECTION_META_PATTERN.search(content)
    if not match:
        return None
    
    json_str = match.group(1).strip()
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    
    if "section_id" not in data or "version" not in data:
        return None
    
    integration_hints = None
    if "integration_hints" in data and data["integration_hints"]:
        integration_hints = _integration_hints_from_dict(data["integration_hints"])
    
    return SectionMetaComment(
        section_id=data["section_id"],
        version=data["version"],
        integration_hints=integration_hints,
    )


def extract_section_meta_and_body(content: str) -> tuple[SectionMetaComment | None, str]:
    """Extract meta comment and return (meta, remaining_body).
    
    Useful when you need both the parsed meta and the content without it.
    
    Args:
        content: Section content that may contain a REPORT_SECTION_META comment
        
    Returns:
        Tuple of (parsed meta or None, body without meta comment)
    """
    meta = parse_section_meta(content)
    
    body = SECTION_META_PATTERN.sub('', content).strip()
    
    return (meta, body)


def serialize_section_meta(meta: SectionMetaComment) -> str:
    """Convert SectionMetaComment to HTML comment string.
    
    Args:
        meta: SectionMetaComment to serialize
        
    Returns:
        HTML comment string in the format:
        <!-- REPORT_SECTION_META
        {
          "section_id": "...",
          "version": 1,
          "integration_hints": {...}
        }
        -->
    """
    data: dict[str, Any] = {
        "section_id": meta.section_id,
        "version": meta.version,
    }
    
    if meta.integration_hints:
        data["integration_hints"] = _integration_hints_to_dict(meta.integration_hints)
    
    json_str = json.dumps(data, indent=2)
    
    return f"<!-- REPORT_SECTION_META\n{json_str}\n-->"


def inject_section_meta(content: str, meta: SectionMetaComment) -> str:
    """Inject or replace REPORT_SECTION_META comment at top of content.
    
    Args:
        content: Section content
        meta: SectionMetaComment to inject
        
    Returns:
        Content with meta comment at top (replacing any existing meta comment)
    """
    _, body = extract_section_meta_and_body(content)
    
    meta_str = serialize_section_meta(meta)
    
    if body:
        return f"{meta_str}\n\n{body}"
    else:
        return meta_str
