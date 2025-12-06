"""Tests for update-section functionality."""

import pytest
from pathlib import Path

from report_agent.orchestrator import ReportOrchestrator


class TestUpdateSection:
    """Tests for update_section orchestrator method."""

    def test_update_section_requires_existing_content(self, tmp_path):
        """update_section should raise if no existing section file."""
        # Create outline with empty section body (just heading, no content)
        outline = tmp_path / "outline.md"
        outline.write_text("# Introduction\n\n# Methods\n\nSome methods content.")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        output_root.mkdir()
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
            dry_run=True,
        )
        
        with pytest.raises(ValueError, match="No existing content"):
            orchestrator.update_section("introduction")

    def test_update_section_loads_existing_file(self, tmp_path):
        """update_section should use content from _sections/ file."""
        outline = tmp_path / "outline.md"
        outline.write_text("""# Introduction

<!-- Review comments:
AUTHOR: Alice
RATING: clarity=3
NOTES: Needs more detail on methodology.
-->
""")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        sections_dir = output_root / "_sections"
        sections_dir.mkdir(parents=True)
        
        # Write existing section file
        section_file = sections_dir / "01_introduction.md"
        section_file.write_text("# Introduction\n\nOriginal content here.")
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
            dry_run=True,
        )
        
        result = orchestrator.update_section("introduction")
        assert result.dry_run
        assert "Original content here" in result.prompt
        assert "Alice" in result.prompt
        assert "Needs more detail" in result.prompt


class TestBuildReportFromSections:
    """Tests for _build_report_from_sections."""

    def test_concatenates_section_files(self, tmp_path):
        """Should concatenate all section files in order."""
        outline = tmp_path / "outline.md"
        outline.write_text("# Intro\n\n# Methods\n\n# Results")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        sections_dir = output_root / "_sections"
        sections_dir.mkdir(parents=True)
        
        (sections_dir / "01_intro.md").write_text("# Intro\n\nIntro content.")
        (sections_dir / "02_methods.md").write_text("# Methods\n\nMethods content.")
        (sections_dir / "03_results.md").write_text("# Results\n\nResults content.")
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
        )
        
        report = orchestrator._build_report_from_sections()
        
        assert "BEGIN SECTION: intro" in report
        assert "Intro content" in report
        assert "Methods content" in report
        assert "Results content" in report
        assert "END SECTION" in report

    def test_handles_missing_sections(self, tmp_path):
        """Should insert placeholder for missing section files."""
        outline = tmp_path / "outline.md"
        outline.write_text("# Intro\n\n# Methods")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        sections_dir = output_root / "_sections"
        sections_dir.mkdir(parents=True)
        
        # Only create first section
        (sections_dir / "01_intro.md").write_text("# Intro\n\nContent.")
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
        )
        
        report = orchestrator._build_report_from_sections()
        
        assert "Intro" in report
        assert "SECTION MISSING: methods" in report


class TestLoadExistingSectionBody:
    """Tests for _load_existing_section_body."""

    def test_prefers_section_file_over_outline(self, tmp_path):
        """Should return content from _sections/ file if it exists."""
        outline = tmp_path / "outline.md"
        outline.write_text("# Intro\n\nOutline content.")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        sections_dir = output_root / "_sections"
        sections_dir.mkdir(parents=True)
        
        # Write different content to section file
        (sections_dir / "01_intro.md").write_text("# Intro\n\nSection file content.")
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
        )
        
        section = orchestrator.get_section("intro")
        body = orchestrator._load_existing_section_body(section)
        
        assert "Section file content" in body
        assert "Outline content" not in body

    def test_falls_back_to_outline_content(self, tmp_path):
        """Should return outline content if no section file exists."""
        outline = tmp_path / "outline.md"
        outline.write_text("# Intro\n\nOutline content here.")
        
        data_root = tmp_path / "data"
        data_root.mkdir()
        
        output_root = tmp_path / "output"
        output_root.mkdir()
        
        orchestrator = ReportOrchestrator(
            outline_path=outline,
            data_root=data_root,
            output_dir=output_root,
        )
        
        section = orchestrator.get_section("intro")
        body = orchestrator._load_existing_section_body(section)
        
        assert "Outline content here" in body


class TestHasExistingProject:
    """Tests for has_existing_project helper."""

    def test_detects_sections_directory(self, tmp_path):
        """Should return True if _sections/ has .md files."""
        from report_agent.cli import has_existing_project
        
        sections_dir = tmp_path / "_sections"
        sections_dir.mkdir()
        (sections_dir / "01_intro.md").write_text("content")
        
        assert has_existing_project(tmp_path) is True

    def test_detects_report_md(self, tmp_path):
        """Should return True if report.md exists."""
        from report_agent.cli import has_existing_project
        
        (tmp_path / "report.md").write_text("report content")
        
        assert has_existing_project(tmp_path) is True

    def test_returns_false_for_empty_directory(self, tmp_path):
        """Should return False for empty directory."""
        from report_agent.cli import has_existing_project
        
        assert has_existing_project(tmp_path) is False


class TestOutlineResolution:
    """Tests for outline resolution and copying helpers."""

    def test_get_outline_in_output_returns_none_if_missing(self, tmp_path):
        """Should return None if no outline.md in output."""
        from report_agent.cli import get_outline_in_output
        
        assert get_outline_in_output(tmp_path) is None

    def test_get_outline_in_output_returns_path_if_exists(self, tmp_path):
        """Should return path if outline.md exists."""
        from report_agent.cli import get_outline_in_output, OUTLINE_FILENAME
        
        outline = tmp_path / OUTLINE_FILENAME
        outline.write_text("# Intro")
        
        result = get_outline_in_output(tmp_path)
        assert result == outline

    def test_copy_outline_to_output(self, tmp_path):
        """Should copy outline file to output_root."""
        from report_agent.cli import copy_outline_to_output, OUTLINE_FILENAME
        
        source = tmp_path / "source_outline.md"
        source.write_text("# Intro\n\nSome content.")
        
        output_root = tmp_path / "output"
        dest = copy_outline_to_output(source, output_root)
        
        assert dest == output_root / OUTLINE_FILENAME
        assert dest.exists()
        assert dest.read_text() == source.read_text()

    def test_resolve_outline_prefers_output_root(self, tmp_path):
        """Should prefer outline in output_root over provided path."""
        from report_agent.cli import resolve_outline, OUTLINE_FILENAME
        from rich.console import Console
        
        source = tmp_path / "source_outline.md"
        source.write_text("# Source")
        
        output_root = tmp_path / "output"
        output_root.mkdir()
        output_outline = output_root / OUTLINE_FILENAME
        output_outline.write_text("# Output Version")
        
        console = Console(quiet=True)
        result = resolve_outline(source, output_root, console)
        
        assert result == output_outline

    def test_resolve_outline_falls_back_to_provided(self, tmp_path):
        """Should use provided outline if none in output_root."""
        from report_agent.cli import resolve_outline
        from rich.console import Console
        
        source = tmp_path / "source_outline.md"
        source.write_text("# Source")
        
        output_root = tmp_path / "output"
        output_root.mkdir()
        
        console = Console(quiet=True)
        result = resolve_outline(source, output_root, console)
        
        assert result == source

    def test_resolve_outline_returns_none_if_not_found(self, tmp_path):
        """Should return None if no outline found anywhere."""
        from report_agent.cli import resolve_outline
        from rich.console import Console
        
        output_root = tmp_path / "output"
        output_root.mkdir()
        
        console = Console(quiet=True)
        result = resolve_outline(None, output_root, console)
        
        assert result is None
