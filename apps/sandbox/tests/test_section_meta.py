"""Tests for section meta parser and serializer."""

import pytest

from report_agent.section_meta import (
    IntegrationHints,
    IntegrationNote,
    SectionMetaComment,
    extract_section_meta_and_body,
    inject_section_meta,
    parse_section_meta,
    serialize_section_meta,
)


class TestParseValidMeta:
    """Tests for parsing valid REPORT_SECTION_META comments."""

    def test_parse_minimal_meta(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "results",
  "version": 1
}
-->

# Results Section
Some content here.
'''
        meta = parse_section_meta(content)
        
        assert meta is not None
        assert meta.section_id == "results"
        assert meta.version == 1
        assert meta.integration_hints is None

    def test_parse_meta_with_integration_hints(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "analysis",
  "version": 3,
  "integration_hints": {
    "avoid_figures": ["throughput_over_time", "latency_histogram"],
    "canonical_figures": [
      {"id": "F1", "semantic_key": "throughput_over_time", "owner_section": "results"}
    ],
    "notes": [
      {
        "type": "removed_duplicate_figure",
        "semantic_key": "throughput_over_time",
        "reason": "Duplicate of F1 in results section",
        "replacement": {"type": "figure_ref", "id": "F1"}
      }
    ]
  }
}
-->

# Analysis
'''
        meta = parse_section_meta(content)
        
        assert meta is not None
        assert meta.section_id == "analysis"
        assert meta.version == 3
        assert meta.integration_hints is not None
        assert meta.integration_hints.avoid_figures == ["throughput_over_time", "latency_histogram"]
        assert len(meta.integration_hints.canonical_figures) == 1
        assert meta.integration_hints.canonical_figures[0]["id"] == "F1"
        assert len(meta.integration_hints.notes) == 1
        note = meta.integration_hints.notes[0]
        assert note.type == "removed_duplicate_figure"
        assert note.semantic_key == "throughput_over_time"
        assert note.reason == "Duplicate of F1 in results section"
        assert note.replacement == {"type": "figure_ref", "id": "F1"}

    def test_parse_meta_with_empty_integration_hints(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "overview",
  "version": 2,
  "integration_hints": {
    "avoid_figures": [],
    "canonical_figures": [],
    "notes": []
  }
}
-->
'''
        meta = parse_section_meta(content)
        
        assert meta is not None
        assert meta.integration_hints is not None
        assert meta.integration_hints.avoid_figures == []
        assert meta.integration_hints.canonical_figures == []
        assert meta.integration_hints.notes == []

    def test_parse_meta_with_note_minimal_fields(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "test",
  "version": 1,
  "integration_hints": {
    "avoid_figures": [],
    "canonical_figures": [],
    "notes": [
      {"type": "info"}
    ]
  }
}
-->
'''
        meta = parse_section_meta(content)
        
        assert meta is not None
        assert len(meta.integration_hints.notes) == 1
        assert meta.integration_hints.notes[0].type == "info"
        assert meta.integration_hints.notes[0].semantic_key is None
        assert meta.integration_hints.notes[0].reason is None
        assert meta.integration_hints.notes[0].replacement is None


class TestParseMissingMalformedMeta:
    """Tests for handling missing or malformed meta comments."""

    def test_parse_no_meta_comment(self):
        content = '''# Results Section

This is just regular content with no meta comment.
'''
        meta = parse_section_meta(content)
        assert meta is None

    def test_parse_invalid_json(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "test"
  "version": 1
}
-->
'''
        meta = parse_section_meta(content)
        assert meta is None

    def test_parse_missing_section_id(self):
        content = '''<!-- REPORT_SECTION_META
{
  "version": 1
}
-->
'''
        meta = parse_section_meta(content)
        assert meta is None

    def test_parse_missing_version(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "test"
}
-->
'''
        meta = parse_section_meta(content)
        assert meta is None

    def test_parse_empty_content(self):
        meta = parse_section_meta("")
        assert meta is None

    def test_parse_regular_html_comment(self):
        content = '''<!-- This is a regular comment -->

# Section
'''
        meta = parse_section_meta(content)
        assert meta is None


class TestRoundtrip:
    """Tests for parse -> serialize -> parse roundtrip."""

    def test_roundtrip_minimal(self):
        original = SectionMetaComment(
            section_id="results",
            version=1,
        )
        
        serialized = serialize_section_meta(original)
        parsed = parse_section_meta(serialized)
        
        assert parsed is not None
        assert parsed.section_id == original.section_id
        assert parsed.version == original.version
        assert parsed.integration_hints is None

    def test_roundtrip_with_hints(self):
        original = SectionMetaComment(
            section_id="analysis",
            version=5,
            integration_hints=IntegrationHints(
                avoid_figures=["fig1", "fig2"],
                canonical_figures=[
                    {"id": "F1", "semantic_key": "fig1", "owner_section": "results"},
                ],
                notes=[
                    IntegrationNote(
                        type="replaced_with_ref",
                        semantic_key="fig1",
                        reason="Already exists in results",
                        replacement={"type": "figure_ref", "id": "F1"},
                    ),
                ],
            ),
        )
        
        serialized = serialize_section_meta(original)
        parsed = parse_section_meta(serialized)
        
        assert parsed is not None
        assert parsed.section_id == original.section_id
        assert parsed.version == original.version
        assert parsed.integration_hints is not None
        assert parsed.integration_hints.avoid_figures == original.integration_hints.avoid_figures
        assert parsed.integration_hints.canonical_figures == original.integration_hints.canonical_figures
        assert len(parsed.integration_hints.notes) == 1
        note = parsed.integration_hints.notes[0]
        orig_note = original.integration_hints.notes[0]
        assert note.type == orig_note.type
        assert note.semantic_key == orig_note.semantic_key
        assert note.reason == orig_note.reason
        assert note.replacement == orig_note.replacement

    def test_roundtrip_empty_hints(self):
        original = SectionMetaComment(
            section_id="test",
            version=1,
            integration_hints=IntegrationHints(),
        )
        
        serialized = serialize_section_meta(original)
        parsed = parse_section_meta(serialized)
        
        assert parsed is not None
        assert parsed.integration_hints is not None
        assert parsed.integration_hints.avoid_figures == []
        assert parsed.integration_hints.canonical_figures == []
        assert parsed.integration_hints.notes == []


class TestInjectSectionMeta:
    """Tests for injecting and replacing meta comments."""

    def test_inject_into_empty_content(self):
        meta = SectionMetaComment(section_id="test", version=1)
        
        result = inject_section_meta("", meta)
        
        assert "REPORT_SECTION_META" in result
        parsed = parse_section_meta(result)
        assert parsed is not None
        assert parsed.section_id == "test"

    def test_inject_into_content_without_meta(self):
        content = '''# Results

This is the results section.
'''
        meta = SectionMetaComment(section_id="results", version=2)
        
        result = inject_section_meta(content, meta)
        
        assert result.startswith("<!-- REPORT_SECTION_META")
        assert "# Results" in result
        assert "This is the results section." in result
        
        parsed = parse_section_meta(result)
        assert parsed is not None
        assert parsed.section_id == "results"
        assert parsed.version == 2

    def test_inject_replaces_existing_meta(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "results",
  "version": 1
}
-->

# Results

Old content.
'''
        new_meta = SectionMetaComment(
            section_id="results",
            version=3,
            integration_hints=IntegrationHints(
                avoid_figures=["fig1"],
            ),
        )
        
        result = inject_section_meta(content, new_meta)
        
        # Should only have one meta comment
        assert result.count("REPORT_SECTION_META") == 1
        
        parsed = parse_section_meta(result)
        assert parsed is not None
        assert parsed.version == 3
        assert parsed.integration_hints is not None
        assert parsed.integration_hints.avoid_figures == ["fig1"]
        
        # Body should still be there
        assert "# Results" in result
        assert "Old content." in result


class TestExtractSectionMetaAndBody:
    """Tests for extracting meta and body separately."""

    def test_extract_returns_correct_body(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "results",
  "version": 1
}
-->

# Results

This is the body content.
'''
        meta, body = extract_section_meta_and_body(content)
        
        assert meta is not None
        assert meta.section_id == "results"
        assert "REPORT_SECTION_META" not in body
        assert "# Results" in body
        assert "This is the body content." in body

    def test_extract_no_meta_returns_full_content(self):
        content = '''# Results

Just regular content.
'''
        meta, body = extract_section_meta_and_body(content)
        
        assert meta is None
        assert "# Results" in body
        assert "Just regular content." in body

    def test_extract_only_meta_returns_empty_body(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "empty",
  "version": 1
}
-->'''
        meta, body = extract_section_meta_and_body(content)
        
        assert meta is not None
        assert body == ""

    def test_extract_preserves_body_formatting(self):
        content = '''<!-- REPORT_SECTION_META
{
  "section_id": "test",
  "version": 1
}
-->

## Heading

- Item 1
- Item 2

Paragraph text.
'''
        meta, body = extract_section_meta_and_body(content)
        
        assert "## Heading" in body
        assert "- Item 1" in body
        assert "- Item 2" in body
        assert "Paragraph text." in body


class TestSerializeSectionMeta:
    """Tests for serializing section meta to HTML comment."""

    def test_serialize_minimal(self):
        meta = SectionMetaComment(section_id="test", version=1)
        
        result = serialize_section_meta(meta)
        
        assert result.startswith("<!-- REPORT_SECTION_META")
        assert result.endswith("-->")
        assert '"section_id": "test"' in result
        assert '"version": 1' in result

    def test_serialize_with_hints(self):
        meta = SectionMetaComment(
            section_id="analysis",
            version=2,
            integration_hints=IntegrationHints(
                avoid_figures=["fig1"],
                canonical_figures=[{"id": "F1"}],
                notes=[
                    IntegrationNote(type="test_note", reason="testing"),
                ],
            ),
        )
        
        result = serialize_section_meta(meta)
        
        assert '"integration_hints"' in result
        assert '"avoid_figures"' in result
        assert '"fig1"' in result
        assert '"canonical_figures"' in result
        assert '"notes"' in result
        assert '"test_note"' in result

    def test_serialize_note_omits_none_fields(self):
        meta = SectionMetaComment(
            section_id="test",
            version=1,
            integration_hints=IntegrationHints(
                notes=[
                    IntegrationNote(type="simple"),
                ],
            ),
        )
        
        result = serialize_section_meta(meta)
        
        # Should not include null/None fields for semantic_key, reason, replacement
        assert "semantic_key" not in result or '"semantic_key": null' not in result
        assert "reason" not in result or '"reason": null' not in result
        assert "replacement" not in result or '"replacement": null' not in result
