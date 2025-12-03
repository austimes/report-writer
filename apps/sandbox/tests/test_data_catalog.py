import pytest
from pathlib import Path
from report_agent.data_catalog import DataCatalog, ChartMeta, _id_to_title


class TestIdToTitle:
    def test_simple_id(self):
        assert _id_to_title("emissions") == "Emissions"

    def test_underscores(self):
        assert _id_to_title("emissions_reduction_by_sector") == "Emissions Reduction By Sector"

    def test_multiple_underscores(self):
        assert _id_to_title("total_energy_consumption") == "Total Energy Consumption"


class TestChartMeta:
    def test_defaults(self):
        chart = ChartMeta(id="test", category="emissions", title="Test Chart")
        assert chart.id == "test"
        assert chart.category == "emissions"
        assert chart.title == "Test Chart"
        assert chart.path_csv is None
        assert chart.path_png is None
        assert chart.path_json is None
        assert chart.dimensions == []
        assert chart.measures == ["val"]
        assert chart.units == ""
        assert chart.filter_expression == ""
        assert chart.scenarios == []

    def test_with_paths(self):
        chart = ChartMeta(
            id="test",
            category="emissions",
            title="Test",
            path_csv=Path("/data/test.csv"),
            path_png=Path("/data/test.png"),
        )
        assert chart.path_csv == Path("/data/test.csv")
        assert chart.path_png == Path("/data/test.png")


class TestDataCatalogWithMockData:
    @pytest.fixture
    def mock_data_root(self, tmp_path):
        (tmp_path / "emissions").mkdir()
        (tmp_path / "transport").mkdir()

        (tmp_path / "emissions" / "total_emissions.csv").write_text("scen,year,val\nA,2025,100")
        (tmp_path / "emissions" / "total_emissions.png").write_bytes(b"PNG")
        (tmp_path / "emissions" / "total_emissions.json").write_text("{}")

        (tmp_path / "emissions" / "emissions_by_sector.csv").write_text("scen,year,val\nA,2025,50")

        (tmp_path / "transport" / "vehicle_fleet.csv").write_text("scen,year,val\nA,2025,200")
        (tmp_path / "transport" / "vehicle_fleet.png").write_bytes(b"PNG")

        specs = [
            {
                "title": "Total Emissions",
                "filter": "varbl == 'emissions'",
                "groupby": ["scen", "year", "unit", "sector"],
                "category": "emissions",
                "si_unit": "Mt CO2-e",
            },
            {
                "title": "Vehicle Fleet",
                "filter": "varbl == 'fleet'",
                "groupby": ["scen", "year", "vehicle_type"],
                "category": "transport",
                "si_unit": "million vehicles",
            },
        ]
        json_parts = ["{" + "\n" + "}\n{".join([__import__("json").dumps(s, indent=4)[1:-1] for s in specs]) + "\n" + "}"]
        content = "{\n" + "}\n{".join([__import__("json").dumps(s, indent=4)[1:-1] for s in specs]) + "\n}"
        (tmp_path / "plot_specs.json").write_text(content)

        return tmp_path

    def test_list_categories(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        categories = catalog.list_categories()
        assert "emissions" in categories
        assert "transport" in categories
        assert len(categories) == 2

    def test_list_all_charts(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        charts = catalog.list_charts()
        assert len(charts) == 3

    def test_list_charts_by_category(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        emissions_charts = catalog.list_charts("emissions")
        assert len(emissions_charts) == 2
        assert all(c.category == "emissions" for c in emissions_charts)

    def test_get_chart(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        chart = catalog.get_chart("total_emissions")
        assert chart is not None
        assert chart.id == "total_emissions"
        assert chart.category == "emissions"
        assert chart.title == "Total Emissions"
        assert chart.path_csv is not None
        assert chart.path_png is not None
        assert chart.path_json is not None
        assert chart.units == "Mt CO2-e"
        assert "sector" in chart.dimensions
        assert chart.filter_expression == "varbl == 'emissions'"

    def test_get_chart_not_found(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        chart = catalog.get_chart("nonexistent")
        assert chart is None

    def test_chart_without_spec(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        chart = catalog.get_chart("emissions_by_sector")
        assert chart is not None
        assert chart.title == "Emissions By Sector"
        assert chart.units == ""
        assert chart.dimensions == []

    def test_partial_files(self, mock_data_root):
        catalog = DataCatalog(mock_data_root)
        chart = catalog.get_chart("vehicle_fleet")
        assert chart is not None
        assert chart.path_csv is not None
        assert chart.path_png is not None
        assert chart.path_json is None


class TestDataCatalogEmptyRoot:
    def test_nonexistent_root(self, tmp_path):
        catalog = DataCatalog(tmp_path / "nonexistent")
        assert catalog.list_categories() == []
        assert catalog.list_charts() == []

    def test_empty_root(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        assert catalog.list_categories() == []
        assert catalog.list_charts() == []

    def test_no_plot_specs(self, tmp_path):
        (tmp_path / "emissions").mkdir()
        (tmp_path / "emissions" / "test.csv").write_text("data")
        catalog = DataCatalog(tmp_path)
        assert len(catalog.list_charts()) == 1
        chart = catalog.get_chart("test")
        assert chart.title == "Test"


class TestDataCatalogSubfolderDiscovery:
    @pytest.fixture
    def nested_data_root(self, tmp_path):
        """Create a nested structure like ampol2025 with export subfolder."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        (project_root / "report-outline.md").write_text("# Report Outline")
        (project_root / "section_chart_map.json").write_text("{}")

        export_folder = project_root / "2025-01-01_Export"
        export_folder.mkdir()

        (export_folder / "emissions").mkdir()
        (export_folder / "emissions" / "total_emissions.csv").write_text("scen,year,val\nA,2025,100")
        (export_folder / "emissions" / "total_emissions.png").write_bytes(b"PNG")

        specs = [{"title": "Total Emissions", "si_unit": "Mt CO2-e", "groupby": ["scen", "year"]}]
        content = "{\n" + "}\n{".join([__import__("json").dumps(s, indent=4)[1:-1] for s in specs]) + "\n}"
        (export_folder / "plot_specs.json").write_text(content)

        return project_root, export_folder

    def test_discovers_subfolder_with_plot_specs(self, nested_data_root):
        project_root, export_folder = nested_data_root
        catalog = DataCatalog(project_root)
        assert catalog.data_root == export_folder
        assert len(catalog.list_categories()) > 0
        assert "emissions" in catalog.list_categories()

    def test_direct_export_folder_still_works(self, nested_data_root):
        project_root, export_folder = nested_data_root
        catalog = DataCatalog(export_folder)
        assert catalog.data_root == export_folder
        assert "emissions" in catalog.list_categories()

    def test_finds_charts_from_parent_folder(self, nested_data_root):
        project_root, export_folder = nested_data_root
        catalog = DataCatalog(project_root)
        charts = catalog.list_charts()
        assert len(charts) == 1
        assert charts[0].id == "total_emissions"
        assert charts[0].title == "Total Emissions"

    def test_no_subfolder_with_plot_specs_uses_original(self, tmp_path):
        """If no subfolder has plot_specs.json, use original root."""
        (tmp_path / "emissions").mkdir()
        (tmp_path / "emissions" / "test.csv").write_text("data")
        catalog = DataCatalog(tmp_path)
        assert catalog.data_root == tmp_path
        assert len(catalog.list_charts()) == 1


class TestDataCatalogRealData:
    def test_real_data_directory_direct(self):
        """Test with direct path to export folder."""
        data_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "example-outputs" / "ampol2025" / "2025-12-03T10.20_Ampol.2025-12-03T10.36_all"
        if not data_path.exists():
            pytest.skip("Example data directory not found")

        catalog = DataCatalog(data_path)

        categories = catalog.list_categories()
        assert len(categories) > 0
        assert "emissions" in categories

        emissions_charts = catalog.list_charts("emissions")
        assert len(emissions_charts) > 0

        chart = emissions_charts[0]
        assert chart.category == "emissions"
        assert chart.path_csv is not None or chart.path_png is not None

        all_charts = catalog.list_charts()
        assert len(all_charts) > 0

    def test_real_data_directory_parent(self):
        """Test with parent folder (ampol2025) - should discover subfolder."""
        data_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "example-outputs" / "ampol2025"
        export_path = data_path / "2025-12-03T10.20_Ampol.2025-12-03T10.36_all"
        if not export_path.exists():
            pytest.skip("Example data directory not found")

        catalog = DataCatalog(data_path)

        assert catalog.data_root == export_path

        categories = catalog.list_categories()
        assert len(categories) > 0
        assert "emissions" in categories

        all_charts = catalog.list_charts()
        assert len(all_charts) > 0
