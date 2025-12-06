"""Tests for report state tracking."""

import json
import tempfile
from pathlib import Path

import pytest

from report_agent.report_state import (
    CanonicalFigure,
    CanonicalTable,
    ReportState,
    SectionStateMeta,
)


class TestReportStateNew:
    """Tests for creating new report state."""
    
    def test_new_creates_empty_state(self):
        state = ReportState.new("test-report")
        
        assert state.report_id == "test-report"
        assert state.figures == []
        assert state.tables == []
        assert state.section_meta == {}
        assert state.created_at != ""
        assert state.updated_at != ""
    
    def test_new_sets_timestamps(self):
        state = ReportState.new("test-report")
        
        assert state.created_at == state.updated_at


class TestReportStatePersistence:
    """Tests for loading and saving report state."""
    
    def test_save_and_load_roundtrip(self):
        state = ReportState.new("test-report")
        state.register_figure("throughput", "results", "Throughput chart", "chart-1")
        state.register_table("summary", "overview", "Summary table")
        state.get_section_meta("results").version = 3
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report_state.json"
            state.save(path)
            
            loaded = ReportState.load(path)
        
        assert loaded.report_id == "test-report"
        assert len(loaded.figures) == 1
        assert loaded.figures[0].semantic_key == "throughput"
        assert loaded.figures[0].chart_id == "chart-1"
        assert len(loaded.tables) == 1
        assert loaded.tables[0].semantic_key == "summary"
        assert loaded.section_meta["results"].version == 3
    
    def test_save_creates_parent_directories(self):
        state = ReportState.new("test-report")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "report_state.json"
            state.save(path)
            
            assert path.exists()
    
    def test_save_updates_updated_at(self):
        state = ReportState.new("test-report")
        original_updated = state.updated_at
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report_state.json"
            state.save(path)
        
        assert state.updated_at >= original_updated
    
    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ReportState.load(Path("/nonexistent/report_state.json"))
    
    def test_load_empty_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report_state.json"
            path.write_text(json.dumps({
                "report_id": "test",
                "figures": [],
                "tables": [],
                "section_meta": {},
            }))
            
            loaded = ReportState.load(path)
        
        assert loaded.figures == []
        assert loaded.tables == []


class TestFigureManagement:
    """Tests for figure registration and lookup."""
    
    def test_get_next_figure_id_empty(self):
        state = ReportState.new("test")
        assert state.get_next_figure_id() == "F1"
    
    def test_get_next_figure_id_sequential(self):
        state = ReportState.new("test")
        state.register_figure("fig1", "sec1", "First")
        state.register_figure("fig2", "sec1", "Second")
        
        assert state.get_next_figure_id() == "F3"
    
    def test_get_next_figure_id_with_gaps(self):
        state = ReportState.new("test")
        state.figures = [
            CanonicalFigure("F1", "a", "sec1", "A"),
            CanonicalFigure("F5", "b", "sec1", "B"),
        ]
        
        assert state.get_next_figure_id() == "F6"
    
    def test_register_figure(self):
        state = ReportState.new("test")
        
        fig = state.register_figure(
            semantic_key="throughput_over_time",
            owner_section="results",
            caption="Throughput vs time",
            chart_id="chart-xyz",
        )
        
        assert fig.id == "F1"
        assert fig.semantic_key == "throughput_over_time"
        assert fig.owner_section == "results"
        assert fig.caption == "Throughput vs time"
        assert fig.chart_id == "chart-xyz"
        assert fig in state.figures
    
    def test_find_figure_by_semantic_key(self):
        state = ReportState.new("test")
        state.register_figure("throughput", "results", "Throughput chart")
        state.register_figure("latency", "results", "Latency chart")
        
        found = state.find_figure_by_semantic_key("throughput")
        
        assert found is not None
        assert found.semantic_key == "throughput"
    
    def test_find_figure_by_semantic_key_not_found(self):
        state = ReportState.new("test")
        state.register_figure("throughput", "results", "Throughput chart")
        
        found = state.find_figure_by_semantic_key("nonexistent")
        
        assert found is None
    
    def test_find_figure_by_chart_id(self):
        state = ReportState.new("test")
        state.register_figure("throughput", "results", "Throughput", "chart-1")
        state.register_figure("latency", "results", "Latency", "chart-2")
        
        found = state.find_figure_by_chart_id("chart-2")
        
        assert found is not None
        assert found.semantic_key == "latency"
    
    def test_find_figure_by_chart_id_not_found(self):
        state = ReportState.new("test")
        
        found = state.find_figure_by_chart_id("nonexistent")
        
        assert found is None
    
    def test_get_figures_for_section(self):
        state = ReportState.new("test")
        state.register_figure("fig1", "results", "Result 1")
        state.register_figure("fig2", "results", "Result 2")
        state.register_figure("fig3", "overview", "Overview")
        
        result_figs = state.get_figures_for_section("results")
        
        assert len(result_figs) == 2
        assert all(f.owner_section == "results" for f in result_figs)
    
    def test_get_figures_not_owned_by(self):
        state = ReportState.new("test")
        state.register_figure("fig1", "results", "Result 1")
        state.register_figure("fig2", "overview", "Overview")
        state.register_figure("fig3", "methods", "Methods")
        
        other_figs = state.get_figures_not_owned_by("results")
        
        assert len(other_figs) == 2
        assert all(f.owner_section != "results" for f in other_figs)


class TestTableManagement:
    """Tests for table registration and lookup."""
    
    def test_get_next_table_id_empty(self):
        state = ReportState.new("test")
        assert state.get_next_table_id() == "T1"
    
    def test_get_next_table_id_sequential(self):
        state = ReportState.new("test")
        state.register_table("tbl1", "sec1", "First")
        state.register_table("tbl2", "sec1", "Second")
        
        assert state.get_next_table_id() == "T3"
    
    def test_register_table(self):
        state = ReportState.new("test")
        
        tbl = state.register_table(
            semantic_key="summary_stats",
            owner_section="overview",
            caption="Summary statistics",
        )
        
        assert tbl.id == "T1"
        assert tbl.semantic_key == "summary_stats"
        assert tbl.owner_section == "overview"
        assert tbl in state.tables
    
    def test_find_table_by_semantic_key(self):
        state = ReportState.new("test")
        state.register_table("summary", "overview", "Summary")
        state.register_table("details", "results", "Details")
        
        found = state.find_table_by_semantic_key("summary")
        
        assert found is not None
        assert found.semantic_key == "summary"
    
    def test_find_table_by_semantic_key_not_found(self):
        state = ReportState.new("test")
        
        found = state.find_table_by_semantic_key("nonexistent")
        
        assert found is None


class TestSectionMetaManagement:
    """Tests for section metadata tracking."""
    
    def test_get_section_meta_creates_new(self):
        state = ReportState.new("test")
        
        meta = state.get_section_meta("results")
        
        assert meta.section_id == "results"
        assert meta.version == 1
        assert meta.last_integrated_version == 0
        assert "results" in state.section_meta
    
    def test_get_section_meta_returns_existing(self):
        state = ReportState.new("test")
        state.section_meta["results"] = SectionStateMeta("results", version=5)
        
        meta = state.get_section_meta("results")
        
        assert meta.version == 5
    
    def test_increment_section_version(self):
        state = ReportState.new("test")
        
        v1 = state.increment_section_version("results")
        v2 = state.increment_section_version("results")
        
        assert v1 == 2
        assert v2 == 3
    
    def test_mark_section_integrated(self):
        state = ReportState.new("test")
        state.get_section_meta("results").version = 5
        
        state.mark_section_integrated("results")
        
        meta = state.get_section_meta("results")
        assert meta.last_integrated_version == 5
    
    def test_is_section_stale_new_section(self):
        state = ReportState.new("test")
        
        assert state.is_section_stale("results") is True
    
    def test_is_section_stale_after_integration(self):
        state = ReportState.new("test")
        state.mark_section_integrated("results")
        
        assert state.is_section_stale("results") is False
    
    def test_is_section_stale_after_modification(self):
        state = ReportState.new("test")
        state.mark_section_integrated("results")
        state.increment_section_version("results")
        
        assert state.is_section_stale("results") is True
