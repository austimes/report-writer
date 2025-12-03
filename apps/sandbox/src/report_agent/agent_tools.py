"""LLM agent tools for the Report Agent with OpenAI-compatible function calling schemas."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from report_agent.chart_reader import ChartReader
from report_agent.data_catalog import DataCatalog
from report_agent.outline_parser import Section, parse_outline


class ReportAgentTools:
    """Holds all tool definitions and handlers for the Report Agent."""

    def __init__(self, outline_path: Path, data_root: Path):
        self.outline_path = Path(outline_path)
        self.data_root = Path(data_root)
        
        self._sections: list[Section] = []
        if self.outline_path.exists():
            self._sections = parse_outline(self.outline_path)
        
        self._catalog = DataCatalog(self.data_root)
        self._chart_reader = ChartReader(self._catalog)
        
        self._drafts: dict[str, str] = {}
        
        self._tool_handlers = {
            "get_section_context": self._get_section_context,
            "list_sections": self._list_sections,
            "write_section_draft": self._write_section_draft,
            "list_chart_categories": self._list_chart_categories,
            "list_charts": self._list_charts,
            "get_chart_metadata": self._get_chart_metadata,
            "get_chart_data": self._get_chart_data,
            "get_chart_image": self._get_chart_image,
        }

    def get_tool_schemas(self) -> list[dict]:
        """Return list of tool schemas for LLM function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_section_context",
                    "description": "Get full context for a section including title, instructions, current content, and review feedback",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section_id": {
                                "type": "string",
                                "description": "The section identifier (slug)"
                            }
                        },
                        "required": ["section_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_sections",
                    "description": "List all sections in the report outline for navigation",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_section_draft",
                    "description": "Write or update draft content for a section",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section_id": {
                                "type": "string",
                                "description": "The section identifier (slug)"
                            },
                            "content": {
                                "type": "string",
                                "description": "The markdown content for the section"
                            }
                        },
                        "required": ["section_id", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_chart_categories",
                    "description": "List available chart categories with count of charts in each",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_charts",
                    "description": "List available charts, optionally filtered by category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Optional category to filter charts by"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_chart_metadata",
                    "description": "Get full metadata for a chart including paths, dimensions, and units",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chart_id": {
                                "type": "string",
                                "description": "The chart identifier"
                            }
                        },
                        "required": ["chart_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_chart_data",
                    "description": "Get chart data with pre-computed summary and insights",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chart_id": {
                                "type": "string",
                                "description": "The chart identifier"
                            },
                            "include_rows": {
                                "type": "boolean",
                                "description": "Whether to include raw data rows"
                            }
                        },
                        "required": ["chart_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_chart_image",
                    "description": "Get chart image as base64 encoded PNG",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chart_id": {
                                "type": "string",
                                "description": "The chart identifier"
                            }
                        },
                        "required": ["chart_id"]
                    }
                }
            },
        ]

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return the result."""
        handler = self._tool_handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            return handler(**arguments)
        except Exception as e:
            return {"error": str(e)}

    def _find_section(self, section_id: str) -> Section | None:
        """Find a section by ID."""
        for section in self._sections:
            if section.id == section_id:
                return section
        return None

    def _get_section_context(self, section_id: str) -> dict:
        """Get full context for a section."""
        section = self._find_section(section_id)
        if section is None:
            return {"error": f"Section not found: {section_id}"}
        
        draft_content = self._drafts.get(section_id)
        
        return {
            "section_id": section.id,
            "title": section.title,
            "level": section.level,
            "instructions": section.instructions,
            "content": section.content,
            "draft_content": draft_content,
            "review_comments": section.review_comments,
            "review_ratings": section.review_ratings,
            "review_notes": section.review_notes,
            "parent_id": section.parent_id,
        }

    def _list_sections(self) -> list[dict]:
        """List all sections for navigation."""
        return [
            {
                "id": section.id,
                "title": section.title,
                "level": section.level,
                "parent_id": section.parent_id,
            }
            for section in self._sections
        ]

    def _write_section_draft(self, section_id: str, content: str) -> dict:
        """Store draft content for a section."""
        section = self._find_section(section_id)
        if section is None:
            return {"success": False, "error": f"Section not found: {section_id}"}
        
        self._drafts[section_id] = content
        return {"success": True, "section_id": section_id}

    def _list_chart_categories(self) -> list[dict]:
        """List chart categories with counts."""
        categories = self._catalog.list_categories()
        result = []
        for cat in categories:
            charts = self._catalog.list_charts(category=cat)
            result.append({"id": cat, "chart_count": len(charts)})
        return result

    def _list_charts(self, category: str | None = None) -> list[dict]:
        """List charts, optionally filtered by category."""
        charts = self._catalog.list_charts(category=category)
        return [
            {
                "id": chart.id,
                "title": chart.title,
                "category": chart.category,
                "units": chart.units,
            }
            for chart in charts
        ]

    def _get_chart_metadata(self, chart_id: str) -> dict:
        """Get full metadata for a chart."""
        chart = self._catalog.get_chart(chart_id)
        if chart is None:
            return {"error": f"Chart not found: {chart_id}"}
        
        return {
            "id": chart.id,
            "category": chart.category,
            "title": chart.title,
            "path_csv": str(chart.path_csv) if chart.path_csv else None,
            "path_png": str(chart.path_png) if chart.path_png else None,
            "path_json": str(chart.path_json) if chart.path_json else None,
            "dimensions": chart.dimensions,
            "measures": chart.measures,
            "units": chart.units,
            "filter_expression": chart.filter_expression,
            "scenarios": chart.scenarios,
        }

    def _get_chart_data(self, chart_id: str, include_rows: bool = False) -> dict:
        """Get chart data with pre-computed summary."""
        chart = self._catalog.get_chart(chart_id)
        if chart is None:
            return {"error": f"Chart not found: {chart_id}"}
        
        try:
            summary = self._chart_reader.get_summary(chart_id)
        except ValueError as e:
            return {"error": str(e)}
        
        result = {
            "chart_id": summary.chart_id,
            "title": summary.title,
            "dimensions": summary.dimensions,
            "measure": summary.measure,
            "measure_type": summary.measure_type,
            "units": summary.units,
            "scenarios": summary.scenarios,
            "years": summary.years,
            "row_count": summary.row_count,
            "by_scenario": summary.by_scenario,
            "key_insights": summary.key_insights,
        }
        
        if include_rows:
            try:
                df = self._chart_reader.load_data(chart_id)
                result["rows"] = df.to_dict(orient="records")
            except ValueError:
                result["rows"] = []
        
        return result

    def _get_chart_image(self, chart_id: str) -> dict:
        """Get chart image as base64."""
        chart = self._catalog.get_chart(chart_id)
        if chart is None:
            return {"error": f"Chart not found: {chart_id}"}
        
        image_b64 = self._chart_reader.get_image_base64(chart_id)
        if image_b64 is None:
            return {"error": f"No image found for chart: {chart_id}"}
        
        return {
            "chart_id": chart_id,
            "image_base64": image_b64,
            "format": "png",
        }

    def get_draft(self, section_id: str) -> str | None:
        """Get draft content for a section (for external access)."""
        return self._drafts.get(section_id)

    def get_all_drafts(self) -> dict[str, str]:
        """Get all draft content (for external access)."""
        return self._drafts.copy()
