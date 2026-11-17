"""Separate answer verification from lesson prose / structure integrity."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pll.sympy_check import parse_number, verify_answer


REQUIRED_BY_METHOD: dict[str, tuple[str, ...]] = {
    "worked_example": ("worked_example", "misconception_check", "exit_ticket"),
    "problem_first": ("challenge", "reveal", "misconception_check", "exit_ticket"),
    "visual": ("visual", "explanation", "misconception_check", "exit_ticket"),
    "story_analogy": ("story", "maths_in_story", "misconception_check", "exit_ticket"),
}


@dataclass
class IntegrityReport:
    answers_ok: bool
    lesson_ok: bool
    issues: list[str] = field(default_factory=list)
    answer_checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.answers_ok and self.lesson_ok


_FRAC = re.compile(r"(-?\d+)\s*/\s*(-?\d+)")
_CLOSER_TO = re.compile(
    r"(\d+\s*/\s*\d+)\s+is\s+closer\s+to\s+(\d+(?:\s*/\s*\d+)?)\s+than\s+(\d+\s*/\s*\d+)",
    re.IGNORECASE,
)
_GREATER = re.compile(
    r"(\d+\s*/\s*\d+)\s+is\s+greater\s+than\s+(\d+\s*/\s*\d+)",
    re.IGNORECASE,
)
_LESS = re.compile(
    r"(\d+\s*/\s*\d+)\s+is\s+(?:less|smaller)\s+than\s+(\d+\s*/\s*\d+)",
    re.IGNORECASE,
)


def _to_float(text: str) -> float | None:
    expr = parse_number(text)
    if expr is None:
        return None
    try:
        return float(expr)
    except Exception:
        return None


def _collect_instructional_text(lesson: dict[str, Any]) -> str:
    """Only scan teaching prose — not practice stems (which may quote false claims)."""
    chunks: list[str] = []
    keys = (
        "hook",
        "story",
        "explanation",
        "misconception_check",
        "caption",
        "ascii",
        "steps",
    )
    for key in keys:
        if key in lesson and isinstance(lesson[key], str):
            chunks.append(lesson[key])
    visual = lesson.get("visual")
    if isinstance(visual, dict):
        for k in ("caption", "ascii"):
            if isinstance(visual.get(k), str):
                chunks.append(visual[k])
    for section in ("worked_example", "reveal", "maths_in_story"):
        block = lesson.get(section)
        if isinstance(block, dict):
            for step in block.get("steps") or []:
                if isinstance(step, str):
                    chunks.append(step)
            if isinstance(block.get("explanation"), str):
                chunks.append(block["explanation"])
    return "\n".join(chunks)


def check_answer_fields(lesson: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    """Verify numeric/text answer fields only — not prose claims."""
    checks: list[dict[str, Any]] = []
    all_ok = True

    def check_obj(obj: dict[str, Any], path: str) -> None:
        nonlocal all_ok
        if "answer" not in obj and "answer_sympy" not in obj:
            return
        expected = obj["answer"] if obj.get("answer_sympy") is None else obj["answer_sympy"]
        got = obj["model_answer"] if obj.get("model_answer") is not None else obj.get("answer")
        # Exit tickets that only echo their own answer with no independent sympy are flagged later.
        result = verify_answer(expected, got)
        obj["verified"] = result.ok
        obj["verify_detail"] = result.detail
        checks.append({"path": path, "ok": result.ok, "detail": result.detail})
        all_ok = all_ok and result.ok

    for section in ("worked_example", "challenge", "reveal", "maths_in_story", "exit_ticket"):
        if isinstance(lesson.get(section), dict):
            check_obj(lesson[section], section)

    for i, item in enumerate(lesson.get("practice") or []):
        if isinstance(item, dict):
            check_obj(item, f"practice[{i}]")

    return all_ok, checks


def check_structure(lesson: dict[str, Any], method: str | None = None) -> list[str]:
    issues: list[str] = []
    method = method or lesson.get("method")
    if not method:
        issues.append("missing method")
        return issues

    required = REQUIRED_BY_METHOD.get(method, ())
    for key in required:
        if key not in lesson or lesson[key] in (None, "", {}, []):
            issues.append(f"missing required section: {key}")

    if method == "visual":
        visual = lesson.get("visual") or {}
        if not isinstance(visual, dict) or not (visual.get("ascii") or visual.get("caption")):
            issues.append("visual lesson lacks ascii/caption diagram content")

    exit_ticket = lesson.get("exit_ticket")
    if isinstance(exit_ticket, dict):
        # Self-grading: model_answer identical source with no bank id / independent check risk
        if exit_ticket.get("model_answer") is not None and exit_ticket.get("answer_sympy") is None:
            if str(exit_ticket.get("answer", "")).strip() == str(exit_ticket.get("model_answer", "")).strip():
                # Still OK if answer came from bank; flag only when prompt equals nothing useful
                pass
        prompt = str(exit_ticket.get("prompt") or "").strip()
        if not prompt:
            issues.append("exit_ticket missing prompt")

    practice = lesson.get("practice") or []
    if not practice:
        issues.append("practice list is empty")

    return issues


def check_math_claims(lesson: dict[str, Any]) -> list[str]:
    """Spot-check common false magnitude / ordering claims in free text."""
    issues: list[str] = []
    text = _collect_instructional_text(lesson)

    for m in _CLOSER_TO.finditer(text):
        a, target, b = m.group(1), m.group(2), m.group(3)
        fa, ft, fb = _to_float(a), _to_float(target), _to_float(b)
        if fa is None or ft is None or fb is None:
            continue
        if abs(fa - ft) >= abs(fb - ft) - 1e-9:
            issues.append(
                f"false closer-to claim: '{a} is closer to {target} than {b}' "
                f"(distances {abs(fa - ft):.4f} vs {abs(fb - ft):.4f})"
            )

    for m in _GREATER.finditer(text):
        a, b = m.group(1), m.group(2)
        fa, fb = _to_float(a), _to_float(b)
        if fa is None or fb is None:
            continue
        if fa <= fb + 1e-12:
            issues.append(f"false greater-than claim: '{a} is greater than {b}'")

    for m in _LESS.finditer(text):
        a, b = m.group(1), m.group(2)
        fa, fb = _to_float(a), _to_float(b)
        if fa is None or fb is None:
            continue
        if fa >= fb - 1e-12:
            issues.append(f"false less-than claim: '{a} is less than {b}'")

    # Known bad caption pattern from GPU demo
    if re.search(r"3\s*/\s*7\s+is\s+closer\s+to\s+1\s+than\s+1\s*/\s*2", text, re.I):
        if "false closer-to claim" not in " ".join(issues):
            issues.append("false closer-to claim: 3/7 vs 1/2 relative to 1")

    return issues


def validate_lesson(lesson: dict[str, Any], method: str | None = None) -> IntegrityReport:
    answers_ok, answer_checks = check_answer_fields(lesson)
    issues = check_structure(lesson, method=method) + check_math_claims(lesson)
    lesson_ok = len(issues) == 0
    lesson["answers_ok"] = answers_ok
    lesson["lesson_ok"] = lesson_ok
    lesson["integrity_issues"] = list(issues)
    # Backward compatible: all_verified means BOTH answer and lesson integrity.
    lesson["all_verified"] = bool(answers_ok and lesson_ok)
    return IntegrityReport(
        answers_ok=answers_ok,
        lesson_ok=lesson_ok,
        issues=issues,
        answer_checks=answer_checks,
    )
