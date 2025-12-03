"""Tests for the Report Agent CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from report_agent.cli import app

runner = CliRunner()


@pytest.fixture
def sample_outline(tmp_path: Path) -> Path:
    """Create a sample outline file."""
    outline = tmp_path / "outline.md"
    outline.write_text(
        "# Projection results\n"
        "<!-- Section instructions: Provide an overview -->\n"
        "<!-- Review comments: -->\n"
        "\n"
        "## Emissions\n"
        "<!-- Section instructions: Describe emissions trends -->\n"
        "<!-- Review comments: RATING: accuracy=4, completeness=3\n"
        "NOTES: Good work on the emissions section. -->\n"
        "\n"
        "## Transport\n"
        "<!-- Section instructions: Analyze transport sector -->\n"
        "<!-- Review comments: -->\n"
    )
    return outline


@pytest.fixture
def sample_data_root(tmp_path: Path) -> Path:
    """Create a sample data directory."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    emissions = data_root / "emissions"
    emissions.mkdir()

    csv_content = "sector,scen,val\nTransport,BAU,100\nTransport,NetZero,-50\n"
    (emissions / "emissions_by_sector.csv").write_text(csv_content)

    return data_root


class TestGenerateSectionCommand:
    def test_missing_outline(self, tmp_path: Path, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "generate-section",
                "--outline", str(tmp_path / "missing.md"),
                "--data-root", str(sample_data_root),
                "--section", "emissions",
                "--output", str(tmp_path / "output.md"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_missing_data_root(self, sample_outline: Path, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "generate-section",
                "--outline", str(sample_outline),
                "--data-root", str(tmp_path / "missing"),
                "--section", "emissions",
                "--output", str(tmp_path / "output.md"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_missing_section(self, sample_outline: Path, sample_data_root: Path, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "generate-section",
                "--outline", str(sample_outline),
                "--data-root", str(sample_data_root),
                "--section", "nonexistent",
                "--output", str(tmp_path / "output.md"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output
        assert "emissions" in result.output

    def test_dry_run(self, sample_outline: Path, sample_data_root: Path, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "generate-section",
                "--outline", str(sample_outline),
                "--data-root", str(sample_data_root),
                "--section", "emissions",
                "--output", str(tmp_path / "output.md"),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Emissions" in result.output


class TestGenerateReportCommand:
    def test_missing_outline(self, tmp_path: Path, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "generate-report",
                "--outline", str(tmp_path / "missing.md"),
                "--data-root", str(sample_data_root),
                "--output", str(tmp_path / "output.md"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_dry_run(self, sample_outline: Path, sample_data_root: Path, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "generate-report",
                "--outline", str(sample_outline),
                "--data-root", str(sample_data_root),
                "--output", str(tmp_path / "output.md"),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "3 sections" in result.output


class TestInspectChartsCommand:
    def test_missing_data_root(self, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "inspect-charts",
                "--data-root", str(tmp_path / "missing"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_list_charts_table(self, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "inspect-charts",
                "--data-root", str(sample_data_root),
                "--format", "table",
            ],
        )
        assert result.exit_code == 0
        assert "emissions_by_sector" in result.output

    def test_list_charts_json(self, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "inspect-charts",
                "--data-root", str(sample_data_root),
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == "emissions_by_sector"
        assert data[0]["category"] == "emissions"

    def test_filter_by_category(self, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "inspect-charts",
                "--data-root", str(sample_data_root),
                "--category", "emissions",
            ],
        )
        assert result.exit_code == 0
        assert "emissions_by_sector" in result.output


class TestInspectSectionsCommand:
    def test_missing_outline(self, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "inspect-sections",
                "--outline", str(tmp_path / "missing.md"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_list_sections(self, sample_outline: Path):
        result = runner.invoke(
            app,
            [
                "inspect-sections",
                "--outline", str(sample_outline),
            ],
        )
        assert result.exit_code == 0
        assert "projection" in result.output.lower()
        assert "emissions" in result.output.lower()
        assert "transport" in result.output.lower()
        assert "3 sections" in result.output

    def test_show_charts(self, sample_outline: Path, sample_data_root: Path):
        result = runner.invoke(
            app,
            [
                "inspect-sections",
                "--outline", str(sample_outline),
                "--data-root", str(sample_data_root),
                "--show-charts",
            ],
        )
        assert result.exit_code == 0
        assert "emissions" in result.output


class TestRunEvalCommand:
    def test_missing_outline(self, tmp_path: Path):
        result = runner.invoke(
            app,
            [
                "run-eval",
                "--outline", str(tmp_path / "missing.md"),
                "--run-id", "test-run",
                "--output", str(tmp_path / "eval.json"),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_run_eval(self, sample_outline: Path, tmp_path: Path):
        output_path = tmp_path / "eval.json"
        result = runner.invoke(
            app,
            [
                "run-eval",
                "--outline", str(sample_outline),
                "--run-id", "test-run-123",
                "--output", str(output_path),
            ],
        )
        assert result.exit_code == 0
        assert output_path.exists()

        data = json.loads(output_path.read_text())
        assert data["run_id"] == "test-run-123"
        assert data["summary"]["total_sections"] == 3
        assert data["summary"]["rated_sections"] == 1
        assert "accuracy" in data["summary"]["average_ratings"]
        assert data["summary"]["average_ratings"]["accuracy"] == 4.0


class TestHelpText:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Report Agent CLI" in result.output

    def test_generate_section_help(self):
        result = runner.invoke(app, ["generate-section", "--help"])
        assert result.exit_code == 0
        assert "--outline" in result.output
        assert "--section" in result.output

    def test_generate_report_help(self):
        result = runner.invoke(app, ["generate-report", "--help"])
        assert result.exit_code == 0
        assert "--outline" in result.output
        assert "--dry-run" in result.output

    def test_inspect_charts_help(self):
        result = runner.invoke(app, ["inspect-charts", "--help"])
        assert result.exit_code == 0
        assert "--data-root" in result.output
        assert "--format" in result.output

    def test_inspect_sections_help(self):
        result = runner.invoke(app, ["inspect-sections", "--help"])
        assert result.exit_code == 0
        assert "--show-charts" in result.output

    def test_run_eval_help(self):
        result = runner.invoke(app, ["run-eval", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
