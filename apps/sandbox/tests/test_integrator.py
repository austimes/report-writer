"""Tests for the report integrator."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from report_agent.integrator import (
    ReportIntegrator,
    IntegrationResult,
    UsageCost,
    REPORT_STATE_UPDATE_PATTERN,
)
from report_agent.report_state import ReportState, CanonicalFigure
from report_agent.outline_parser import Section


def make_section(id: str, title: str, level: int = 1, content: str = "") -> Section:
    """Helper to create Section objects for tests."""
    return Section(
        id=id,
        title=title,
        level=level,
        instructions="",
        review_comments="",
        review_author="",
        review_ratings={},
        review_notes="",
        parent_id=None,
        content=content,
    )


class TestReportStateUpdatePattern:
    """Tests for the REPORT_STATE_UPDATE regex pattern."""
    
    def test_matches_valid_block(self):
        content = '''Some content before

<!-- REPORT_STATE_UPDATE
{
  "report_id": "test",
  "figures": []
}
-->

Some content after'''
        
        match = REPORT_STATE_UPDATE_PATTERN.search(content)
        assert match is not None
        assert '"report_id": "test"' in match.group(1)
    
    def test_no_match_without_block(self):
        content = "Just regular content without any special blocks"
        match = REPORT_STATE_UPDATE_PATTERN.search(content)
        assert match is None


class TestIntegratorPromptBuilding:
    """Tests for building integration prompts."""
    
    def test_build_prompt_includes_section_count(self):
        integrator = ReportIntegrator(dry_run=True)
        state = ReportState.new("test-report")
        sections = [
            make_section("intro", "Introduction"),
            make_section("results", "Results"),
        ]
        
        prompt = integrator._build_integration_prompt(
            "# Report\nContent here",
            state,
            sections,
        )
        
        assert "2 sections" in prompt
    
    def test_build_prompt_includes_report_state(self):
        integrator = ReportIntegrator(dry_run=True)
        state = ReportState.new("my-report")
        state.register_figure("throughput", "results", "Throughput chart")
        
        prompt = integrator._build_integration_prompt(
            "# Report",
            state,
            [],
        )
        
        assert "my-report" in prompt
        assert "throughput" in prompt
    
    def test_build_prompt_includes_report_content(self):
        integrator = ReportIntegrator(dry_run=True)
        state = ReportState.new("test")
        
        report_content = "# My Report\n\nThis is the full report content."
        prompt = integrator._build_integration_prompt(
            report_content,
            state,
            [],
        )
        
        assert "This is the full report content." in prompt


class TestIntegratorResponseParsing:
    """Tests for parsing integration responses."""
    
    def test_parse_response_extracts_state_update(self):
        integrator = ReportIntegrator(dry_run=True)
        original_state = ReportState.new("test")
        
        response = '''# Integrated Report

Some integrated content here.

<!-- REPORT_STATE_UPDATE
{
  "report_id": "test",
  "figures": [
    {
      "id": "F1",
      "semantic_key": "throughput",
      "owner_section": "results",
      "caption": "Throughput chart"
    }
  ],
  "tables": [],
  "section_meta": {}
}
-->'''
        
        content, state = integrator._parse_integration_response(response, original_state)
        
        assert "<!-- REPORT_STATE_UPDATE" not in content
        assert "Some integrated content here." in content
        assert len(state.figures) == 1
        assert state.figures[0].id == "F1"
    
    def test_parse_response_preserves_original_state_on_missing_block(self):
        integrator = ReportIntegrator(dry_run=True)
        original_state = ReportState.new("test")
        original_state.register_figure("existing", "intro", "Existing figure")
        
        response = "# Just content without state update block"
        
        content, state = integrator._parse_integration_response(response, original_state)
        
        assert content == response
        assert len(state.figures) == 1
        assert state.figures[0].semantic_key == "existing"
    
    def test_parse_response_handles_invalid_json(self):
        integrator = ReportIntegrator(dry_run=True)
        original_state = ReportState.new("test")
        
        response = '''Content

<!-- REPORT_STATE_UPDATE
{ invalid json here }
-->'''
        
        content, state = integrator._parse_integration_response(response, original_state)
        
        assert state.report_id == "test"


class TestIntegratorValidation:
    """Tests for change validation."""
    
    def test_validate_changes_passes_small_changes(self):
        integrator = ReportIntegrator(dry_run=True)
        
        original = "The quick brown fox jumps over the lazy dog."
        integrated = "The quick brown fox leaps over the lazy dog."
        
        is_valid, message = integrator._validate_changes(original, integrated, 0.3)
        
        assert is_valid is True
        assert "within bounds" in message
    
    def test_validate_changes_fails_large_changes(self):
        integrator = ReportIntegrator(dry_run=True)
        
        original = "The quick brown fox jumps over the lazy dog."
        integrated = "Completely different content that shares nothing."
        
        is_valid, message = integrator._validate_changes(original, integrated, 0.3)
        
        assert is_valid is False
        assert "exceed" in message
    
    def test_validate_changes_identical_content(self):
        integrator = ReportIntegrator(dry_run=True)
        
        content = "Same content in both."
        
        is_valid, message = integrator._validate_changes(content, content, 0.3)
        
        assert is_valid is True
        assert "0.0%" in message


class TestIntegratorDryRun:
    """Tests for dry run mode."""
    
    def test_dry_run_returns_original_content(self):
        integrator = ReportIntegrator(dry_run=True)
        state = ReportState.new("test")
        sections = [make_section("intro", "Intro")]
        
        result = integrator.integrate(
            "# Original content",
            state,
            sections,
        )
        
        assert result.integrated_content == "# Original content"
        assert result.duplicates_removed == 0
        assert result.validation_passed is True
        assert "Dry run" in result.validation_message


class TestIntegratorSectionDetection:
    """Tests for detecting modified sections."""
    
    def test_detect_modified_sections(self):
        integrator = ReportIntegrator(dry_run=True)
        
        original = '''<!-- BEGIN SECTION: intro (Introduction) -->
# Introduction
Original intro content.
<!-- END SECTION: intro -->

<!-- BEGIN SECTION: results (Results) -->
# Results
Original results.
<!-- END SECTION: results -->'''
        
        integrated = '''<!-- BEGIN SECTION: intro (Introduction) -->
# Introduction
Modified intro content with cross-refs.
<!-- END SECTION: intro -->

<!-- BEGIN SECTION: results (Results) -->
# Results
Original results.
<!-- END SECTION: results -->'''
        
        sections = [
            make_section("intro", "Introduction"),
            make_section("results", "Results"),
        ]
        
        modified = integrator._detect_modified_sections(original, integrated, sections)
        
        assert "intro" in modified
        assert "results" not in modified
    
    def test_extract_section_content(self):
        integrator = ReportIntegrator(dry_run=True)
        
        content = '''<!-- BEGIN SECTION: intro (Introduction) -->
# Introduction
This is the intro content.
<!-- END SECTION: intro -->'''
        
        extracted = integrator._extract_section_content(content, "intro")
        
        assert "# Introduction" in extracted
        assert "This is the intro content." in extracted


class TestIntegratorPatternCounting:
    """Tests for counting pattern changes."""
    
    def test_count_removed_figures(self):
        integrator = ReportIntegrator(dry_run=True)
        
        original = '''
![Chart 1](figures/chart1.png)
![Chart 2](figures/chart2.png)
![Chart 3](figures/chart3.png)
'''
        
        integrated = '''
![Chart 1](figures/chart1.png)
See Figure 1 above for chart 2 data.
![Chart 3](figures/chart3.png)
'''
        
        removed = integrator._count_pattern_changes(
            original, integrated, r'!\[.*?\]\(figures/.*?\)'
        )
        
        assert removed == 1
