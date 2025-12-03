# Report Agent Design: LLM-Powered Report Generation

## Overview

This document describes the architecture for LLM/AI agent CLI tools that automate report generation from energy model outputs (AusTIMES). The agent ingests:
1. A **report outline** (Markdown with section instructions)
2. **Chart data** (CSVs, PNGs, Plotly JSON)
3. **Expert review feedback** (HTML comments in the outline)

And produces draft report content for each section.

## Status

**Current state**: No implementation exists. This is a new capability.

**Production use case**: AMPOL ASRS (Australian Sustainability Reporting Standards) emissions reporting.

## Architecture

### High-Level Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Report Outline │     │   Chart Data    │     │ Section-Chart   │
│  (Markdown)     │────▶│  (CSV/PNG/JSON) │────▶│    Mapping      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────────────────────────────────────────────────────┐
│                    Report Agent CLI                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │  Outline    │  │    Data     │  │    LLM Tools        │   │
│  │  Parser     │  │   Catalog   │  │  (get_chart_data,   │   │
│  │             │  │             │  │   write_section)    │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────┐     ┌─────────────────┐
│  Draft Report   │────▶│  Expert Review  │─────┐
│  (Markdown)     │     │  (Ratings/Notes)│     │
└─────────────────┘     └─────────────────┘     │
        ▲                                       │
        │                                       │
        └──────────── Iterate ◀────────────────┘
```

### Technology Choice

**Recommendation**: Extend the existing **Python sandbox** (`apps/sandbox`).

Rationale:
- LLM orchestration already lives here (`llm_client.py`, `prompt_builder.py`)
- CSV/data processing is natural in Python (pandas)
- Image handling (base64 encoding PNGs) is straightforward
- Avoids duplicating logic in a TypeScript CLI

### Package Structure

```
apps/sandbox/src/
├── sandbox/               # Existing code
│   ├── api/
│   ├── core/
│   └── main.py
└── report_agent/          # NEW
    ├── __init__.py
    ├── cli.py             # Typer CLI entry point
    ├── outline_parser.py  # Parse report outline Markdown
    ├── data_catalog.py    # Discover and index chart data
    ├── chart_reader.py    # Read/summarize CSV, PNG, JSON
    ├── agent_tools.py     # LLM tool definitions
    ├── section_mapper.py  # Map sections to relevant charts
    ├── eval_runner.py     # Parse reviews, compute metrics
    └── config.py          # Settings, paths, model config
```

## Report Outline Format

The outline uses HTML comments to embed machine-readable instructions:

```markdown
# Projection results 
<!-- Section instructions: Provide an overview of the projection results -->
<!-- Review comments: -->

## Emissions 
<!-- Section instructions: Provide an overview of the emissions projection results -->
<!-- Review comments: RATING: accuracy=4, completeness=3, clarity=5
NOTES: Missed mention of House View scenario. Add baseline comparison. -->
```

### Parsed Structure

```python
@dataclass
class Section:
    id: str                    # slug from title, e.g., "emissions"
    title: str                 # "Emissions"
    level: int                 # heading level (1=h1, 2=h2, etc.)
    instructions: str          # from "Section instructions:"
    review_comments: str       # from "Review comments:"
    review_ratings: dict       # parsed {accuracy: 4, completeness: 3, ...}
    review_notes: str          # free-text notes
    parent_id: str | None      # parent section ID
    content: str               # existing draft content (if any)
```

## Data Catalog

### Chart Data Structure

```
data/example-outputs/ampol2025/2025-12-03T10.20_Ampol.../
├── plot_specs.json           # Pivot settings for each chart
├── project_view_*.csv        # Raw project data (optional)
├── emissions/                # Category folder
│   ├── emissions_reduction_by_sector.csv
│   ├── emissions_reduction_by_sector.png
│   ├── emissions_reduction_by_sector.json  # Plotly spec
│   └── ...
├── transport/
│   └── ...
├── electricity/
│   └── ...
└── ...
```

### Chart Metadata

```python
@dataclass
class ChartMeta:
    id: str                    # "emissions_reduction_by_sector"
    category: str              # "emissions"
    title: str                 # from plot_specs or filename
    path_csv: Path | None
    path_png: Path | None
    path_json: Path | None
    dimensions: list[str]      # ["process_sector0", "scen"]
    measures: list[str]        # ["val"]
    scenarios: list[str]       # ["Ampol-1p5DS", "Ampol-2p5DS", "Ampol-House-View"]
    units: str                 # "Mt CO₂-e" or "PJ"
    linked_section_ids: list[str]  # from section-chart mapping
```

## LLM Tools

The agent exposes focused, composable tools:

### 1. Outline Tools

| Tool | Description |
|------|-------------|
| `get_section_context(section_id)` | Returns title, instructions, current draft, review comments |
| `write_section_draft(section_id, content)` | Writes Markdown content for a section |

### 2. Chart Discovery Tools

| Tool | Description |
|------|-------------|
| `list_chart_categories()` | Returns available categories (emissions, transport, etc.) |
| `list_charts(category?, section_id?)` | Returns chart metadata for filtering |
| `get_section_charts(section_id)` | Returns curated charts for a section (from mapping) |

### 3. Chart Data Tools

| Tool | Description |
|------|-------------|
| `get_chart_data(chart_id, options)` | Returns schema, rows, and **pre-computed summary** |
| `get_chart_image(chart_id)` | Returns base64 PNG for vision models |
| `get_plot_spec(chart_id)` | Returns Plotly JSON spec |

### Pre-computed Summaries

The key design decision: **do data processing in Python**, not in the LLM.

Example `get_chart_data` response for `emissions_reduction_by_sector`:

```json
{
  "chart_id": "emissions_reduction_by_sector",
  "schema": {"columns": ["process_sector0", "val", "measure", "scen"]},
  "row_count": 25,
  "summary": {
    "dimensions": ["process_sector0", "scen"],
    "measure": "val",
    "measure_type": "relative (change from 2025)",
    "scenarios": ["Ampol-1p5DS", "Ampol-2p5DS", "Ampol-House-View"],
    "baseline": {"name": "Net 2025", "value": 401.05},
    "by_scenario": {
      "Ampol-1p5DS": {
        "total_reduction": -472.53,
        "top_reductions": [
          {"sector": "Power Generation", "value": -128.92},
          {"sector": "Industry", "value": -109.74},
          {"sector": "Transport", "value": -94.07}
        ]
      },
      "Ampol-2p5DS": { ... },
      "Ampol-House-View": {
        "total_reduction": -195.63,
        "notable": "Land Use shows net INCREASE of +33.58"
      }
    },
    "key_insights": [
      "All scenarios start from baseline of 401.05 Mt CO₂-e in 2025",
      "Power Generation provides largest reduction across all scenarios (~128 Mt)",
      "Ampol-1p5DS achieves deepest cuts, with Transport and Industry contributing significantly",
      "House View scenario shows weaker Transport reductions and net emissions increase from Land Use"
    ]
  }
}
```

## Section-Chart Mapping

### Static Mapping File

Create `section_chart_map.json`:

```json
{
  "projection-results": {
    "description": "Top-level overview",
    "charts": ["emissions_reduction_by_sector", "electricity_generation_by_fuel"]
  },
  "emissions": {
    "description": "Emissions projections overview",
    "charts": [
      "emissions_reduction_by_sector",
      "emissions_from_electricity_generation",
      "domestic_transport_emissions_by_subsector"
    ]
  },
  "transport": {
    "description": "Transport energy consumption",
    "charts": [
      "domestic_transport_energy_use_by_fuel",
      "road_transport_energy_use_by_fuel",
      "road_vehicle_stock_by_drivetrain"
    ]
  }
}
```

### Fallback: Auto-mapping

If a section isn't in the mapping, use heuristics:
1. Match section title keywords to chart categories
2. Match section title to chart titles
3. Return top 3-5 matches by relevance

## CLI Commands

```bash
# Generate full report
python -m report_agent generate-report \
  --outline data/example-outputs/ampol2025/report-outline.md \
  --data-root data/example-outputs/ampol2025/2025-12-03T10.20_Ampol.2025-12-03T10.36_all \
  --output report-draft.md

# Generate single section (for iteration)
python -m report_agent generate-section \
  --outline report-outline.md \
  --data-root ... \
  --section emissions

# Inspect available charts
python -m report_agent inspect-charts \
  --data-root ... \
  --category emissions

# Run evaluation on reviewed report
python -m report_agent run-eval \
  --outline report-reviewed.md \
  --run-id ampol-2025-v1 \
  --output eval_results.json
```

## Evaluation Framework

### Review Comment Format

Analysts encode ratings in the review comments:

```markdown
<!-- Review comments:
RATING: accuracy=4, completeness=3, clarity=5, data_use=4
NOTES: Good coverage of 1.5DS scenario. Missed mention of House View's 
Land Use increase. Consider adding year-by-year breakdown.
-->
```

### Scoring Dimensions

| Dimension | Description |
|-----------|-------------|
| `accuracy` | Numbers and facts are correct |
| `completeness` | All relevant data/scenarios covered |
| `clarity` | Writing is clear and professional |
| `data_use` | Appropriate use of available charts/data |

### Eval Run Record

```json
{
  "run_id": "ampol-2025-v1",
  "timestamp": "2025-12-03T14:00:00Z",
  "model": "gpt-4.1",
  "prompt_version": "v1.0",
  "sections": [
    {
      "section_id": "emissions",
      "draft_length": 450,
      "ratings": {"accuracy": 4, "completeness": 3, "clarity": 5, "data_use": 4},
      "notes": "Good coverage of 1.5DS scenario..."
    }
  ],
  "aggregate": {
    "accuracy": 4.2,
    "completeness": 3.5,
    "clarity": 4.8,
    "data_use": 4.0
  }
}
```

## DuckDB: When to Add

**Start without DuckDB.** Add it when:
- Analysts need ad-hoc multi-table queries
- CSV count/size causes performance issues
- Cross-report comparisons are needed (2025 vs 2026)

Implementation path:
1. Abstract data access behind `DataBackend` interface
2. Implement `PandasBackend` first
3. Add `DuckDBBackend` with external tables over CSVs
4. Expose constrained `sql_query` tool with read-only access

## Guardrails

### Data Faithfulness

- Never let LLM scan filesystem directly
- Provide pre-computed summaries with **verbatim key numbers**
- Agent narrates data rather than computing

### Section-Chart Mismatch Prevention

- Keep `section_chart_map.json` under version control
- Add `inspect-section-mapping` CLI command
- Review mapping changes like code changes

### Eval Quality

- Document scoring rubric for analysts
- Enforce RATING format, flag malformed comments
- Track prompt/tool versions in each eval run

## Implementation Phases

### Phase 1: MVP (1-2 days)

1. `outline_parser.py` - Parse sections, instructions, comments
2. `data_catalog.py` - Discover charts from folder structure
3. `chart_reader.py` - Load CSV, generate basic summaries
4. CLI: `generate-section --section emissions`
5. Manual review workflow

### Phase 2: Full Report Generation (2-3 days)

1. `section_mapper.py` - Static mapping + fallback
2. `agent_tools.py` - Full tool definitions
3. CLI: `generate-report`
4. Image support for vision models

### Phase 3: Eval Framework (1-2 days)

1. `eval_runner.py` - Parse reviews, compute metrics
2. CLI: `run-eval`
3. Eval results storage/visualization

### Phase 4: Enhancements (ongoing)

- DuckDB integration if needed
- Derived insight tools (`compare_scenarios`, `trend_summary`)
- Automated consistency checks
- Web UI integration via Convex

## Related Documents

- [Agent Threads](agent-threads.md) - LLM orchestration in web app
- [Architecture](architecture.md) - Overall system design
- [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) - bd task tracking

## Next Steps

1. Create bd issues for each implementation phase
2. Set up `report_agent` package structure
3. Implement outline parser with test data
4. Build data catalog for AMPOL dataset
