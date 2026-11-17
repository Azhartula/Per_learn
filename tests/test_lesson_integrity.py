"""Lesson integrity: answers vs prose claims."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pll.lesson_integrity import validate_lesson
from pll.lessons import generate_lesson


def test_false_closer_claim_fails_lesson_ok():
    lesson = {
        "method": "visual",
        "visual": {
            "type": "fraction_bars",
            "ascii": "[##..] 1/2",
            "caption": "Notice how 3/7 is closer to 1 than 1/2, despite having a larger denominator.",
        },
        "explanation": "Bars help compare sizes.",
        "misconception_check": "Bigger denominator is not always bigger.",
        "exit_ticket": {"prompt": "Which is greater: 1/2 or 1/3?", "answer": "1/2"},
        "practice": [
            {"id": "x", "prompt": "q", "answer": "1/2", "answer_sympy": "1/2"},
        ],
    }
    report = validate_lesson(lesson, method="visual")
    assert report.answers_ok is True
    assert report.lesson_ok is False
    assert any("closer" in i.lower() for i in report.issues)
    assert lesson["all_verified"] is False


def test_template_lessons_pass_integrity():
    for method in ("worked_example", "problem_first", "visual", "story_analogy"):
        lesson = generate_lesson(method=method, skill="ordering_fractions", use_ollama=False)
        assert lesson.answers_ok, (method, lesson.integrity_issues)
        assert lesson.lesson_ok, (method, lesson.integrity_issues)
        assert lesson.all_verified


def test_missing_visual_section_fails():
    lesson = {
        "method": "visual",
        "explanation": "text only",
        "misconception_check": "x",
        "exit_ticket": {"prompt": "p", "answer": "1"},
        "practice": [{"id": "a", "answer": "1"}],
    }
    report = validate_lesson(lesson)
    assert report.lesson_ok is False
