"""Data catalog for discovering and indexing chart metadata from the data directory."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import re


@dataclass
class ChartMeta:
    """Metadata for a single chart."""

    id: str
    category: str
    title: str
    path_csv: Path | None = None
    path_png: Path | None = None
    path_json: Path | None = None
    dimensions: list[str] = field(default_factory=list)
    measures: list[str] = field(default_factory=lambda: ["val"])
    units: str = ""
    filter_expression: str = ""
    scenarios: list[str] = field(default_factory=list)


def _id_to_title(chart_id: str) -> str:
    """Convert a chart ID to a human-readable title."""
    return chart_id.replace("_", " ").title()


class DataCatalog:
    """Catalog of available charts in a data directory."""

    def __init__(self, data_root: Path):
        self._original_root = Path(data_root)
        self.data_root = self._find_data_root()
        self._charts: dict[str, ChartMeta] = {}
        self._categories: list[str] = []
        self._plot_specs: dict[str, dict] = {}

        self._load_plot_specs()
        self._scan_charts()

    def _find_data_root(self) -> Path:
        """Locate the actual data export folder containing plot_specs.json.

        If the original root contains plot_specs.json, use it directly.
        Otherwise, search for subdirectories that contain plot_specs.json.
        Returns the first matching subdirectory, or the original root if none found.
        """
        if not self._original_root.exists():
            return self._original_root

        if (self._original_root / "plot_specs.json").exists():
            return self._original_root

        for entry in sorted(self._original_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                if (entry / "plot_specs.json").exists():
                    return entry

        return self._original_root

    def _load_plot_specs(self) -> dict:
        """Parse plot_specs.json (newline-delimited JSON objects)."""
        specs_path = self.data_root / "plot_specs.json"
        if not specs_path.exists():
            return {}

        content = specs_path.read_text()
        parts = content.split("}\n{")

        specs_by_title: dict[str, dict] = {}
        for i, part in enumerate(parts):
            if i == 0:
                json_str = part + "}"
            elif i == len(parts) - 1:
                json_str = "{" + part
            else:
                json_str = "{" + part + "}"

            try:
                spec = json.loads(json_str)
                title = spec.get("title", "")
                if title:
                    specs_by_title[title] = spec
            except json.JSONDecodeError:
                continue

        self._plot_specs = specs_by_title
        return specs_by_title

    def _scan_charts(self) -> None:
        """Discover charts from folder structure."""
        if not self.data_root.exists():
            return

        categories = []
        for entry in sorted(self.data_root.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                categories.append(entry.name)
                self._scan_category(entry)

        self._categories = categories

    def _scan_category(self, category_path: Path) -> None:
        """Scan a category folder for charts."""
        category = category_path.name

        chart_ids: set[str] = set()
        for file in category_path.iterdir():
            if file.suffix in (".csv", ".png", ".json"):
                chart_ids.add(file.stem)

        for chart_id in sorted(chart_ids):
            csv_path = category_path / f"{chart_id}.csv"
            png_path = category_path / f"{chart_id}.png"
            json_path = category_path / f"{chart_id}.json"

            spec = self._find_spec_for_chart(chart_id)

            title = spec.get("title", _id_to_title(chart_id)) if spec else _id_to_title(chart_id)
            groupby = spec.get("groupby", []) if spec else []
            dimensions = [col for col in groupby if col not in ("scen", "year", "unit")]
            si_unit = spec.get("si_unit", "") if spec else ""
            filter_expr = spec.get("filter", "") if spec else ""

            chart = ChartMeta(
                id=chart_id,
                category=category,
                title=title,
                path_csv=csv_path if csv_path.exists() else None,
                path_png=png_path if png_path.exists() else None,
                path_json=json_path if json_path.exists() else None,
                dimensions=dimensions,
                measures=["val"],
                units=si_unit,
                filter_expression=filter_expr,
                scenarios=[],
            )
            self._charts[chart_id] = chart

    def _find_spec_for_chart(self, chart_id: str) -> dict | None:
        """Find the plot spec matching a chart ID."""
        chart_title_normalized = chart_id.replace("_", " ").lower()

        for title, spec in self._plot_specs.items():
            spec_title_normalized = title.lower()
            if self._normalize_title(spec_title_normalized) == self._normalize_title(chart_title_normalized):
                return spec

        return None

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        return re.sub(r"[^a-z0-9]", "", title.lower())

    def list_categories(self) -> list[str]:
        """Return category folder names."""
        return self._categories.copy()

    def list_charts(self, category: str | None = None) -> list[ChartMeta]:
        """List charts, optionally filtered by category."""
        charts = list(self._charts.values())
        if category is not None:
            charts = [c for c in charts if c.category == category]
        return sorted(charts, key=lambda c: (c.category, c.id))

    def get_chart(self, chart_id: str) -> ChartMeta | None:
        """Get a single chart by ID."""
        return self._charts.get(chart_id)
