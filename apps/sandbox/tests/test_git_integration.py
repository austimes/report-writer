"""Tests for git integration and change journal."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from report_agent.git_integration import (
    require_executable,
    run_git,
    run_gh,
    load_report_meta,
    ensure_report_project,
    auto_commit,
    init_repo,
    REPORT_META_FILENAME,
    GITHUB_ORG,
)
from report_agent.change_journal import (
    JournalEntry,
    get_journal_dir,
    create_entry,
    save_entry,
    update_entry,
    load_entry,
    list_entries,
    format_entry_for_commit,
)
from report_agent.cli import app

runner = CliRunner()


class TestRequireExecutable:
    def test_require_executable_exists(self):
        with patch("shutil.which", return_value="/usr/bin/git"):
            require_executable("git")

    def test_require_executable_missing(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="not found on PATH"):
                require_executable("nonexistent-tool")


class TestLoadReportMeta:
    def test_load_report_meta_success(self, tmp_path: Path):
        meta = {"report_name": "Test Report", "slug": "test-report"}
        meta_path = tmp_path / REPORT_META_FILENAME
        meta_path.write_text(json.dumps(meta))

        result = load_report_meta(tmp_path)
        assert result == meta

    def test_load_report_meta_missing(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match="not found"):
            load_report_meta(tmp_path)

    def test_load_report_meta_invalid_json(self, tmp_path: Path):
        meta_path = tmp_path / REPORT_META_FILENAME
        meta_path.write_text("{ invalid json }")

        with pytest.raises(RuntimeError, match="Invalid JSON"):
            load_report_meta(tmp_path)


class TestEnsureReportProject:
    def test_ensure_report_project_success(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        meta = {"report_name": "Test Report", "slug": "test-report"}
        (tmp_path / REPORT_META_FILENAME).write_text(json.dumps(meta))

        result = ensure_report_project(tmp_path)
        assert result == meta

    def test_ensure_report_project_no_git(self, tmp_path: Path):
        meta = {"report_name": "Test Report", "slug": "test-report"}
        (tmp_path / REPORT_META_FILENAME).write_text(json.dumps(meta))

        with pytest.raises(RuntimeError, match="Not a git repository"):
            ensure_report_project(tmp_path)

    def test_ensure_report_project_no_meta(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()

        with pytest.raises(RuntimeError, match="not found"):
            ensure_report_project(tmp_path)

    def test_ensure_report_project_not_exists(self, tmp_path: Path):
        missing_path = tmp_path / "nonexistent"

        with pytest.raises(RuntimeError, match="does not exist"):
            ensure_report_project(missing_path)


class TestChangeJournal:
    def test_create_entry(self):
        entry = create_entry(
            command="generate-section",
            arguments={"section": "emissions"},
            model="claude-3",
            sections_affected=["emissions"],
        )

        assert entry.id
        assert len(entry.id) == 36  # UUID format
        assert entry.timestamp
        assert entry.command == "generate-section"
        assert entry.arguments == {"section": "emissions"}
        assert entry.model == "claude-3"
        assert entry.sections_affected == ["emissions"]
        assert entry.success is True

    def test_save_and_load_entry(self, tmp_path: Path):
        entry = create_entry(
            command="generate-section",
            arguments={"section": "emissions", "dry_run": False},
            model="claude-3",
            thinking_level="medium",
            sections_affected=["emissions"],
        )

        path = save_entry(tmp_path, entry)
        assert path.exists()

        loaded = load_entry(path)
        assert loaded.id == entry.id
        assert loaded.timestamp == entry.timestamp
        assert loaded.command == entry.command
        assert loaded.arguments == entry.arguments
        assert loaded.model == entry.model
        assert loaded.thinking_level == entry.thinking_level
        assert loaded.sections_affected == entry.sections_affected

    def test_update_entry(self, tmp_path: Path):
        entry = create_entry(
            command="generate-section",
            arguments={"section": "emissions"},
        )
        save_entry(tmp_path, entry)

        update_entry(
            tmp_path,
            entry,
            success=True,
            cost_usd=0.05,
            duration_seconds=12.5,
        )

        assert entry.success is True
        assert entry.cost_usd == 0.05
        assert entry.duration_seconds == 12.5

    def test_list_entries(self, tmp_path: Path):
        entries = []
        for i in range(3):
            entry = create_entry(
                command=f"command-{i}",
                arguments={"index": i},
            )
            save_entry(tmp_path, entry)
            entries.append(entry)

        listed = list_entries(tmp_path)
        assert len(listed) == 3
        assert listed[0].command == "command-2"
        assert listed[1].command == "command-1"
        assert listed[2].command == "command-0"

    def test_format_entry_for_commit(self):
        entry = create_entry(
            command="generate-section",
            arguments={"section": "emissions"},
            model="claude-3",
            thinking_level="high",
            sections_affected=["emissions"],
            review_notes="Good analysis of transport sector data.",
            review_author="reviewer@example.com",
        )
        entry.cost_usd = 0.0325
        entry.duration_seconds = 15.7

        formatted = format_entry_for_commit(entry)

        assert "Command: generate-section" in formatted
        assert f"Journal ID: {entry.id}" in formatted
        assert "Sections: emissions" in formatted
        assert "Model: claude-3" in formatted
        assert "Thinking: high" in formatted
        assert "Review notes: Good analysis" in formatted
        assert "Reviewer: reviewer@example.com" in formatted
        assert "Cost: $0.0325" in formatted
        assert "Duration: 15.7s" in formatted


class TestCLIIntegration:
    def test_init_report_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init-report" in result.output

    def test_generate_section_requires_init(self, tmp_path: Path):
        outline = tmp_path / "outline.md"
        outline.write_text("# Test\n## Section One\n")
        data_root = tmp_path / "data"
        data_root.mkdir()
        output_root = tmp_path / "output"
        output_root.mkdir()

        result = runner.invoke(
            app,
            [
                "generate-section",
                "--outline", str(outline),
                "--data-root", str(data_root),
                "--section", "section-one",
                "--output-root", str(output_root),
            ],
        )

        assert result.exit_code == 1
        assert "git" in result.output.lower() or "init" in result.output.lower()
