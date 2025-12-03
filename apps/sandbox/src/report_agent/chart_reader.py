"""Chart reader with pre-computed summaries for the Report Agent."""

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from report_agent.data_catalog import ChartMeta, DataCatalog


@dataclass
class ChartSummary:
    """Pre-computed summary of chart data."""

    chart_id: str
    title: str
    dimensions: list[str]
    measure: str
    measure_type: str
    units: str
    scenarios: list[str]
    years: list[int]
    row_count: int
    by_scenario: dict = field(default_factory=dict)
    key_insights: list[str] = field(default_factory=list)


class ChartReader:
    """Read and summarize chart data from the catalog."""

    def __init__(self, catalog: DataCatalog):
        self.catalog = catalog
        self._df_cache: dict[str, pd.DataFrame] = {}

    def load_data(self, chart_id: str) -> pd.DataFrame:
        """Load CSV data into a DataFrame."""
        if chart_id in self._df_cache:
            return self._df_cache[chart_id]

        chart = self.catalog.get_chart(chart_id)
        if chart is None or chart.path_csv is None:
            raise ValueError(f"Chart not found or has no CSV: {chart_id}")

        df = pd.read_csv(chart.path_csv)
        self._df_cache[chart_id] = df
        return df

    def get_summary(self, chart_id: str) -> ChartSummary:
        """Compute a comprehensive summary of the chart data."""
        chart = self.catalog.get_chart(chart_id)
        if chart is None:
            raise ValueError(f"Chart not found: {chart_id}")

        df = self.load_data(chart_id)

        scenarios = self._extract_scenarios(df)
        years = self._extract_years(df)
        dimensions = self._detect_dimensions(df, chart)
        measure = self._detect_measure(df)
        measure_type = self._detect_measure_type(df)

        by_scenario = {}
        for scenario in scenarios:
            by_scenario[scenario] = self._compute_scenario_summary(df, scenario)

        key_insights = self._generate_insights(df, chart)

        return ChartSummary(
            chart_id=chart_id,
            title=chart.title,
            dimensions=dimensions,
            measure=measure,
            measure_type=measure_type,
            units=chart.units,
            scenarios=scenarios,
            years=years,
            row_count=len(df),
            by_scenario=by_scenario,
            key_insights=key_insights,
        )

    def get_image_base64(self, chart_id: str) -> str | None:
        """Encode PNG image as base64 string."""
        chart = self.catalog.get_chart(chart_id)
        if chart is None or chart.path_png is None:
            return None

        if not chart.path_png.exists():
            return None

        with open(chart.path_png, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def get_plot_spec(self, chart_id: str) -> dict | None:
        """Load Plotly JSON specification."""
        chart = self.catalog.get_chart(chart_id)
        if chart is None or chart.path_json is None:
            return None

        if not chart.path_json.exists():
            return None

        with open(chart.path_json) as f:
            return json.load(f)

    def _extract_scenarios(self, df: pd.DataFrame) -> list[str]:
        """Extract unique scenario values from the data."""
        if "scen" in df.columns:
            return sorted(df["scen"].dropna().unique().tolist())
        return []

    def _extract_years(self, df: pd.DataFrame) -> list[int]:
        """Extract unique years from the data."""
        if "year" in df.columns:
            return sorted(int(y) for y in df["year"].dropna().unique())

        year_cols = [c for c in df.columns if c.isdigit() and 2000 <= int(c) <= 2100]
        if year_cols:
            return sorted(int(c) for c in year_cols)

        return []

    def _detect_dimensions(self, df: pd.DataFrame, chart: ChartMeta) -> list[str]:
        """Detect dimension columns in the data."""
        if chart.dimensions:
            return [d for d in chart.dimensions if d in df.columns]

        skip_cols = {"scen", "year", "val", "unit", "units", "measure"}
        potential = [c for c in df.columns if c not in skip_cols and df[c].dtype == object]

        non_numeric = []
        for col in potential:
            try:
                pd.to_numeric(df[col], errors="raise")
            except (ValueError, TypeError):
                non_numeric.append(col)

        return non_numeric

    def _detect_measure(self, df: pd.DataFrame) -> str:
        """Detect the measure column name."""
        if "val" in df.columns:
            return "val"

        year_cols = [c for c in df.columns if c.isdigit() and 2000 <= int(c) <= 2100]
        if year_cols:
            return "year_values"

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            return numeric_cols[0]

        return "val"

    def _detect_measure_type(self, df: pd.DataFrame) -> str:
        """Detect what the measure represents."""
        if "measure" in df.columns:
            measures = df["measure"].dropna().unique()
            if len(measures) == 1:
                return str(measures[0])
            return ", ".join(str(m) for m in measures)
        return "value"

    def _compute_scenario_summary(self, df: pd.DataFrame, scenario: str) -> dict:
        """Compute per-scenario summary statistics."""
        if "scen" not in df.columns:
            return {}

        scen_df = df[df["scen"] == scenario]
        result: dict = {}

        if "val" in scen_df.columns:
            values = scen_df["val"].dropna()

            baseline_row = scen_df[scen_df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]
            if not baseline_row.empty:
                result["baseline"] = float(baseline_row["val"].iloc[0])

            non_baseline = scen_df[~scen_df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]
            if not non_baseline.empty:
                total_reduction = non_baseline["val"].sum()
                result["total_reduction"] = round(float(total_reduction), 2)

                dim_col = scen_df.columns[0]
                sorted_df = non_baseline.sort_values("val")

                reductions = sorted_df[sorted_df["val"] < 0].head(3)
                result["top_reductions"] = [
                    {"sector": row[dim_col], "value": round(float(row["val"]), 2)} for _, row in reductions.iterrows()
                ]

                increases = sorted_df[sorted_df["val"] > 0]
                result["notable_increases"] = [
                    {"sector": row[dim_col], "value": round(float(row["val"]), 2)} for _, row in increases.iterrows()
                ]
        else:
            year_cols = [c for c in scen_df.columns if c.isdigit() and 2000 <= int(c) <= 2100]
            if year_cols:
                first_year = min(year_cols, key=int)
                last_year = max(year_cols, key=int)

                start_total = scen_df[first_year].sum()
                end_total = scen_df[last_year].sum()

                result["start_year"] = int(first_year)
                result["end_year"] = int(last_year)
                result["start_value"] = round(float(start_total), 2)
                result["end_value"] = round(float(end_total), 2)

                if start_total != 0:
                    pct_change = ((end_total - start_total) / abs(start_total)) * 100
                    result["percent_change"] = round(float(pct_change), 1)

        return result

    def _generate_insights(self, df: pd.DataFrame, chart_meta: ChartMeta) -> list[str]:
        """Auto-generate key insights from the data."""
        insights = []
        scenarios = self._extract_scenarios(df)

        if "val" in df.columns:
            self._add_emissions_insights(df, scenarios, chart_meta, insights)
        else:
            year_cols = [c for c in df.columns if c.isdigit() and 2000 <= int(c) <= 2100]
            if year_cols:
                self._add_timeseries_insights(df, year_cols, scenarios, chart_meta, insights)

        return insights

    def _add_emissions_insights(
        self, df: pd.DataFrame, scenarios: list[str], chart_meta: ChartMeta, insights: list[str]
    ) -> None:
        """Add insights for emissions reduction type charts."""
        units = chart_meta.units or "units"

        baseline_rows = df[df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]
        if not baseline_rows.empty:
            baseline = baseline_rows["val"].iloc[0]
            insights.append(f"Baseline emissions in 2025: {baseline:.2f} {units}")

        dim_col = df.columns[0]
        non_baseline = df[~df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]

        if not non_baseline.empty:
            sector_avg = non_baseline.groupby(dim_col)["val"].mean()
            if len(sector_avg) > 0:
                top_reducer = sector_avg.idxmin()
                avg_reduction = abs(sector_avg.min())
                insights.append(f"{top_reducer} provides largest reduction across all scenarios (~{avg_reduction:.0f} {units})")

        for scen in scenarios:
            scen_df = df[df["scen"] == scen]
            non_baseline_scen = scen_df[~scen_df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]

            if not non_baseline_scen.empty:
                total = non_baseline_scen["val"].sum()
                if scen == scenarios[0] or total == min(
                    df[~df.iloc[:, 0].astype(str).str.contains("Net", case=False, na=False)]
                    .groupby("scen")["val"]
                    .sum()
                ):
                    if total < 0:
                        insights.append(f"{scen} achieves deepest total cuts ({total:.2f})")

                increases = non_baseline_scen[non_baseline_scen["val"] > 0]
                for _, row in increases.iterrows():
                    sector = row[dim_col]
                    val = row["val"]
                    insights.append(f"{scen} shows net increase from {sector} (+{val:.2f})")

    def _add_timeseries_insights(
        self,
        df: pd.DataFrame,
        year_cols: list[str],
        scenarios: list[str],
        chart_meta: ChartMeta,
        insights: list[str],
    ) -> None:
        """Add insights for time series type charts."""
        units = chart_meta.units or "units"
        first_year = min(year_cols, key=int)
        last_year = max(year_cols, key=int)

        for scen in scenarios[:2]:
            scen_df = df[df["scen"] == scen] if "scen" in df.columns else df

            start_total = scen_df[first_year].sum()
            end_total = scen_df[last_year].sum()

            if start_total != 0:
                pct_change = ((end_total - start_total) / abs(start_total)) * 100
                direction = "increases" if pct_change > 0 else "decreases"
                insights.append(f"{scen}: Total {direction} {abs(pct_change):.1f}% from {first_year} to {last_year}")

        if len(scenarios) > 1 and "scen" in df.columns:
            final_totals = {}
            for scen in scenarios:
                scen_df = df[df["scen"] == scen]
                final_totals[scen] = scen_df[last_year].sum()

            max_scen = max(final_totals, key=lambda k: final_totals[k])
            min_scen = min(final_totals, key=lambda k: final_totals[k])

            if max_scen != min_scen:
                diff = final_totals[max_scen] - final_totals[min_scen]
                insights.append(f"By {last_year}, {max_scen} is {diff:.1f} {units} higher than {min_scen}")
