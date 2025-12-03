import json
import pytest
from pathlib import Path

from report_agent.eval_runner import (
    SectionEval,
    EvalRun,
    EvalRunner,
    RATING_DIMENSIONS,
    compare_runs,
)


class TestSectionEval:
    def test_create_section_eval(self):
        section = SectionEval(
            section_id="emissions",
            title="Emissions",
            ratings={"accuracy": 4, "completeness": 3, "clarity": 5, "data_use": 4},
            notes="Good coverage of 1.5DS scenario.",
            draft_length=450,
        )
        assert section.section_id == "emissions"
        assert section.ratings["accuracy"] == 4
        assert section.draft_length == 450


class TestEvalRun:
    def test_create_eval_run(self):
        sections = [
            SectionEval(
                section_id="emissions",
                title="Emissions",
                ratings={"accuracy": 4},
                notes="",
                draft_length=100,
            )
        ]
        run = EvalRun(
            run_id="test-run-1",
            timestamp="2025-12-03T14:00:00Z",
            model="gpt-4",
            prompt_version="v1.0",
            outline_path="/path/to/outline.md",
            data_root="/path/to/data",
            sections=sections,
            aggregate={"accuracy": 4.0},
        )
        assert run.run_id == "test-run-1"
        assert len(run.sections) == 1
        assert run.aggregate["accuracy"] == 4.0


class TestEvalRunner:
    def test_parse_reviews(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Report\n"
            "<!-- Section instructions: Overview -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "## Emissions\n"
            "<!-- Section instructions: Describe emissions -->\n"
            "<!-- Review comments: RATING: accuracy=4, completeness=3\n"
            "NOTES: Good coverage of 1.5DS scenario. -->\n"
            "\n"
            "Content about emissions here.\n"
            "\n"
            "## Energy\n"
            "<!-- Section instructions: Describe energy -->\n"
            "<!-- Review comments: RATING: accuracy=5, clarity=4\n"
            "NOTES: Clear presentation. -->\n"
            "\n"
            "Content about energy.\n"
        )

        runner = EvalRunner(outline)
        sections = runner.parse_reviews()

        assert len(sections) == 2

        emissions = sections[0]
        assert emissions.section_id == "emissions"
        assert emissions.title == "Emissions"
        assert emissions.ratings == {"accuracy": 4, "completeness": 3}
        assert emissions.notes == "Good coverage of 1.5DS scenario."
        assert emissions.draft_length > 0

        energy = sections[1]
        assert energy.section_id == "energy"
        assert energy.ratings == {"accuracy": 5, "clarity": 4}

    def test_parse_reviews_no_ratings(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Report\n"
            "<!-- Section instructions: Overview -->\n"
            "<!-- Review comments: -->\n"
        )

        runner = EvalRunner(outline)
        sections = runner.parse_reviews()
        assert len(sections) == 0

    def test_compute_aggregate(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text("# Empty\n")

        runner = EvalRunner(outline)

        sections = [
            SectionEval(
                section_id="a",
                title="A",
                ratings={"accuracy": 4, "completeness": 3, "clarity": 5, "data_use": 4},
                notes="",
                draft_length=100,
            ),
            SectionEval(
                section_id="b",
                title="B",
                ratings={"accuracy": 5, "completeness": 4, "clarity": 4, "data_use": 3},
                notes="",
                draft_length=200,
            ),
        ]

        aggregate = runner.compute_aggregate(sections)

        assert aggregate["accuracy"] == 4.5
        assert aggregate["completeness"] == 3.5
        assert aggregate["clarity"] == 4.5
        assert aggregate["data_use"] == 3.5
        assert "overall" in aggregate
        assert aggregate["overall"] == 4.0

    def test_compute_aggregate_empty(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text("# Empty\n")

        runner = EvalRunner(outline)
        aggregate = runner.compute_aggregate([])
        assert aggregate == {}

    def test_compute_aggregate_partial_ratings(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text("# Empty\n")

        runner = EvalRunner(outline)

        sections = [
            SectionEval(
                section_id="a",
                title="A",
                ratings={"accuracy": 4},
                notes="",
                draft_length=100,
            ),
            SectionEval(
                section_id="b",
                title="B",
                ratings={"accuracy": 5, "clarity": 3},
                notes="",
                draft_length=200,
            ),
        ]

        aggregate = runner.compute_aggregate(sections)
        assert aggregate["accuracy"] == 4.5
        assert aggregate["clarity"] == 3.0
        assert "completeness" not in aggregate
        assert "data_use" not in aggregate

    def test_run_eval(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Report\n"
            "<!-- Section instructions: Overview -->\n"
            "<!-- Review comments: RATING: accuracy=4\nNOTES: Test -->\n"
        )

        runner = EvalRunner(outline)
        result = runner.run_eval(
            run_id="test-run",
            model="gpt-4",
            prompt_version="v2.0",
        )

        assert result.run_id == "test-run"
        assert result.model == "gpt-4"
        assert result.prompt_version == "v2.0"
        assert result.outline_path == str(outline)
        assert len(result.sections) == 1
        assert result.aggregate["accuracy"] == 4.0

    def test_save_and_load_results(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Report\n"
            "<!-- Section instructions: Overview -->\n"
            "<!-- Review comments: RATING: accuracy=4, clarity=5\nNOTES: Good work -->\n"
            "\n"
            "Content here.\n"
        )

        runner = EvalRunner(outline)
        original = runner.run_eval(run_id="save-test", model="claude", prompt_version="v1.0")

        output_path = tmp_path / "results" / "eval.json"
        runner.save_results(original, output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["run_id"] == "save-test"
        assert data["model"] == "claude"
        assert len(data["sections"]) == 1

        loaded = runner.load_results(output_path)
        assert loaded.run_id == original.run_id
        assert loaded.model == original.model
        assert len(loaded.sections) == len(original.sections)
        assert loaded.sections[0].section_id == original.sections[0].section_id
        assert loaded.aggregate == original.aggregate


class TestCompareRuns:
    def test_compare_runs_improvement(self):
        run1 = EvalRun(
            run_id="run1",
            timestamp="2025-12-01T10:00:00Z",
            model="gpt-3.5",
            prompt_version="v1.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[
                SectionEval(
                    section_id="emissions",
                    title="Emissions",
                    ratings={"accuracy": 3, "clarity": 3},
                    notes="",
                    draft_length=100,
                )
            ],
            aggregate={"accuracy": 3.0, "clarity": 3.0, "overall": 3.0},
        )

        run2 = EvalRun(
            run_id="run2",
            timestamp="2025-12-02T10:00:00Z",
            model="gpt-4",
            prompt_version="v2.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[
                SectionEval(
                    section_id="emissions",
                    title="Emissions",
                    ratings={"accuracy": 4, "clarity": 5},
                    notes="",
                    draft_length=150,
                )
            ],
            aggregate={"accuracy": 4.0, "clarity": 5.0, "overall": 4.5},
        )

        comparison = compare_runs(run1, run2)

        assert comparison["run1_id"] == "run1"
        assert comparison["run2_id"] == "run2"

        assert comparison["dimension_deltas"]["accuracy"]["delta"] == 1.0
        assert comparison["dimension_deltas"]["accuracy"]["improved"] is True
        assert comparison["dimension_deltas"]["clarity"]["delta"] == 2.0

        assert comparison["summary"]["overall_delta"] == 1.5
        assert comparison["summary"]["overall_improved"] is True
        assert comparison["summary"]["dimensions_improved"] == 3

    def test_compare_runs_regression(self):
        run1 = EvalRun(
            run_id="run1",
            timestamp="2025-12-01T10:00:00Z",
            model="gpt-4",
            prompt_version="v1.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[],
            aggregate={"accuracy": 5.0, "overall": 5.0},
        )

        run2 = EvalRun(
            run_id="run2",
            timestamp="2025-12-02T10:00:00Z",
            model="gpt-3.5",
            prompt_version="v1.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[],
            aggregate={"accuracy": 3.0, "overall": 3.0},
        )

        comparison = compare_runs(run1, run2)

        assert comparison["dimension_deltas"]["accuracy"]["delta"] == -2.0
        assert comparison["dimension_deltas"]["accuracy"]["improved"] is False
        assert comparison["summary"]["overall_improved"] is False
        assert comparison["summary"]["dimensions_regressed"] == 2

    def test_compare_runs_different_sections(self):
        run1 = EvalRun(
            run_id="run1",
            timestamp="2025-12-01T10:00:00Z",
            model="gpt-4",
            prompt_version="v1.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[
                SectionEval(
                    section_id="emissions",
                    title="Emissions",
                    ratings={"accuracy": 4},
                    notes="",
                    draft_length=100,
                )
            ],
            aggregate={"accuracy": 4.0, "overall": 4.0},
        )

        run2 = EvalRun(
            run_id="run2",
            timestamp="2025-12-02T10:00:00Z",
            model="gpt-4",
            prompt_version="v2.0",
            outline_path="/path/outline.md",
            data_root="/path/data",
            sections=[
                SectionEval(
                    section_id="emissions",
                    title="Emissions",
                    ratings={"accuracy": 5},
                    notes="",
                    draft_length=150,
                ),
                SectionEval(
                    section_id="energy",
                    title="Energy",
                    ratings={"accuracy": 4},
                    notes="",
                    draft_length=200,
                ),
            ],
            aggregate={"accuracy": 4.5, "overall": 4.5},
        )

        comparison = compare_runs(run1, run2)

        assert "emissions" in comparison["section_deltas"]
        assert "energy" in comparison["section_deltas"]
        assert comparison["section_deltas"]["emissions"]["rating_deltas"]["accuracy"] == 1
        assert comparison["section_deltas"]["energy"]["run1"] is None
        assert comparison["section_deltas"]["energy"]["run2"] is not None


class TestRatingDimensions:
    def test_rating_dimensions_defined(self):
        assert "accuracy" in RATING_DIMENSIONS
        assert "completeness" in RATING_DIMENSIONS
        assert "clarity" in RATING_DIMENSIONS
        assert "data_use" in RATING_DIMENSIONS
        assert len(RATING_DIMENSIONS) == 4
