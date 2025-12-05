"""Prompt templates for report generation.

This module provides utilities for loading and formatting prompt templates
from external files, making it easy to iterate on prompts without changing code.

Templates use Python's str.format() syntax for variable substitution:
- {variable_name} - replaced with the value
- Use {{ and }} to escape literal braces
"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template by name.
    
    Args:
        name: Prompt filename without extension, or with extension.
              e.g., "system", "section_generation", "system.txt"
    
    Returns:
        The prompt template as a string.
    
    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    if "." not in name:
        for ext in [".txt", ".md"]:
            path = PROMPTS_DIR / f"{name}{ext}"
            if path.exists():
                return path.read_text()
        raise FileNotFoundError(f"Prompt '{name}' not found in {PROMPTS_DIR}")
    
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def format_prompt(name: str, **kwargs) -> str:
    """Load and format a prompt template with the given variables.
    
    Args:
        name: Prompt filename (see load_prompt)
        **kwargs: Variables to substitute in the template
    
    Returns:
        The formatted prompt string.
    """
    template = load_prompt(name)
    return template.format(**kwargs)


def get_system_prompt() -> str:
    """Get the system prompt for the LLM."""
    return load_prompt("system").strip()
