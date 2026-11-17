"""Load and fill teaching-method prompt templates."""

from __future__ import annotations

from pathlib import Path

from pll.config import METHODS
from pll.questions import Question

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "content" / "prompts"

METHOD_FILES = {
    "worked_example": "worked_example.txt",
    "problem_first": "problem_first.txt",
    "visual": "visual.txt",
    "story_analogy": "story_analogy.txt",
}

SKILL_LABELS = {
    "equivalent_fractions": "equivalent fractions",
    "ordering_fractions": "ordering and comparing fractions",
    "add_subtract_fractions": "adding and subtracting fractions",
    "multiply_fractions": "multiplying fractions",
    "fraction_of": "finding a fraction of a quantity",
    "mixed_improper": "mixed numbers and improper fractions",
}


def load_template(method: str) -> str:
    if method not in METHOD_FILES:
        raise ValueError(f"Unknown method {method!r}. Choose from {METHODS}")
    path = PROMPTS_DIR / METHOD_FILES[method]
    return path.read_text(encoding="utf-8")


def _practice_block(questions: list[Question]) -> str:
    lines = []
    for q in questions:
        choice_bit = ""
        if q.choices:
            choice_bit = " | choices: " + ", ".join(q.choices)
        lines.append(
            f"- id={q.id} | {q.stem}{choice_bit} | CORRECT_ANSWER={q.answer}"
        )
    return "\n".join(lines)


def _answer_key(example: Question, practice: list[Question]) -> str:
    rows = [f"- example {example.id}: {example.answer}"]
    for q in practice:
        rows.append(f"- {q.id}: {q.answer}")
    return "\n".join(rows)


def build_prompt(
    method: str,
    skill: str,
    misconception: str,
    example: Question,
    practice: list[Question],
) -> str:
    template = load_template(method)
    return template.format(
        skill=SKILL_LABELS.get(skill, skill),
        misconception=misconception,
        n_practice=len(practice),
        answer_key=_answer_key(example, practice),
        practice_block=_practice_block(practice),
    )
