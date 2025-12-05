import pytest
from pathlib import Path
from report_agent.outline_parser import Section, parse_outline, slugify, parse_review_block


class TestSlugify:
    def test_simple_title(self):
        assert slugify("Emissions") == "emissions"

    def test_multiple_words(self):
        assert slugify("Projection results") == "projection-results"

    def test_special_characters(self):
        assert slugify("Energy & Power!") == "energy-power"

    def test_multiple_spaces(self):
        assert slugify("Energy   consumption") == "energy-consumption"

    def test_leading_trailing_spaces(self):
        assert slugify("  Emissions  ") == "emissions"

    def test_mixed_case(self):
        assert slugify("Energy Consumption by Sector") == "energy-consumption-by-sector"


class TestParseReviewBlock:
    def test_empty_text(self):
        author, ratings, notes = parse_review_block("")
        assert author == ""
        assert ratings == {}
        assert notes == ""

    def test_rating_only(self):
        text = "RATING: accuracy=4, completeness=3"
        author, ratings, notes = parse_review_block(text)
        assert ratings == {"accuracy": 4, "completeness": 3}
        assert notes == ""

    def test_rating_with_notes(self):
        text = "RATING: accuracy=4, completeness=3\nNOTES: Good coverage but missed House View scenario."
        author, ratings, notes = parse_review_block(text)
        assert ratings == {"accuracy": 4, "completeness": 3}
        assert notes == "Good coverage but missed House View scenario."

    def test_notes_multiline(self):
        text = "RATING: clarity=5\nNOTES: First line.\nSecond line."
        author, ratings, notes = parse_review_block(text)
        assert ratings == {"clarity": 5}
        assert notes == "First line.\nSecond line."

    def test_no_rating_line(self):
        text = "Some random text without rating"
        author, ratings, notes = parse_review_block(text)
        assert ratings == {}
        assert notes == ""

    def test_author_field(self):
        text = "AUTHOR: Alice\nRATING: clarity=5\nNOTES: Great work."
        author, ratings, notes = parse_review_block(text)
        assert author == "Alice"
        assert ratings == {"clarity": 5}
        assert notes == "Great work."


class TestParseOutline:
    def test_parse_simple_outline(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Projection results\n"
            "<!-- Section instructions: Provide an overview -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "## Emissions\n"
            "<!-- Section instructions: Describe emissions -->\n"
            "<!-- Review comments: RATING: accuracy=4\n"
            "NOTES: Good work. -->\n"
        )
        sections = parse_outline(outline)

        assert len(sections) == 2

        assert sections[0].id == "projection-results"
        assert sections[0].title == "Projection results"
        assert sections[0].level == 1
        assert sections[0].instructions == "Provide an overview"
        assert sections[0].parent_id is None

        assert sections[1].id == "emissions"
        assert sections[1].title == "Emissions"
        assert sections[1].level == 2
        assert sections[1].instructions == "Describe emissions"
        assert sections[1].parent_id == "projection-results"
        assert sections[1].review_ratings == {"accuracy": 4}
        assert sections[1].review_notes == "Good work."

    def test_nested_hierarchy(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Top\n"
            "<!-- Section instructions: Top level -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "## Middle\n"
            "<!-- Section instructions: Middle level -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "### Bottom\n"
            "<!-- Section instructions: Bottom level -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "## Another Middle\n"
            "<!-- Section instructions: Another middle -->\n"
            "<!-- Review comments: -->\n"
        )
        sections = parse_outline(outline)

        assert len(sections) == 4
        assert sections[0].parent_id is None
        assert sections[1].parent_id == "top"
        assert sections[2].parent_id == "middle"
        assert sections[3].parent_id == "top"

    def test_content_extraction(self, tmp_path):
        outline = tmp_path / "outline.md"
        outline.write_text(
            "# Section One\n"
            "<!-- Section instructions: Instructions here -->\n"
            "<!-- Review comments: -->\n"
            "\n"
            "This is the content of section one.\n"
            "It has multiple lines.\n"
            "\n"
            "## Section Two\n"
            "<!-- Section instructions: More instructions -->\n"
            "<!-- Review comments: -->\n"
        )
        sections = parse_outline(outline)

        assert len(sections) == 2
        assert "This is the content of section one." in sections[0].content
        assert "It has multiple lines." in sections[0].content


class TestIntegrationWithRealFile:
    def test_parse_real_outline(self):
        outline_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "example-outputs" / "ampol2025" / "report-outline.md"
        if not outline_path.exists():
            pytest.skip("Example outline file not found")

        sections = parse_outline(outline_path)

        assert len(sections) > 0
        assert sections[0].id == "projection-results"
        assert sections[0].level == 1

        emissions = next((s for s in sections if s.id == "emissions"), None)
        assert emissions is not None
        assert emissions.parent_id == "projection-results"
        assert emissions.level == 2

        transport = next((s for s in sections if s.id == "transport"), None)
        assert transport is not None
        assert transport.parent_id == "energy-consumption-by-sector"
        assert transport.level == 3
