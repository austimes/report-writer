"""Section-to-chart mapping for report generation."""

import fnmatch
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .data_catalog import ChartMeta, DataCatalog
from .outline_parser import Section

logger = logging.getLogger(__name__)


@dataclass
class ChartSelector:
    """A single chart selector - can be explicit ID, pattern, or auto-fill."""

    id: str | None = None
    pattern: str | None = None
    auto: bool = False
    max: int | None = None
    sort: str = "id"


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

    selectors: list[ChartSelector] = field(default_factory=list)
    description: str = ""
    max_charts: int | None = None

    @property
    def charts(self) -> list[str]:
        """Backwards-compatible: return explicit chart IDs only."""
        return [s.id for s in self.selectors if s.id is not None]


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
        """Load static mappings from JSON file.

        Supports both legacy format (list of strings) and new format
        with pattern/auto selectors.
        """
        if not self._mapping_path or not self._mapping_path.exists():
            return

        try:
            content = self._mapping_path.read_text()
            data = json.loads(content)
            for section_id, mapping_data in data.items():
                raw_charts = mapping_data.get("charts", [])
                description = mapping_data.get("description", "")
                max_charts = mapping_data.get("max_charts")

                selectors = self._parse_selectors(raw_charts)
                self._static_mappings[section_id] = SectionMapping(
                    selectors=selectors,
                    description=description,
                    max_charts=max_charts,
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load static mappings: {e}")

    def _parse_selectors(self, raw_charts: list) -> list[ChartSelector]:
        """Parse chart entries into ChartSelector objects.

        Handles:
        - Strings: explicit chart IDs (legacy format)
        - Dicts with "pattern": glob pattern matching
        - Dicts with "auto": auto-fill using keyword scoring
        """
        selectors: list[ChartSelector] = []

        for entry in raw_charts:
            if isinstance(entry, str):
                selectors.append(ChartSelector(id=entry))
            elif isinstance(entry, dict):
                selectors.append(
                    ChartSelector(
                        id=entry.get("id"),
                        pattern=entry.get("pattern"),
                        auto=entry.get("auto", False),
                        max=entry.get("max"),
                        sort=entry.get("sort", "id"),
                    )
                )

        return selectors

    def get_charts_for_section(self, section_id: str) -> list[ChartMeta]:
        """Get relevant charts for a section."""
        if section_id in self._static_mappings:
            return self._resolve_configured_charts(section_id)

        return self._auto_map_section(section_id)

    def get_charts_for_section_obj(self, section: Section) -> list[ChartMeta]:
        """Get relevant charts for a Section object (uses full context)."""
        if section.id in self._static_mappings:
            return self._resolve_configured_charts(section.id, section)

        return self._auto_map_section_with_context(section)

    def _resolve_configured_charts(
        self,
        section_id: str,
        section: Section | None = None,
    ) -> list[ChartMeta]:
        """Resolve configured charts using explicit IDs, patterns, and auto-fill.

        Processes selectors in order (order = priority):
        1. Explicit IDs: look up specific charts
        2. Patterns: glob-match against available charts
        3. Auto: use keyword scoring to fill remaining slots

        Missing charts are silently skipped. Duplicates are deduplicated.
        """
        mapping = self._static_mappings[section_id]
        result: list[ChartMeta] = []
        seen: set[str] = set()

        def add_chart(chart: ChartMeta) -> bool:
            """Add chart if not seen and under max_charts limit."""
            full_id = f"{chart.category}/{chart.id}"
            if full_id in seen:
                return False
            if mapping.max_charts and len(result) >= mapping.max_charts:
                return False
            result.append(chart)
            seen.add(full_id)
            return True

        for sel in mapping.selectors:
            if mapping.max_charts and len(result) >= mapping.max_charts:
                break

            if sel.id:
                chart = self._lookup_chart(sel.id)
                if chart:
                    add_chart(chart)
                else:
                    logger.debug(f"Chart not found: {sel.id}")

            elif sel.pattern:
                matches = self._match_pattern(sel.pattern)
                if sel.sort == "title":
                    matches.sort(key=lambda c: c.title)
                else:
                    matches.sort(key=lambda c: (c.category, c.id))

                count = 0
                for chart in matches:
                    if sel.max is not None and count >= sel.max:
                        break
                    if add_chart(chart):
                        count += 1

            elif sel.auto:
                if section is not None:
                    autos = self._auto_map_section_with_context(section)
                else:
                    autos = self._auto_map_section(section_id)

                count = 0
                for chart in autos:
                    if mapping.max_charts and len(result) >= mapping.max_charts:
                        break
                    if sel.max is not None and count >= sel.max:
                        break
                    if add_chart(chart):
                        count += 1

        return result

    def _lookup_chart(self, chart_id: str) -> ChartMeta | None:
        """Look up a chart by ID, handling category/id format."""
        chart = self._catalog.get_chart(chart_id)
        if chart:
            return chart
        if "/" in chart_id:
            base_id = chart_id.split("/", 1)[1]
            return self._catalog.get_chart(base_id)
        return None

    def _match_pattern(self, pattern: str) -> list[ChartMeta]:
        """Match charts against a glob pattern.

        If pattern contains "/", matches against "category/id".
        Otherwise, matches against just the chart id.
        """
        all_charts = self._catalog.list_charts()
        matches: list[ChartMeta] = []

        for chart in all_charts:
            full_id = f"{chart.category}/{chart.id}"

            if "/" in pattern:
                if fnmatch.fnmatch(full_id, pattern):
                    matches.append(chart)
            else:
                if fnmatch.fnmatch(chart.id, pattern):
                    matches.append(chart)

        return matches

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
