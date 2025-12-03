import pytest
from pathlib import Path
from io import StringIO

import pandas as pd

from report_agent.chart_reader import ChartReader, ChartSummary
from report_agent.data_catalog import DataCatalog, ChartMeta


class TestChartSummary:
    def test_dataclass_fields(self):
        summary = ChartSummary(
            chart_id="test",
            title="Test Chart",
            dimensions=["sector"],
            measure="val",
            measure_type="relative",
            units="Mt CO2-e",
            scenarios=["A", "B"],
            years=[2025, 2030],
            row_count=10,
        )
        assert summary.chart_id == "test"
        assert summary.title == "Test Chart"
        assert summary.dimensions == ["sector"]
        assert summary.measure == "val"
        assert summary.measure_type == "relative"
        assert summary.units == "Mt CO2-e"
        assert summary.scenarios == ["A", "B"]
        assert summary.years == [2025, 2030]
        assert summary.row_count == 10
        assert summary.by_scenario == {}
        assert summary.key_insights == []

    def test_with_by_scenario(self):
        summary = ChartSummary(
            chart_id="test",
            title="Test",
            dimensions=[],
            measure="val",
            measure_type="value",
            units="",
            scenarios=["A"],
            years=[],
            row_count=5,
            by_scenario={"A": {"baseline": 100}},
            key_insights=["Test insight"],
        )
        assert summary.by_scenario == {"A": {"baseline": 100}}
        assert summary.key_insights == ["Test insight"]


class TestChartReaderWithMockData:
    @pytest.fixture
    def mock_data_root(self, tmp_path):
        (tmp_path / "emissions").mkdir()

        csv_content = """process_sector0,val,measure,scen
Net 2025,401.05,relative,Ampol-1p5DS
Power Generation,-128.92,relative,Ampol-1p5DS
Industry,-109.74,relative,Ampol-1p5DS
Transport,-94.07,relative,Ampol-1p5DS
Net 2025,401.05,relative,Ampol-House-View
Power Generation,-127.83,relative,Ampol-House-View
Industry,-72.37,relative,Ampol-House-View
Land Use,33.58,relative,Ampol-House-View
"""
        (tmp_path / "emissions" / "emissions_reduction.csv").write_text(csv_content)

        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        (tmp_path / "emissions" / "emissions_reduction.png").write_bytes(png_data)

        json_content = '{"title": "Emissions Reduction", "type": "bar"}'
        (tmp_path / "emissions" / "emissions_reduction.json").write_text(json_content)

        spec_content = """{
    "title": "Emissions Reduction",
    "filter": "varbl == 'emissions'",
    "groupby": ["scen", "process_sector0"],
    "category": "emissions",
    "si_unit": "Mt CO2-e"
}"""
        (tmp_path / "plot_specs.json").write_text(spec_content)

        return tmp_path

    @pytest.fixture
    def catalog(self, mock_data_root):
        return DataCatalog(mock_data_root)

    @pytest.fixture
    def reader(self, catalog):
        return ChartReader(catalog)

    def test_load_data(self, reader):
        df = reader.load_data("emissions_reduction")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 8
        assert "val" in df.columns
        assert "scen" in df.columns

    def test_load_data_caching(self, reader):
        df1 = reader.load_data("emissions_reduction")
        df2 = reader.load_data("emissions_reduction")
        assert df1 is df2

    def test_load_data_not_found(self, reader):
        with pytest.raises(ValueError, match="Chart not found"):
            reader.load_data("nonexistent")

    def test_get_summary_basic(self, reader):
        summary = reader.get_summary("emissions_reduction")
        assert summary.chart_id == "emissions_reduction"
        assert summary.title == "Emissions Reduction"
        assert summary.measure == "val"
        assert summary.measure_type == "relative"
        assert summary.row_count == 8

    def test_get_summary_scenarios(self, reader):
        summary = reader.get_summary("emissions_reduction")
        assert len(summary.scenarios) == 2
        assert "Ampol-1p5DS" in summary.scenarios
        assert "Ampol-House-View" in summary.scenarios

    def test_get_summary_dimensions(self, reader):
        summary = reader.get_summary("emissions_reduction")
        assert "process_sector0" in summary.dimensions

    def test_get_summary_by_scenario(self, reader):
        summary = reader.get_summary("emissions_reduction")
        assert "Ampol-1p5DS" in summary.by_scenario
        scen_summary = summary.by_scenario["Ampol-1p5DS"]
        assert scen_summary["baseline"] == 401.05
        assert "total_reduction" in scen_summary
        assert "top_reductions" in scen_summary

    def test_get_summary_top_reductions(self, reader):
        summary = reader.get_summary("emissions_reduction")
        top = summary.by_scenario["Ampol-1p5DS"]["top_reductions"]
        assert len(top) >= 1
        assert top[0]["sector"] == "Power Generation"
        assert top[0]["value"] == -128.92

    def test_get_summary_notable_increases(self, reader):
        summary = reader.get_summary("emissions_reduction")
        increases = summary.by_scenario["Ampol-House-View"]["notable_increases"]
        assert len(increases) == 1
        assert increases[0]["sector"] == "Land Use"
        assert increases[0]["value"] == 33.58

    def test_get_summary_key_insights(self, reader):
        summary = reader.get_summary("emissions_reduction")
        assert len(summary.key_insights) > 0
        insights_text = " ".join(summary.key_insights)
        assert "401.05" in insights_text
        assert "Power Generation" in insights_text

    def test_get_image_base64(self, reader):
        b64 = reader.get_image_base64("emissions_reduction")
        assert b64 is not None
        assert isinstance(b64, str)
        import base64
        decoded = base64.b64decode(b64)
        assert decoded.startswith(b"\x89PNG")

    def test_get_image_base64_not_found(self, reader):
        result = reader.get_image_base64("nonexistent")
        assert result is None

    def test_get_plot_spec(self, reader):
        spec = reader.get_plot_spec("emissions_reduction")
        assert spec is not None
        assert spec["title"] == "Emissions Reduction"
        assert spec["type"] == "bar"

    def test_get_plot_spec_not_found(self, reader):
        result = reader.get_plot_spec("nonexistent")
        assert result is None


class TestChartReaderTimeSeriesData:
    @pytest.fixture
    def timeseries_data_root(self, tmp_path):
        (tmp_path / "emissions").mkdir()

        csv_content = """scen,sector,unit,2025,2030,2040,2050
Ampol-1p5DS,Agriculture,Mt CO2-e,100,90,70,50
Ampol-1p5DS,Industry,Mt CO2-e,200,180,140,100
Ampol-House-View,Agriculture,Mt CO2-e,100,95,85,80
Ampol-House-View,Industry,Mt CO2-e,200,195,185,180
"""
        (tmp_path / "emissions" / "emissions_by_sector.csv").write_text(csv_content)

        spec_content = """{
    "title": "Emissions By Sector",
    "groupby": ["scen", "sector"],
    "si_unit": "Mt CO2-e"
}"""
        (tmp_path / "plot_specs.json").write_text(spec_content)

        return tmp_path

    @pytest.fixture
    def reader(self, timeseries_data_root):
        catalog = DataCatalog(timeseries_data_root)
        return ChartReader(catalog)

    def test_extract_years_from_columns(self, reader):
        summary = reader.get_summary("emissions_by_sector")
        assert summary.years == [2025, 2030, 2040, 2050]

    def test_scenario_summary_timeseries(self, reader):
        summary = reader.get_summary("emissions_by_sector")
        scen_summary = summary.by_scenario["Ampol-1p5DS"]
        assert scen_summary["start_year"] == 2025
        assert scen_summary["end_year"] == 2050
        assert scen_summary["start_value"] == 300.0
        assert scen_summary["end_value"] == 150.0
        assert scen_summary["percent_change"] == -50.0

    def test_timeseries_insights(self, reader):
        summary = reader.get_summary("emissions_by_sector")
        insights_text = " ".join(summary.key_insights)
        assert "2025" in insights_text or "2050" in insights_text
        assert "%" in insights_text or "decreases" in insights_text


class TestChartReaderEdgeCases:
    @pytest.fixture
    def minimal_data_root(self, tmp_path):
        (tmp_path / "data").mkdir()

        csv_content = """category,value
A,100
B,200
C,300
"""
        (tmp_path / "data" / "simple.csv").write_text(csv_content)
        return tmp_path

    @pytest.fixture
    def reader(self, minimal_data_root):
        catalog = DataCatalog(minimal_data_root)
        return ChartReader(catalog)

    def test_no_scenario_column(self, reader):
        summary = reader.get_summary("simple")
        assert summary.scenarios == []
        assert summary.by_scenario == {}

    def test_no_year_column(self, reader):
        summary = reader.get_summary("simple")
        assert summary.years == []

    def test_detect_dimensions_fallback(self, reader):
        summary = reader.get_summary("simple")
        assert "category" in summary.dimensions

    def test_detect_measure_fallback(self, reader):
        summary = reader.get_summary("simple")
        assert summary.measure in ["val", "value"]


class TestChartReaderRealData:
    def test_real_emissions_reduction(self):
        data_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "data"
            / "example-outputs"
            / "ampol2025"
            / "2025-12-03T10.20_Ampol.2025-12-03T10.36_all"
        )
        if not data_path.exists():
            pytest.skip("Example data directory not found")

        catalog = DataCatalog(data_path)
        reader = ChartReader(catalog)

        chart = catalog.get_chart("emissions_reduction_by_sector")
        if chart is None:
            pytest.skip("emissions_reduction_by_sector chart not found")

        summary = reader.get_summary("emissions_reduction_by_sector")

        assert len(summary.scenarios) >= 1
        assert summary.row_count > 0
        assert len(summary.key_insights) > 0

        for scen in summary.scenarios:
            scen_summary = summary.by_scenario[scen]
            assert "baseline" in scen_summary or "total_reduction" in scen_summary

    def test_real_timeseries_data(self):
        data_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "data"
            / "example-outputs"
            / "ampol2025"
            / "2025-12-03T10.20_Ampol.2025-12-03T10.36_all"
        )
        if not data_path.exists():
            pytest.skip("Example data directory not found")

        catalog = DataCatalog(data_path)
        reader = ChartReader(catalog)

        chart = catalog.get_chart("agriculture_and_land_use_emissions")
        if chart is None:
            pytest.skip("agriculture_and_land_use_emissions chart not found")

        summary = reader.get_summary("agriculture_and_land_use_emissions")

        assert len(summary.years) > 0
        assert 2025 in summary.years
        assert 2050 in summary.years
