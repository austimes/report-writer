"""Section-to-chart mapping for report generation."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .data_catalog import ChartMeta, DataCatalog
from .outline_parser import Section


CATEGORY_ALIASES: dict[str, list[str]] = {
    "emissions": ["emissions"],
    "electricity-generation": ["electricity"],
    "electricity": ["electricity"],
    "transport": ["transport"],
    "residential": ["built_environment"],
    "commercial": ["built_environment"],
    "agriculture": ["agriculture"],
    "industry": ["industry", "manufacturing"],
    "manufacturing": ["manufacturing", "industry"],
}


@dataclass
class SectionMapping:
    """Mapping configuration for a section."""

    charts: list[str]
    description: str = ""


def get_section_keywords(section: Section) -> set[str]:
    """Extract keywords from section title and instructions."""
    text = f"{section.title} {section.instructions}"
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    words = text.split()

    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall", "can",
        "this", "that", "these", "those", "it", "its", "their", "they",
        "section", "include", "including", "discuss", "describe", "explain",
        "analyze", "analysis", "overview", "summary", "about", "how", "what",
        "when", "where", "why", "which", "key", "main", "major", "primary",
    }

    keywords = {w for w in words if len(w) > 2 and w not in stopwords}
    return keywords


class SectionMapper:
    """Maps report sections to relevant charts using static mappings and auto-matching."""

    def __init__(self, catalog: DataCatalog, mapping_path: Path | None = None):
        """
        Args:
            catalog: DataCatalog instance
            mapping_path: Optional path to section_chart_map.json
        """
        self._catalog = catalog
        self._mapping_path = mapping_path
        self._static_mappings: dict[str, SectionMapping] = {}

        if mapping_path and mapping_path.exists():
            self._load_static_mappings()

    def _load_static_mappings(self) -> None:
        """Load static mappings from JSON file."""
        if not self._mapping_path or not self._mapping_path.exists():
            return

        try:
            content = self._mapping_path.read_text()
            data = json.loads(content)
            for section_id, mapping_data in data.items():
                charts = mapping_data.get("charts", [])
                description = mapping_data.get("description", "")
                self._static_mappings[section_id] = SectionMapping(
                    charts=charts, description=description
                )
        except (json.JSONDecodeError, KeyError):
            pass

    def get_charts_for_section(self, section_id: str) -> list[ChartMeta]:
        """Get relevant charts for a section."""
        if section_id in self._static_mappings:
            mapping = self._static_mappings[section_id]
            charts = []
            for chart_id in mapping.charts:
                chart = self._lookup_chart(chart_id)
                if chart:
                    charts.append(chart)
            return charts

        return self._auto_map_section(section_id)

    def _lookup_chart(self, chart_id: str) -> ChartMeta | None:
        """Look up a chart by ID, handling category/id format."""
        chart = self._catalog.get_chart(chart_id)
        if chart:
            return chart
        if "/" in chart_id:
            base_id = chart_id.split("/", 1)[1]
            return self._catalog.get_chart(base_id)
        return None

    def get_charts_for_section_obj(self, section: Section) -> list[ChartMeta]:
        """Get relevant charts for a Section object (uses full context)."""
        if section.id in self._static_mappings:
            return self.get_charts_for_section(section.id)

        return self._auto_map_section_with_context(section)

    def _auto_map_section(self, section_id: str) -> list[ChartMeta]:
        """Auto-map a section using only its ID."""
        section_keywords = self._extract_keywords_from_id(section_id)
        return self._find_matching_charts(section_keywords, section_id)

    def _auto_map_section_with_context(self, section: Section) -> list[ChartMeta]:
        """Auto-map a section using full context."""
        keywords = get_section_keywords(section)
        keywords.update(self._extract_keywords_from_id(section.id))
        return self._find_matching_charts(keywords, section.id)

    def _extract_keywords_from_id(self, section_id: str) -> set[str]:
        """Extract keywords from a section ID."""
        words = section_id.replace("-", " ").replace("_", " ").lower().split()
        return {w for w in words if len(w) > 2}

    def _find_matching_charts(
        self, keywords: set[str], section_id: str
    ) -> list[ChartMeta]:
        """Find charts matching the given keywords."""
        all_charts = self._catalog.list_charts()
        scored_charts: list[tuple[float, ChartMeta]] = []

        category_matches = self._get_category_matches(section_id)

        for chart in all_charts:
            score = self._score_chart(chart, keywords, section_id, category_matches)
            if score > 0:
                scored_charts.append((score, chart))

        scored_charts.sort(key=lambda x: (-x[0], x[1].id))
        return [chart for _, chart in scored_charts[:5]]

    def _get_category_matches(self, section_id: str) -> set[str]:
        """Get categories that match the section via aliases."""
        matched_categories: set[str] = set()
        section_id_lower = section_id.lower()

        for alias_key, category_list in CATEGORY_ALIASES.items():
            if alias_key in section_id_lower or section_id_lower in alias_key:
                matched_categories.update(category_list)

        return matched_categories

    def _score_chart(
        self,
        chart: ChartMeta,
        keywords: set[str],
        section_id: str,
        category_matches: set[str],
    ) -> float:
        """Score a chart based on relevance to the section."""
        score = 0.0

        if chart.category in category_matches:
            score += 3.0

        section_id_parts = set(section_id.lower().replace("-", " ").split())
        if chart.category.lower() in section_id_parts:
            score += 2.0

        chart_title_lower = chart.title.lower()
        chart_title_words = set(
            re.sub(r"[^\w\s]", " ", chart_title_lower).split()
        )

        keyword_overlap = keywords & chart_title_words
        score += len(keyword_overlap) * 1.0

        section_id_lower = section_id.lower().replace("-", "_")
        if section_id_lower in chart.id.lower():
            score += 2.0
        elif any(part in chart.id.lower() for part in section_id_lower.split("_") if len(part) > 3):
            score += 1.0

        return score

    def get_all_mappings(self) -> dict[str, list[str]]:
        """Return all section -> chart_id mappings."""
        return {
            section_id: mapping.charts
            for section_id, mapping in self._static_mappings.items()
        }
