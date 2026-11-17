#!/usr/bin/env python3
"""Validate every numeric answer in the question bank with SymPy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.questions import QuestionBank
from pll.sympy_check import verify_question_bank_item


def main() -> None:
    bank = QuestionBank.load()
    print(bank.summary())
    failed = 0
    checked = 0
    for q in bank.items:
        if q.answer_sympy is None:
            print(f"  skip text  {q.id}: {q.answer!r}")
            continue
        checked += 1
        result = verify_question_bank_item(q.answer, q.answer_sympy)
        mark = "OK" if result.ok else "FAIL"
        if not result.ok:
            failed += 1
        print(f"  {mark:4s} {q.id}: {q.answer!r} vs {q.answer_sympy!r}")
    print(f"\nChecked {checked}, failed {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
