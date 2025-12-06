# Task: Write the '{section_title}' section of the report

## Section Information
- **Title**: {section_title}
- **Level**: {heading_markers} (heading level {section_level})
{parent_section_line}

{instructions_block}

{existing_content_block}

{integration_hints_block}

{state_hints_block}

{available_data_block}

## Output Requirements
1. **DO NOT include the section heading** - it will be added automatically
2. Write professional, technical prose suitable for an annual report
3. Reference specific data points from the charts provided
4. Maintain consistency with the parent section context
5. Use appropriate markdown formatting (but no top-level heading)
6. Keep the content focused and concise
7. **Include figures**: For each chart with a figure, include it using markdown image syntax:
   - Use the exact format: `![Chart Title](figures/{{chart_id}}.png)`
   - Use the chart ID exactly as provided (e.g., `figures/emissions_by_sector.png`)
   - Place figures after relevant discussion of the data
   - Caption format: `*Figure: [description of what the figure shows]*`
8. Use the nearest whole number when reporting values.
9. Do not try to be overly precise in the numerical values since these results have inherent uncertainty.
10. Use the word "Scenario" rather than "Case".

## Scenario Naming Convention
Use these exact scenario names consistently throughout:
- **Ampol-1p5DS** (1.5°C-aligned pathway)
- **Ampol-2p5DS** (2.5°C pathway)
- **Ampol-House-View** (reference/baseline scenario)

## Content Guidelines
- Focus on insights specific to this section's scope
- Avoid repeating detailed analysis that belongs in other sections
- Cross-reference other sections where appropriate rather than duplicating content

Write the section content below (no heading):
