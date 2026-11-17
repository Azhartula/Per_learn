"""Load and query the Year 5 fraction question bank."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BANK = Path(__file__).resolve().parents[2] / "data" / "questions" / "year5_fractions.json"

# Map ASSISTments / Phase 1 skill names → bank skill ids.
SKILL_ALIASES = {
    "Multiplication Fractions": "multiply_fractions",
    "Ordering Fractions": "ordering_fractions",
    "Addition and Subtraction Fractions": "add_subtract_fractions",
    "Equivalent Fractions": "equivalent_fractions",
    "Fraction Of": "fraction_of",
    "Division Fractions": "multiply_fractions",  # closest demo overlap
    "Conversion of Fraction Decimals Percents": "equivalent_fractions",
}


@dataclass(frozen=True)
class Question:
    id: str
    skill: str
    difficulty: int
    misconceptions: tuple[str, ...]
    stem: str
    type: str
    answer: Any
    answer_sympy: Any
    explanation: str
    choices: tuple[str, ...] | None = None
    form: str = "A"
    distractor_misconceptions: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Question:
        choices = d.get("choices")
        dmap = d.get("distractor_misconceptions") or {}
        return cls(
            id=d["id"],
            skill=d["skill"],
            difficulty=int(d.get("difficulty", 1)),
            misconceptions=tuple(d.get("misconceptions") or ()),
            stem=d["stem"],
            type=d.get("type", "fill"),
            answer=d["answer"],
            answer_sympy=d.get("answer_sympy"),
            explanation=d.get("explanation", ""),
            choices=tuple(choices) if choices else None,
            form=str(d.get("form") or "A"),
            distractor_misconceptions=dict(dmap) if dmap else None,
        )


@dataclass
class QuestionBank:
    skills: list[str]
    misconceptions: dict[str, str]
    items: list[Question]
    path: Path

    @classmethod
    def load(cls, path: str | Path | None = None) -> QuestionBank:
        path = Path(path) if path else DEFAULT_BANK
        raw = json.loads(path.read_text(encoding="utf-8"))
        misc = {m["id"]: m["label"] for m in raw.get("misconceptions", [])}
        items = [Question.from_dict(x) for x in raw["items"]]
        return cls(
            skills=list(raw.get("skills", [])),
            misconceptions=misc,
            items=items,
            path=path,
        )

    def by_skill(self, skill: str) -> list[Question]:
        skill = SKILL_ALIASES.get(skill, skill)
        return [q for q in self.items if q.skill == skill]

    def by_form(self, form: str, skill: str | None = None) -> list[Question]:
        form = form.upper()
        items = self.items if skill is None else self.by_skill(skill)
        return [q for q in items if q.form.upper() == form]

    def by_misconception(self, misconception_id: str) -> list[Question]:
        return [q for q in self.items if misconception_id in q.misconceptions]

    def misconception_from_response(self, question: Question, response: Any) -> list[str]:
        """Map a selected distractor to misconception ids (not 'any wrong ⇒ all tags')."""
        if question.distractor_misconceptions:
            key = str(response).strip()
            mid = question.distractor_misconceptions.get(key)
            if mid:
                return [mid]
            # try normalized match
            for choice, mid in question.distractor_misconceptions.items():
                if str(choice).strip().lower() == key.lower():
                    return [mid]
        return []

    def get(self, item_id: str) -> Question:
        for q in self.items:
            if q.id == item_id:
                return q
        raise KeyError(item_id)

    def pick_lesson_set(
        self,
        skill: str,
        misconception_id: str | None = None,
        n_practice: int = 3,
        n_examples: int = 1,
    ) -> dict[str, list[Question]]:
        """Pick worked example(s) + practice items for a lesson."""
        pool = self.by_skill(skill)
        if not pool:
            raise ValueError(f"No questions for skill: {skill}")

        tagged = (
            [q for q in pool if misconception_id and misconception_id in q.misconceptions]
            if misconception_id
            else []
        )
        preferred = tagged or pool
        preferred = sorted(preferred, key=lambda q: q.difficulty)

        examples = preferred[:n_examples]
        rest = [q for q in preferred if q not in examples]
        if len(rest) < n_practice:
            rest = rest + [q for q in pool if q not in examples and q not in rest]
        practice = rest[:n_practice]
        return {"examples": examples, "practice": practice}

    def summary(self) -> str:
        lines = [f"Question bank: {self.path.name} ({len(self.items)} items)"]
        for skill in self.skills:
            n = len(self.by_skill(skill))
            lines.append(f"  {skill}: {n}")
        return "\n".join(lines)
