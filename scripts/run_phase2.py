#!/usr/bin/env python3
"""Phase 2: question bank + method prompts + SymPy-verified lessons."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.config import METHODS
from pll.lessons import generate_lesson, render_lesson_markdown, save_lesson
from pll.questions import QuestionBank
from pll.sympy_check import verify_question_bank_item


def validate_bank(bank: QuestionBank) -> list[str]:
    problems = []
    for q in bank.items:
        if q.answer_sympy is None:
            continue
        check = verify_question_bank_item(q.answer, q.answer_sympy)
        if not check.ok:
            problems.append(f"{q.id}: answer={q.answer!r} sympy={q.answer_sympy!r} ({check.detail})")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method",
        choices=METHODS,
        default=None,
        help="Teaching method (default: generate all four)",
    )
    parser.add_argument("--skill", default="multiply_fractions")
    parser.add_argument("--misconception", default=None)
    parser.add_argument("--llm", action="store_true", help="Call OpenAI-compatible API")
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "lessons"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    bank = QuestionBank.load()
    print(bank.summary())
    print()

    problems = validate_bank(bank)
    if problems:
        print("Bank SymPy mismatches:")
        for p in problems:
            print(" ", p)
        if args.validate_only:
            sys.exit(1)
    else:
        print(f"Bank validation: all {sum(1 for q in bank.items if q.answer_sympy is not None)} numeric items OK")

    if args.validate_only:
        return

    methods = [args.method] if args.method else list(METHODS)
    out_dir = Path(args.out_dir)
    summary = []

    for method in methods:
        lesson = generate_lesson(
            method=method,
            skill=args.skill,
            misconception_id=args.misconception,
            bank=bank,
            use_llm=args.llm,
        )
        json_path = save_lesson(lesson, out_dir)
        md_path = out_dir / f"{lesson.skill}__{lesson.method}.md"
        md_path.write_text(render_lesson_markdown(lesson), encoding="utf-8")
        print(
            f"\n[{method}] verified={lesson.all_verified} source={lesson.source}\n"
            f"  JSON: {json_path}\n  MD:   {md_path}"
        )
        summary.append(
            {
                "method": method,
                "skill": lesson.skill,
                "misconception": lesson.misconception_id,
                "all_verified": lesson.all_verified,
                "source": lesson.source,
                "practice_n": len(lesson.practice),
            }
        )

    summary_path = out_dir / "phase2_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
