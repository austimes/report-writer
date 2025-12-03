import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Section:
    id: str
    title: str
    level: int
    instructions: str
    review_comments: str
    review_author: str
    review_ratings: dict
    review_notes: str
    parent_id: str | None
    content: str


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


def parse_review_block(text: str) -> tuple[str, dict, str]:
    """Parse review block, returning (author, ratings, notes)."""
    if not text or not text.strip():
        return "", {}, ""

    author = ""
    ratings = {}
    notes = ""

    lines = text.strip().split("\n")
    notes_started = False
    notes_lines = []

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.startswith("[EXAMPLE - LLM IGNORE:"):
            break

        if line_stripped.startswith("AUTHOR:"):
            author = line_stripped[7:].strip()
        elif line_stripped.startswith("RATING:"):
            rating_part = line_stripped[7:].strip()
            for pair in rating_part.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    value = value.strip()
                    if value:
                        try:
                            ratings[key.strip()] = int(value)
                        except ValueError:
                            pass
        elif line_stripped.startswith("NOTES:"):
            notes_started = True
            notes_content = line_stripped[6:].strip()
            if notes_content:
                notes_lines.append(notes_content)
        elif notes_started:
            notes_lines.append(line_stripped)

    notes = "\n".join(notes_lines).strip()
    return author, ratings, notes


def parse_outline(path: Path) -> list[Section]:
    content = path.read_text()

    sections: list[Section] = []
    parent_stack: list[tuple[int, str]] = []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    instruction_pattern = re.compile(r"<!--\s*Section instructions:\s*(.*?)\s*-->", re.DOTALL)
    review_pattern = re.compile(r"<!--\s*Review comments:\s*(.*?)\s*-->", re.DOTALL)

    headings = list(heading_pattern.finditer(content))

    for idx, match in enumerate(headings):
        level = len(match.group(1))
        title = match.group(2).strip()
        section_id = slugify(title)

        while parent_stack and parent_stack[-1][0] >= level:
            parent_stack.pop()

        parent_id = parent_stack[-1][1] if parent_stack else None
        parent_stack.append((level, section_id))

        start = match.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(content)
        section_text = content[start:end]

        instructions = ""
        instruction_match = instruction_pattern.search(section_text)
        if instruction_match:
            instructions = instruction_match.group(1).strip()

        review_comments = ""
        review_match = review_pattern.search(section_text)
        if review_match:
            review_comments = review_match.group(1).strip()

        review_author, review_ratings, review_notes = parse_review_block(review_comments)

        section_content = section_text
        section_content = instruction_pattern.sub("", section_content)
        section_content = review_pattern.sub("", section_content)
        section_content = section_content.strip()

        sections.append(
            Section(
                id=section_id,
                title=title,
                level=level,
                instructions=instructions,
                review_comments=review_comments,
                review_author=review_author,
                review_ratings=review_ratings,
                review_notes=review_notes,
                parent_id=parent_id,
                content=section_content,
            )
        )

    return sections
