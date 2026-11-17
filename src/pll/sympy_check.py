"""Verify fraction answers with SymPy before they reach a student."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    expected: str
    got: str
    detail: str = ""


def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _mixed_to_improper(text: str) -> str | None:
    """Parse '1 1/4' or '1-1/4' into an improper fraction string."""
    m = re.fullmatch(r"(-?\d+)\s+(\d+)\s*/\s*(\d+)", text.strip())
    if not m:
        m = re.fullmatch(r"(-?\d+)\s*-\s*(\d+)\s*/\s*(\d+)", text.strip())
    if not m:
        return None
    whole, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
    sign = -1 if whole < 0 else 1
    whole = abs(whole)
    return str(sign * (whole * den + num)) + f"/{den}"


def parse_number(text: str) -> sp.Expr | None:
    """Parse a student/bank answer into a SymPy expression, or None if not numeric."""
    raw = _normalize_text(str(text))
    if raw in {"yes", "no", "true", "false", "equal", "they are equal"}:
        return None

    mixed = _mixed_to_improper(raw)
    if mixed:
        raw = mixed

    # Strip trailing punctuation / wrappers.
    raw = raw.strip(" .")
    raw = raw.replace("÷", "/").replace("×", "*").replace("·", "*")

    try:
        return sp.simplify(parse_expr(raw, transformations=TRANSFORMS, evaluate=True))
    except Exception:
        try:
            return sp.Rational(raw)
        except Exception:
            return None


def values_equal(a: Any, b: Any) -> bool:
    ea, eb = parse_number(a), parse_number(b)
    if ea is None or eb is None:
        return _normalize_text(str(a)) == _normalize_text(str(b))
    try:
        return bool(sp.simplify(sp.Eq(ea, eb)) is True or sp.simplify(ea - eb) == 0)
    except Exception:
        return False


def verify_answer(expected: Any, got: Any) -> CheckResult:
    """Compare one expected answer to a candidate (model or student)."""
    if isinstance(expected, list):
        # Multi-answer: every expected value must appear in got (order-insensitive).
        if not isinstance(got, list):
            got_list = [x.strip() for x in str(got).split(",") if x.strip()]
        else:
            got_list = list(got)
        missing = []
        for exp in expected:
            if not any(values_equal(exp, g) for g in got_list):
                missing.append(str(exp))
        ok = not missing
        return CheckResult(
            ok=ok,
            expected=str(expected),
            got=str(got),
            detail="missing: " + ", ".join(missing) if missing else "all match",
        )

    ok = values_equal(expected, got)
    return CheckResult(
        ok=ok,
        expected=str(expected),
        got=str(got),
        detail="numeric/text match" if ok else "mismatch",
    )


def verify_question_bank_item(answer: Any, answer_sympy: Any) -> CheckResult:
    """Sanity-check that bank answer and sympy field agree when both numeric."""
    if answer_sympy is None:
        return CheckResult(True, str(answer), str(answer), "no sympy field (text answer)")
    return verify_answer(answer_sympy, answer)


def verify_lesson_answers(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    For each lesson item with expected + model_answer, attach verification.
    Items without model_answer are checked against their own answer_sympy.
    """
    results = []
    for item in items:
        expected = item.get("answer_sympy", item.get("answer"))
        got = item.get("model_answer", item.get("answer"))
        check = verify_answer(expected, got)
        results.append({**item, "verified": check.ok, "verify_detail": check.detail})
    return results
