# Report Integration Task

You are integrating a report with {section_count} sections.

## Current Report State

The report state tracks canonical figures and tables to prevent duplication:

```json
{report_state_json}
```

## Full Report Content

Below is the complete report assembled from independently-generated sections:

---

{full_report_content}

---

## Your Task

1. **Identify Duplicates**: Find figures/charts that appear in multiple sections (same data visualized multiple times)
2. **Assign Canonical IDs**: For each unique figure, assign F1, F2, etc. For tables, assign T1, T2, etc.
3. **Update References**: Replace duplicate figures with cross-references (e.g., "see Figure 3 in the Emissions Overview section")
4. **Add Cross-References**: Where sections discuss the same data, add references to connect them
5. **Update Section Meta**: Add REPORT_SECTION_META comments at the top of each section

## REPORT_SECTION_META Format

At the top of each section (after the heading), add a hidden comment with integration metadata:

```
<!-- REPORT_SECTION_META
{{
  "section_id": "section-slug",
  "canonical_figures": ["F1", "F3"],
  "references_figures": ["F2"],
  "avoid_duplicating": ["emissions_by_sector", "throughput_timeline"],
  "notes": "Removed duplicate emissions chart, now references F1 from Executive Summary"
}}
-->
```

Fields:
- `section_id`: The section identifier/slug
- `canonical_figures`: Figure IDs that this section owns/defines
- `references_figures`: Figure IDs from other sections that this section references
- `avoid_duplicating`: Semantic keys of figures this section should NOT recreate
- `notes`: What integration changes were made and why

## Output Format

Return the integrated report with:

1. **Updated section content** with duplicates replaced by cross-references
2. **REPORT_SECTION_META comments** at the top of each section (after the heading)
3. **A final REPORT_STATE_UPDATE block** containing the updated report state

### REPORT_STATE_UPDATE Format

At the very end of your response, include the updated report state:

```
<!-- REPORT_STATE_UPDATE
{{
  "report_id": "{report_id}",
  "figures": [
    {{
      "id": "F1",
      "semantic_key": "emissions_by_sector",
      "owner_section": "executive-summary",
      "caption": "Emissions breakdown by sector",
      "chart_id": "emissions_by_sector.png"
    }}
  ],
  "tables": [],
  "section_meta": {{
    "executive-summary": {{
      "section_id": "executive-summary",
      "version": 1,
      "last_integrated_version": 1
    }}
  }}
}}
-->
```

## Guidelines

- Preserve ALL original content except for duplicate figures
- When removing a duplicate, replace it with a clear cross-reference
- Number figures in order of first appearance (F1, F2, F3, ...)
- Number tables separately (T1, T2, T3, ...)
- Keep figure captions when they add context
- If two figures show the same data differently, keep the clearer one
- Be conservative: when in doubt, keep both figures
