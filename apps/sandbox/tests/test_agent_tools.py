"""Tests for the Report Agent tools."""

import pytest
from pathlib import Path

from report_agent.agent_tools import ReportAgentTools


class TestReportAgentToolsInit:
    @pytest.fixture
    def empty_root(self, tmp_path):
        return tmp_path

    def test_init_with_nonexistent_paths(self, empty_root):
        outline_path = empty_root / "outline.md"
        data_path = empty_root / "data"
        
        tools = ReportAgentTools(outline_path, data_path)
        assert tools._sections == []
        assert tools.get_tool_schemas() is not None


class TestToolSchemas:
    @pytest.fixture
    def tools(self, tmp_path):
        return ReportAgentTools(tmp_path / "outline.md", tmp_path / "data")

    def test_get_tool_schemas_returns_list(self, tools):
        schemas = tools.get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 8

    def test_schema_format(self, tools):
        schemas = tools.get_tool_schemas()
        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_all_tools_present(self, tools):
        schemas = tools.get_tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        
        expected = [
            "get_section_context",
            "list_sections",
            "write_section_draft",
            "list_chart_categories",
            "list_charts",
            "get_chart_metadata",
            "get_chart_data",
            "get_chart_image",
        ]
        assert names == expected


class TestOutlineTools:
    @pytest.fixture
    def mock_outline(self, tmp_path):
        outline_content = """# Annual Report

## Executive Summary

<!-- Section instructions: Write the executive summary. -->

Current summary content here.

<!-- Review comments:
RATING: clarity=3, accuracy=4
NOTES: Needs more data citations.
-->

## Emissions Overview

<!-- Section instructions: Describe emissions trends. -->

### Sector Analysis

<!-- Section instructions: Break down by sector. -->
"""
        outline_path = tmp_path / "outline.md"
        outline_path.write_text(outline_content)
        return outline_path

    @pytest.fixture
    def tools(self, mock_outline, tmp_path):
        data_path = tmp_path / "data"
        data_path.mkdir()
        return ReportAgentTools(mock_outline, data_path)

    def test_list_sections(self, tools):
        result = tools.execute_tool("list_sections", {})
        assert isinstance(result, list)
        assert len(result) == 4
        
        ids = [s["id"] for s in result]
        assert "annual-report" in ids
        assert "executive-summary" in ids
        assert "emissions-overview" in ids
        assert "sector-analysis" in ids

    def test_list_sections_structure(self, tools):
        result = tools.execute_tool("list_sections", {})
        for section in result:
            assert "id" in section
            assert "title" in section
            assert "level" in section
            assert "parent_id" in section

    def test_list_sections_hierarchy(self, tools):
        result = tools.execute_tool("list_sections", {})
        sections_by_id = {s["id"]: s for s in result}
        
        assert sections_by_id["executive-summary"]["parent_id"] == "annual-report"
        assert sections_by_id["sector-analysis"]["parent_id"] == "emissions-overview"

    def test_get_section_context(self, tools):
        result = tools.execute_tool("get_section_context", {"section_id": "executive-summary"})
        
        assert result["section_id"] == "executive-summary"
        assert result["title"] == "Executive Summary"
        assert result["level"] == 2
        assert "Current summary content" in result["content"]
        assert result["instructions"] == "Write the executive summary."
        assert result["review_ratings"] == {"clarity": 3, "accuracy": 4}
        assert "Needs more data citations" in result["review_notes"]

    def test_get_section_context_not_found(self, tools):
        result = tools.execute_tool("get_section_context", {"section_id": "nonexistent"})
        assert "error" in result

    def test_write_section_draft(self, tools):
        result = tools.execute_tool("write_section_draft", {
            "section_id": "executive-summary",
            "content": "New draft content here."
        })
        
        assert result["success"] is True
        assert result["section_id"] == "executive-summary"
        
        context = tools.execute_tool("get_section_context", {"section_id": "executive-summary"})
        assert context["draft_content"] == "New draft content here."

    def test_write_section_draft_not_found(self, tools):
        result = tools.execute_tool("write_section_draft", {
            "section_id": "nonexistent",
            "content": "Content"
        })
        assert result["success"] is False
        assert "error" in result

    def test_get_draft_accessor(self, tools):
        tools.execute_tool("write_section_draft", {
            "section_id": "executive-summary",
            "content": "Draft text"
        })
        
        assert tools.get_draft("executive-summary") == "Draft text"
        assert tools.get_draft("nonexistent") is None

    def test_get_all_drafts(self, tools):
        tools.execute_tool("write_section_draft", {
            "section_id": "executive-summary",
            "content": "Draft 1"
        })
        tools.execute_tool("write_section_draft", {
            "section_id": "emissions-overview",
            "content": "Draft 2"
        })
        
        drafts = tools.get_all_drafts()
        assert len(drafts) == 2
        assert drafts["executive-summary"] == "Draft 1"
        assert drafts["emissions-overview"] == "Draft 2"


class TestChartDiscoveryTools:
    @pytest.fixture
    def mock_data_root(self, tmp_path):
        emissions_dir = tmp_path / "emissions"
        emissions_dir.mkdir()
        
        csv_content = """sector,val,scen
Power,-100,ScenA
Industry,-50,ScenA
"""
        (emissions_dir / "emissions_reduction.csv").write_text(csv_content)
        (emissions_dir / "emissions_reduction.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        
        (emissions_dir / "emissions_by_year.csv").write_text("scen,2025,2030\nA,100,80")
        
        economy_dir = tmp_path / "economy"
        economy_dir.mkdir()
        (economy_dir / "gdp_growth.csv").write_text("year,value\n2025,100")
        
        spec_content = """{
    "title": "Emissions Reduction",
    "si_unit": "Mt CO2-e",
    "groupby": ["scen", "sector"]
}"""
        (tmp_path / "plot_specs.json").write_text(spec_content)
        
        return tmp_path

    @pytest.fixture
    def tools(self, mock_data_root, tmp_path):
        return ReportAgentTools(tmp_path / "outline.md", mock_data_root)

    def test_list_chart_categories(self, tools):
        result = tools.execute_tool("list_chart_categories", {})
        
        assert isinstance(result, list)
        assert len(result) == 2
        
        categories = {c["id"]: c["chart_count"] for c in result}
        assert "emissions" in categories
        assert "economy" in categories
        assert categories["emissions"] == 2
        assert categories["economy"] == 1

    def test_list_charts_all(self, tools):
        result = tools.execute_tool("list_charts", {})
        
        assert isinstance(result, list)
        assert len(result) == 3
        
        for chart in result:
            assert "id" in chart
            assert "title" in chart
            assert "category" in chart
            assert "units" in chart

    def test_list_charts_by_category(self, tools):
        result = tools.execute_tool("list_charts", {"category": "emissions"})
        
        assert len(result) == 2
        for chart in result:
            assert chart["category"] == "emissions"

    def test_list_charts_empty_category(self, tools):
        result = tools.execute_tool("list_charts", {"category": "nonexistent"})
        assert result == []

    def test_get_chart_metadata(self, tools):
        result = tools.execute_tool("get_chart_metadata", {"chart_id": "emissions_reduction"})
        
        assert result["id"] == "emissions_reduction"
        assert result["category"] == "emissions"
        assert result["title"] == "Emissions Reduction"
        assert "path_csv" in result
        assert "dimensions" in result
        assert "measures" in result

    def test_get_chart_metadata_not_found(self, tools):
        result = tools.execute_tool("get_chart_metadata", {"chart_id": "nonexistent"})
        assert "error" in result


class TestChartDataTools:
    @pytest.fixture
    def mock_data_root(self, tmp_path):
        emissions_dir = tmp_path / "emissions"
        emissions_dir.mkdir()
        
        csv_content = """sector,val,scen
Net 2025,401.05,ScenA
Power,-128.92,ScenA
Industry,-109.74,ScenA
Net 2025,401.05,ScenB
Power,-100.00,ScenB
"""
        (emissions_dir / "chart1.csv").write_text(csv_content)
        
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"
        (emissions_dir / "chart1.png").write_bytes(png_data)
        
        (tmp_path / "plot_specs.json").write_text('{"title": "Chart 1", "si_unit": "Mt"}')
        
        return tmp_path

    @pytest.fixture
    def tools(self, mock_data_root, tmp_path):
        return ReportAgentTools(tmp_path / "outline.md", mock_data_root)

    def test_get_chart_data_basic(self, tools):
        result = tools.execute_tool("get_chart_data", {"chart_id": "chart1"})
        
        assert result["chart_id"] == "chart1"
        assert "title" in result
        assert "dimensions" in result
        assert "measure" in result
        assert "scenarios" in result
        assert "years" in result
        assert "row_count" in result
        assert "by_scenario" in result
        assert "key_insights" in result
        
        assert result["row_count"] == 5
        assert "ScenA" in result["scenarios"]
        assert "ScenB" in result["scenarios"]

    def test_get_chart_data_with_rows(self, tools):
        result = tools.execute_tool("get_chart_data", {
            "chart_id": "chart1",
            "include_rows": True
        })
        
        assert "rows" in result
        assert len(result["rows"]) == 5
        assert result["rows"][0]["sector"] == "Net 2025"

    def test_get_chart_data_without_rows(self, tools):
        result = tools.execute_tool("get_chart_data", {
            "chart_id": "chart1",
            "include_rows": False
        })
        
        assert "rows" not in result

    def test_get_chart_data_not_found(self, tools):
        result = tools.execute_tool("get_chart_data", {"chart_id": "nonexistent"})
        assert "error" in result

    def test_get_chart_image(self, tools):
        result = tools.execute_tool("get_chart_image", {"chart_id": "chart1"})
        
        assert result["chart_id"] == "chart1"
        assert result["format"] == "png"
        assert "image_base64" in result
        assert len(result["image_base64"]) > 0

    def test_get_chart_image_not_found(self, tools):
        result = tools.execute_tool("get_chart_image", {"chart_id": "nonexistent"})
        assert "error" in result


class TestExecuteToolErrors:
    @pytest.fixture
    def tools(self, tmp_path):
        return ReportAgentTools(tmp_path / "outline.md", tmp_path / "data")

    def test_unknown_tool(self, tools):
        result = tools.execute_tool("unknown_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_missing_required_argument(self, tools):
        result = tools.execute_tool("get_section_context", {})
        assert "error" in result


class TestRealDataIntegration:
    def test_with_real_data(self):
        data_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "data"
            / "example-outputs"
            / "ampol2025"
            / "2025-12-03T10.20_Ampol.2025-12-03T10.36_all"
        )
        outline_path = data_path.parent / "outline.md"
        
        if not data_path.exists():
            pytest.skip("Example data directory not found")
        
        tools = ReportAgentTools(outline_path, data_path)
        
        categories = tools.execute_tool("list_chart_categories", {})
        assert len(categories) > 0
        
        charts = tools.execute_tool("list_charts", {})
        assert len(charts) > 0
        
        if charts:
            chart_id = charts[0]["id"]
            data = tools.execute_tool("get_chart_data", {"chart_id": chart_id})
            assert "error" not in data or data.get("row_count", 0) > 0
