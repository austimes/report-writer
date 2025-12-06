"""Report state tracking for cross-section integration.

This module provides data structures for tracking canonical figures, tables,
and other artifacts across report sections, enabling the integration pass
to deduplicate content and add cross-references.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class CanonicalFigure:
    """A canonical figure registered in the report.
    
    Attributes:
        id: Unique figure ID (e.g., 'F1', 'F2')
        semantic_key: Semantic identifier (e.g., 'throughput_over_time')
        owner_section: Section ID that owns this figure
        caption: Figure caption/description
        chart_id: Optional link to source chart from data catalog
    """
    id: str
    semantic_key: str
    owner_section: str
    caption: str
    chart_id: str | None = None


@dataclass
class CanonicalTable:
    """A canonical table registered in the report.
    
    Attributes:
        id: Unique table ID (e.g., 'T1', 'T2')
        semantic_key: Semantic identifier
        owner_section: Section ID that owns this table
        caption: Table caption/description
    """
    id: str
    semantic_key: str
    owner_section: str
    caption: str


@dataclass
class SectionStateMeta:
    """Metadata about a section's integration state.
    
    Attributes:
        section_id: The section identifier
        version: Current version of the section content
        last_integrated_version: Version when integration was last run
    """
    section_id: str
    version: int = 1
    last_integrated_version: int = 0


@dataclass
class ReportState:
    """Global state for report integration.
    
    Tracks all canonical figures, tables, and section metadata to enable
    the integration pass to deduplicate content and maintain cross-references.
    """
    report_id: str
    figures: list[CanonicalFigure] = field(default_factory=list)
    tables: list[CanonicalTable] = field(default_factory=list)
    section_meta: dict[str, SectionStateMeta] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    
    @classmethod
    def new(cls, report_id: str) -> ReportState:
        """Create a new empty report state."""
        now = datetime.now().isoformat()
        return cls(
            report_id=report_id,
            figures=[],
            tables=[],
            section_meta={},
            created_at=now,
            updated_at=now,
        )
    
    @classmethod
    def load(cls, path: Path) -> ReportState:
        """Load report state from a JSON file.
        
        Args:
            path: Path to report_state.json file
            
        Returns:
            Loaded ReportState instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(path) as f:
            data = json.load(f)
        
        figures = [
            CanonicalFigure(**fig) for fig in data.get("figures", [])
        ]
        tables = [
            CanonicalTable(**tbl) for tbl in data.get("tables", [])
        ]
        section_meta = {
            k: SectionStateMeta(**v) for k, v in data.get("section_meta", {}).items()
        }
        
        return cls(
            report_id=data["report_id"],
            figures=figures,
            tables=tables,
            section_meta=section_meta,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
    
    def save(self, path: Path) -> None:
        """Save report state to a JSON file.
        
        Args:
            path: Path to save report_state.json
        """
        self.updated_at = datetime.now().isoformat()
        
        data = {
            "report_id": self.report_id,
            "figures": [asdict(fig) for fig in self.figures],
            "tables": [asdict(tbl) for tbl in self.tables],
            "section_meta": {k: asdict(v) for k, v in self.section_meta.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_next_figure_id(self) -> str:
        """Return the next available figure ID (F1, F2, ...)."""
        if not self.figures:
            return "F1"
        
        max_num = 0
        for fig in self.figures:
            if fig.id.startswith("F"):
                try:
                    num = int(fig.id[1:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        
        return f"F{max_num + 1}"
    
    def get_next_table_id(self) -> str:
        """Return the next available table ID (T1, T2, ...)."""
        if not self.tables:
            return "T1"
        
        max_num = 0
        for tbl in self.tables:
            if tbl.id.startswith("T"):
                try:
                    num = int(tbl.id[1:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        
        return f"T{max_num + 1}"
    
    def register_figure(
        self,
        semantic_key: str,
        owner_section: str,
        caption: str,
        chart_id: str | None = None,
    ) -> CanonicalFigure:
        """Register a new canonical figure.
        
        Args:
            semantic_key: Semantic identifier for the figure
            owner_section: Section ID that owns this figure
            caption: Figure caption/description
            chart_id: Optional link to source chart
            
        Returns:
            The newly created CanonicalFigure
        """
        figure = CanonicalFigure(
            id=self.get_next_figure_id(),
            semantic_key=semantic_key,
            owner_section=owner_section,
            caption=caption,
            chart_id=chart_id,
        )
        self.figures.append(figure)
        return figure
    
    def register_table(
        self,
        semantic_key: str,
        owner_section: str,
        caption: str,
    ) -> CanonicalTable:
        """Register a new canonical table.
        
        Args:
            semantic_key: Semantic identifier for the table
            owner_section: Section ID that owns this table
            caption: Table caption/description
            
        Returns:
            The newly created CanonicalTable
        """
        table = CanonicalTable(
            id=self.get_next_table_id(),
            semantic_key=semantic_key,
            owner_section=owner_section,
            caption=caption,
        )
        self.tables.append(table)
        return table
    
    def find_figure_by_semantic_key(self, key: str) -> CanonicalFigure | None:
        """Find an existing figure by its semantic key.
        
        Args:
            key: Semantic key to search for
            
        Returns:
            The matching CanonicalFigure or None if not found
        """
        for fig in self.figures:
            if fig.semantic_key == key:
                return fig
        return None
    
    def find_figure_by_chart_id(self, chart_id: str) -> CanonicalFigure | None:
        """Find an existing figure by its source chart ID.
        
        Args:
            chart_id: Chart ID to search for
            
        Returns:
            The matching CanonicalFigure or None if not found
        """
        for fig in self.figures:
            if fig.chart_id == chart_id:
                return fig
        return None
    
    def find_table_by_semantic_key(self, key: str) -> CanonicalTable | None:
        """Find an existing table by its semantic key.
        
        Args:
            key: Semantic key to search for
            
        Returns:
            The matching CanonicalTable or None if not found
        """
        for tbl in self.tables:
            if tbl.semantic_key == key:
                return tbl
        return None
    
    def get_section_meta(self, section_id: str) -> SectionStateMeta:
        """Get or create section metadata.
        
        Args:
            section_id: The section identifier
            
        Returns:
            Existing or newly created SectionStateMeta
        """
        if section_id not in self.section_meta:
            self.section_meta[section_id] = SectionStateMeta(section_id=section_id)
        return self.section_meta[section_id]
    
    def increment_section_version(self, section_id: str) -> int:
        """Increment a section's version number.
        
        Args:
            section_id: The section identifier
            
        Returns:
            The new version number
        """
        meta = self.get_section_meta(section_id)
        meta.version += 1
        return meta.version
    
    def mark_section_integrated(self, section_id: str) -> None:
        """Mark a section as having been integrated at its current version.
        
        Args:
            section_id: The section identifier
        """
        meta = self.get_section_meta(section_id)
        meta.last_integrated_version = meta.version
    
    def is_section_stale(self, section_id: str) -> bool:
        """Check if a section's integration hints may be stale.
        
        Returns True if the section has been modified since the last
        integration pass.
        
        Args:
            section_id: The section identifier
            
        Returns:
            True if section.version > section.last_integrated_version
        """
        meta = self.get_section_meta(section_id)
        return meta.version > meta.last_integrated_version
    
    def get_figures_for_section(self, section_id: str) -> list[CanonicalFigure]:
        """Get all figures owned by a section.
        
        Args:
            section_id: The section identifier
            
        Returns:
            List of CanonicalFigure objects owned by this section
        """
        return [fig for fig in self.figures if fig.owner_section == section_id]
    
    def get_figures_not_owned_by(self, section_id: str) -> list[CanonicalFigure]:
        """Get all figures NOT owned by a section.
        
        Useful for generating integration hints about what figures exist
        elsewhere that this section should reference instead of recreating.
        
        Args:
            section_id: The section identifier
            
        Returns:
            List of CanonicalFigure objects NOT owned by this section
        """
        return [fig for fig in self.figures if fig.owner_section != section_id]
