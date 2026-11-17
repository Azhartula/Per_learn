#!/usr/bin/env python3
"""Phase 3: live loop — diagnose → bandit method → lesson → delayed check → parent summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.config import METHODS
from pll.loop import run_session, save_session
from pll.prompts import SKILL_LABELS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="Alex", help="Student display name")
    parser.add_argument(
        "--mode",
        choices=("demo", "interactive"),
        default="demo",
        help="demo = simulated student; interactive = type answers in the terminal",
    )
    parser.add_argument("--items", type=int, default=8, help="Diagnostic length")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "sessions"))
    args = parser.parse_args()

    print("=" * 60)
    print("Personalized Learning Loop — Phase 3 live session")
    print(f"Student: {args.name}  |  mode: {args.mode}")
    print("=" * 60)

    session = run_session(
        student_name=args.name,
        mode=args.mode,
        n_diagnostic=args.items,
        seed=args.seed,
        use_llm=args.llm,
    )

    print("\n--- Diagnostic ---")
    print(
        f"Score: {session.diagnostic.n_correct}/{session.diagnostic.n_items}  "
        f"ability≈{session.diagnostic.ability:.0%}"
    )
    print("Skill scores:")
    for skill, score in sorted(session.diagnostic.skill_scores.items(), key=lambda x: x[1]):
        label = SKILL_LABELS.get(skill, skill)
        print(f"  {score:.0%}  {label}")
    if session.diagnostic.active_misconceptions:
        print("Active misconceptions:", ", ".join(session.diagnostic.active_misconceptions[:3]))
    print(
        f"Weakest skill → teach: {SKILL_LABELS.get(session.diagnostic.weakest_skill, session.diagnostic.weakest_skill)}"
    )

    print("\n--- Method pick (contextual bandit) ---")
    print(f"Chosen: {session.method}  (of {', '.join(METHODS)})")

    print("\n--- Lesson ---")
    print(f"Title: {session.lesson.title}")
    print(f"SymPy verified: {session.lesson.all_verified}  |  source: {session.lesson.source}")
    print(f"Targets: {session.lesson.misconception_label}")

    print("\n--- Delayed check (no help) ---")
    print(
        f"Score: {session.delayed.n_correct}/{session.delayed.n_items} "
        f"({session.delayed.score:.0%})  review_due={session.delayed.review_due}"
    )

    print("\n--- Parent summary ---")
    print(session.parent_summary)

    paths = save_session(session, args.out_dir)
    print("\nSaved:")
    for key, path in paths.items():
        print(f"  {key}: {path}")


if __name__ == "__main__":
    main()
