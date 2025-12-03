import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from .outline_parser import parse_outline, Section


@dataclass
class SectionEval:
    section_id: str
    title: str
    ratings: dict[str, int]
    notes: str
    draft_length: int


@dataclass
class EvalRun:
    run_id: str
    timestamp: str
    model: str
    prompt_version: str
    outline_path: str
    data_root: str
    sections: list[SectionEval]
    aggregate: dict[str, float] = field(default_factory=dict)


RATING_DIMENSIONS = ["accuracy", "completeness", "clarity", "data_use"]


class EvalRunner:
    def __init__(self, outline_path: Path):
        self.outline_path = outline_path
        self._sections: list[Section] | None = None

    @property
    def sections(self) -> list[Section]:
        if self._sections is None:
            self._sections = parse_outline(self.outline_path)
        return self._sections

    def parse_reviews(self) -> list[SectionEval]:
        results = []
        for section in self.sections:
            if section.review_ratings:
                results.append(
                    SectionEval(
                        section_id=section.id,
                        title=section.title,
                        ratings=section.review_ratings,
                        notes=section.review_notes,
                        draft_length=len(section.content),
                    )
                )
        return results

    def compute_aggregate(self, sections: list[SectionEval]) -> dict[str, float]:
        if not sections:
            return {}

        dimension_sums: dict[str, float] = {dim: 0.0 for dim in RATING_DIMENSIONS}
        dimension_counts: dict[str, int] = {dim: 0 for dim in RATING_DIMENSIONS}

        for section in sections:
            for dim in RATING_DIMENSIONS:
                if dim in section.ratings:
                    dimension_sums[dim] += section.ratings[dim]
                    dimension_counts[dim] += 1

        aggregate: dict[str, float] = {}
        total_sum = 0.0
        total_count = 0

        for dim in RATING_DIMENSIONS:
            if dimension_counts[dim] > 0:
                avg = dimension_sums[dim] / dimension_counts[dim]
                aggregate[dim] = round(avg, 2)
                total_sum += dimension_sums[dim]
                total_count += dimension_counts[dim]

        if total_count > 0:
            aggregate["overall"] = round(total_sum / total_count, 3)

        return aggregate

    def run_eval(
        self,
        run_id: str,
        model: str = "unknown",
        prompt_version: str = "v1.0",
    ) -> EvalRun:
        sections = self.parse_reviews()
        aggregate = self.compute_aggregate(sections)

        data_root = ""
        parent = self.outline_path.parent
        if parent.name and parent.exists():
            data_root = str(parent)

        return EvalRun(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            prompt_version=prompt_version,
            outline_path=str(self.outline_path),
            data_root=data_root,
            sections=sections,
            aggregate=aggregate,
        )

    def save_results(self, eval_run: EvalRun, output_path: Path) -> None:
        data = asdict(eval_run)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2))

    def load_results(self, path: Path) -> EvalRun:
        data = json.loads(path.read_text())
        sections = [SectionEval(**s) for s in data.pop("sections")]
        return EvalRun(sections=sections, **data)


def compare_runs(run1: EvalRun, run2: EvalRun) -> dict:
    comparison: dict = {
        "run1_id": run1.run_id,
        "run2_id": run2.run_id,
        "run1_timestamp": run1.timestamp,
        "run2_timestamp": run2.timestamp,
        "dimension_deltas": {},
        "section_deltas": {},
        "summary": {},
    }

    all_dims = set(run1.aggregate.keys()) | set(run2.aggregate.keys())
    for dim in all_dims:
        val1 = run1.aggregate.get(dim, 0.0)
        val2 = run2.aggregate.get(dim, 0.0)
        delta = round(val2 - val1, 3)
        comparison["dimension_deltas"][dim] = {
            "run1": val1,
            "run2": val2,
            "delta": delta,
            "improved": delta > 0,
        }

    run1_sections = {s.section_id: s for s in run1.sections}
    run2_sections = {s.section_id: s for s in run2.sections}
    all_section_ids = set(run1_sections.keys()) | set(run2_sections.keys())

    for sid in all_section_ids:
        s1 = run1_sections.get(sid)
        s2 = run2_sections.get(sid)
        section_delta: dict = {"run1": None, "run2": None, "rating_deltas": {}}

        if s1:
            section_delta["run1"] = asdict(s1)
        if s2:
            section_delta["run2"] = asdict(s2)

        if s1 and s2:
            for dim in RATING_DIMENSIONS:
                v1 = s1.ratings.get(dim)
                v2 = s2.ratings.get(dim)
                if v1 is not None and v2 is not None:
                    section_delta["rating_deltas"][dim] = v2 - v1

        comparison["section_deltas"][sid] = section_delta

    overall1 = run1.aggregate.get("overall", 0.0)
    overall2 = run2.aggregate.get("overall", 0.0)
    overall_delta = round(overall2 - overall1, 3)

    improved_dims = sum(
        1
        for d in comparison["dimension_deltas"].values()
        if d.get("delta", 0) > 0
    )
    regressed_dims = sum(
        1
        for d in comparison["dimension_deltas"].values()
        if d.get("delta", 0) < 0
    )

    comparison["summary"] = {
        "overall_delta": overall_delta,
        "overall_improved": overall_delta > 0,
        "dimensions_improved": improved_dims,
        "dimensions_regressed": regressed_dims,
    }

    return comparison
