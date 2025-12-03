import json
import pytest
from pathlib import Path

from report_agent.data_catalog import DataCatalog, ChartMeta
from report_agent.outline_parser import Section
from report_agent.section_mapper import (
    SectionMapper,
    SectionMapping,
    get_section_keywords,
    CATEGORY_ALIASES,
)


class TestGetSectionKeywords:
    def test_basic_extraction(self):
        section = Section(
            id="emissions",
            title="Emissions Overview",
            level=1,
            instructions="Discuss carbon emissions trends",
            review_comments="",
            review_ratings={},
            review_notes="",
            parent_id=None,
            content="",
        )
        keywords = get_section_keywords(section)
        assert "emissions" in keywords
        assert "carbon" in keywords
        assert "trends" in keywords

    def test_stopwords_removed(self):
        section = Section(
            id="test",
            title="The Main Overview",
            level=1,
            instructions="This is a section about the analysis",
            review_comments="",
            review_ratings={},
            review_notes="",
            parent_id=None,
            content="",
        )
        keywords = get_section_keywords(section)
        assert "the" not in keywords
        assert "this" not in keywords
        assert "about" not in keywords
        assert "section" not in keywords

    def test_short_words_removed(self):
        section = Section(
            id="test",
            title="CO2 in Air",
            level=1,
            instructions="",
            review_comments="",
            review_ratings={},
            review_notes="",
            parent_id=None,
            content="",
        )
        keywords = get_section_keywords(section)
        assert "in" not in keywords
        assert "co2" in keywords
        assert "air" in keywords


class TestSectionMapping:
    def test_dataclass(self):
        mapping = SectionMapping(charts=["chart1", "chart2"], description="Test mapping")
        assert mapping.charts == ["chart1", "chart2"]
        assert mapping.description == "Test mapping"

    def test_default_description(self):
        mapping = SectionMapping(charts=["chart1"])
        assert mapping.description == ""


class TestSectionMapperWithMockData:
    @pytest.fixture
    def mock_data_root(self, tmp_path):
        (tmp_path / "emissions").mkdir()
        (tmp_path / "transport").mkdir()
        (tmp_path / "electricity").mkdir()
        (tmp_path / "built_environment").mkdir()
        (tmp_path / "agriculture").mkdir()

        (tmp_path / "emissions" / "emissions_reduction_by_sector.csv").write_text("data")
        (tmp_path / "emissions" / "emissions_from_electricity_generation.csv").write_text("data")
        (tmp_path / "emissions" / "total_emissions.csv").write_text("data")

        (tmp_path / "transport" / "domestic_transport_energy_use_by_fuel.csv").write_text("data")
        (tmp_path / "transport" / "road_transport_energy_use_by_fuel.csv").write_text("data")
        (tmp_path / "transport" / "vehicle_fleet.csv").write_text("data")

        (tmp_path / "electricity" / "electricity_generation_by_source.csv").write_text("data")
        (tmp_path / "electricity" / "electricity_capacity.csv").write_text("data")

        (tmp_path / "built_environment" / "residential_energy_use.csv").write_text("data")
        (tmp_path / "built_environment" / "commercial_energy_use.csv").write_text("data")
        (tmp_path / "built_environment" / "building_efficiency.csv").write_text("data")

        (tmp_path / "agriculture" / "agricultural_emissions.csv").write_text("data")

        return tmp_path

    @pytest.fixture
    def catalog(self, mock_data_root):
        return DataCatalog(mock_data_root)

    @pytest.fixture
    def mapping_file(self, tmp_path):
        mapping_data = {
            "emissions": {
                "charts": ["emissions_reduction_by_sector", "emissions_from_electricity_generation"],
                "description": "Overview of emissions projections",
            },
            "transport": {
                "charts": ["domestic_transport_energy_use_by_fuel", "road_transport_energy_use_by_fuel"],
                "description": "Transport sector energy",
            },
        }
        mapping_path = tmp_path / "section_chart_map.json"
        mapping_path.write_text(json.dumps(mapping_data))
        return mapping_path


class TestSectionMapperStaticMappings(TestSectionMapperWithMockData):
    def test_load_static_mappings(self, catalog, mapping_file):
        mapper = SectionMapper(catalog, mapping_file)
        mappings = mapper.get_all_mappings()
        assert "emissions" in mappings
        assert "transport" in mappings
        assert len(mappings["emissions"]) == 2

    def test_get_charts_for_section_static(self, catalog, mapping_file):
        mapper = SectionMapper(catalog, mapping_file)
        charts = mapper.get_charts_for_section("emissions")
        assert len(charts) == 2
        chart_ids = [c.id for c in charts]
        assert "emissions_reduction_by_sector" in chart_ids
        assert "emissions_from_electricity_generation" in chart_ids

    def test_static_mapping_missing_chart(self, catalog, tmp_path):
        mapping_data = {
            "test": {
                "charts": ["nonexistent_chart", "emissions_reduction_by_sector"],
                "description": "Test",
            }
        }
        mapping_path = tmp_path / "mapping.json"
        mapping_path.write_text(json.dumps(mapping_data))

        mapper = SectionMapper(catalog, mapping_path)
        charts = mapper.get_charts_for_section("test")
        assert len(charts) == 1
        assert charts[0].id == "emissions_reduction_by_sector"

    def test_no_mapping_file(self, catalog):
        mapper = SectionMapper(catalog, None)
        mappings = mapper.get_all_mappings()
        assert mappings == {}


class TestSectionMapperAutoMapping(TestSectionMapperWithMockData):
    def test_auto_map_by_category_name(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("emissions")
        chart_ids = [c.id for c in charts]
        assert any("emissions" in cid for cid in chart_ids)

    def test_auto_map_transport_section(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("transport")
        assert len(charts) > 0
        categories = [c.category for c in charts]
        assert "transport" in categories

    def test_auto_map_electricity_section(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("electricity-generation")
        chart_ids = [c.id for c in charts]
        assert any("electricity" in cid for cid in chart_ids)

    def test_auto_map_residential_section(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("residential")
        chart_ids = [c.id for c in charts]
        assert any("residential" in cid for cid in chart_ids)

    def test_auto_map_commercial_section(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("commercial")
        chart_ids = [c.id for c in charts]
        assert any("commercial" in cid for cid in chart_ids)

    def test_auto_map_agriculture_section(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("agriculture")
        assert len(charts) > 0
        chart_ids = [c.id for c in charts]
        assert any("agricultural" in cid or "agriculture" in cid for cid in chart_ids)

    def test_auto_map_returns_max_five(self, catalog):
        mapper = SectionMapper(catalog, None)
        charts = mapper.get_charts_for_section("energy")
        assert len(charts) <= 5

    def test_fallback_when_section_not_in_static(self, catalog, mapping_file):
        mapper = SectionMapper(catalog, mapping_file)
        charts = mapper.get_charts_for_section("electricity-generation")
        assert len(charts) > 0


class TestSectionMapperWithSectionObject(TestSectionMapperWithMockData):
    def test_get_charts_for_section_obj(self, catalog):
        mapper = SectionMapper(catalog, None)
        section = Section(
            id="transport-overview",
            title="Transport Sector Overview",
            level=1,
            instructions="Analyze transport energy use by fuel type",
            review_comments="",
            review_ratings={},
            review_notes="",
            parent_id=None,
            content="",
        )
        charts = mapper.get_charts_for_section_obj(section)
        assert len(charts) > 0
        chart_ids = [c.id for c in charts]
        assert any("transport" in cid for cid in chart_ids)

    def test_section_obj_uses_instructions(self, catalog):
        mapper = SectionMapper(catalog, None)
        section = Section(
            id="energy-analysis",
            title="Energy Analysis",
            level=1,
            instructions="Focus on residential building energy consumption patterns",
            review_comments="",
            review_ratings={},
            review_notes="",
            parent_id=None,
            content="",
        )
        charts = mapper.get_charts_for_section_obj(section)
        chart_ids = [c.id for c in charts]
        assert any("residential" in cid for cid in chart_ids)


class TestCategoryAliases:
    def test_emissions_alias(self):
        assert "emissions" in CATEGORY_ALIASES
        assert "emissions" in CATEGORY_ALIASES["emissions"]

    def test_residential_maps_to_built_environment(self):
        assert "residential" in CATEGORY_ALIASES
        assert "built_environment" in CATEGORY_ALIASES["residential"]

    def test_commercial_maps_to_built_environment(self):
        assert "commercial" in CATEGORY_ALIASES
        assert "built_environment" in CATEGORY_ALIASES["commercial"]

    def test_industry_maps_to_manufacturing(self):
        assert "industry" in CATEGORY_ALIASES
        assert "manufacturing" in CATEGORY_ALIASES["industry"]


class TestSectionMapperInvalidMapping:
    @pytest.fixture
    def catalog(self, tmp_path):
        (tmp_path / "emissions").mkdir()
        (tmp_path / "emissions" / "test.csv").write_text("data")
        return DataCatalog(tmp_path)

    def test_invalid_json(self, catalog, tmp_path):
        mapping_path = tmp_path / "invalid.json"
        mapping_path.write_text("not valid json")
        mapper = SectionMapper(catalog, mapping_path)
        assert mapper.get_all_mappings() == {}

    def test_nonexistent_mapping_file(self, catalog, tmp_path):
        mapper = SectionMapper(catalog, tmp_path / "nonexistent.json")
        assert mapper.get_all_mappings() == {}
