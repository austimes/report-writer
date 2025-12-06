# Report Integration Task

You are integrating an assembled report to make it cohesive and consistent.

## Full Report Content

Below is the complete report assembled from independently-generated sections.
Each section is wrapped with `<!-- BEGIN SECTION: section-id (Title) -->` and `<!-- END SECTION: section-id -->` markers.

---

{full_report_content}

---

## Your Task

Review the entire report and make **minimal edits** to:

1. **Identify Duplicate Figures**: Find figures with identical image URLs (e.g., `![...](figures/same_chart.png)`) across sections
2. **Assign Consistent Numbering**: Number figures as F1, F2, F3... and tables as T1, T2, T3... in order of first appearance
3. **Remove Duplicates**: Replace duplicate figures with cross-references (e.g., "see Figure 3 in the Executive Summary")
4. **Add Cross-References**: Where sections discuss the same data, add brief references to connect them
5. **Add INTEGRATION_HINTS**: Insert a metadata comment at the start of each section (see format below)

## CRITICAL CONSTRAINTS

- **DO NOT** remove, move, rename, or insert any section boundary markers:
  - `<!-- BEGIN SECTION: ... -->`
  - `<!-- END SECTION: ... -->`
- **DO NOT** change the meaning of any content
- **DO NOT** add new analysis, claims, or data
- **DO NOT** reorder sections
- **DO NOT** substantially rewrite paragraphs
- **ONLY** edit content *inside* section markers
- **PREFER** minimal phrasing changes for coherence

## INTEGRATION_HINTS Format

Place this comment immediately after the `<!-- BEGIN SECTION: ... -->` marker, before the heading:

```
<!-- INTEGRATION_HINTS: {{"section_id": "section-slug", "canonical_figures": ["F1"], "references_figures": ["F2", "F3"], "avoid_duplicating": ["emissions_by_sector.png"], "notes": "Removed duplicate chart, now refs F1"}} -->
```

Fields:
- `section_id`: Must match the ID in the BEGIN SECTION marker
- `canonical_figures`: Figure IDs (F1, F2...) that this section owns/defines
- `references_figures`: Figure IDs from other sections that this section references
- `avoid_duplicating`: Image filenames that should not be recreated in this section
- `notes`: Brief description of integration changes made

## Detecting Duplicates

- Treat **identical image URLs** as the same figure (e.g., `figures/emissions_breakdown.png`)
- When you find duplicates, keep the **first occurrence** and replace later ones with cross-references
- If two figures show similar data differently, keep the clearer one

## Output Format

Return **only** the complete integrated markdown for the entire report.
- Optionally wrap in a ```markdown code fence
- Do NOT include any explanation or commentary outside the markdown
- Preserve ALL section markers exactly as they appear
