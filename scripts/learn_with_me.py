#!/usr/bin/env python3
"""
Learn with me — YOU answer the questions; the system adapts how it teaches.

Flow each session:
  1. Short sample quiz (you answer)
  2. Bandit picks a teaching method from your mastery so far
  3. Lesson generated (local Qwen via Ollama, or template fallback)
  4. Practice — you answer
  5. Unassisted check — you answer (this trains the bandit)
  6. Profile saved; next session uses what it learned about you
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import make_context, mastery_bin
from pll.config import METHODS
from pll.diagnostic import run_diagnostic
from pll.learner import LEARNERS_DIR, adaptation_summary, load_or_create, save_profile, SessionRecord
from pll.lessons import generate_lesson, render_lesson_markdown
from pll.loop import interactive_answer_fn, run_delayed_check
from pll.ollama_client import is_reachable
from pll.parent_summary import METHOD_PLAIN
from pll.prompts import SKILL_LABELS
from pll.questions import QuestionBank
from pll.sympy_check import verify_answer


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _pause(msg: str = "Press Enter to continue…") -> None:
    input(f"\n{msg}")


def _show_lesson(markdown: str) -> None:
    print("\n" + "=" * 64)
    print(markdown)
    print("=" * 64)


def _practice_round(lesson, bank: QuestionBank) -> float:
    print("\n--- Practice (with the lesson above — try from memory if you can) ---")
    correct = 0
    total = 0
    for item in lesson.practice:
        total += 1
        q = bank.get(item["id"])
        print(f"\nPractice {total}: {q.stem}")
        if q.choices:
            for i, c in enumerate(q.choices):
                print(f"  {chr(65 + i)}) {c}")
        response = input("Your answer: ").strip()
        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        ok = verify_answer(expected, response).ok
        correct += int(ok)
        print("  ✓ correct" if ok else f"  ✗ not quite — answer was {q.answer}")
    return correct / max(total, 1)


def run_one_session(
    name: str,
    *,
    use_ollama: bool,
    model: str,
    n_diagnostic: int,
    learners_dir: Path,
) -> None:
    profile = load_or_create(name, learners_dir)
    bank = QuestionBank.load()
    bandit = profile.to_bandit(seed=profile.sessions_completed + 7)

    print("\n" + adaptation_summary(profile))
    print("\n--- Step 1: Sample questions (answer honestly) ---")
    print("These help estimate where you are right now.\n")

    diagnostic = run_diagnostic(
        bank,
        interactive_answer_fn,
        n_items=n_diagnostic,
        seed=1000 + profile.sessions_completed,
    )

    # Blend prior mastery with this diagnostic so progress is sticky.
    mastery_before = profile.mastery
    profile.mastery = float(np.clip(0.55 * profile.mastery + 0.45 * diagnostic.ability, 0.05, 0.95))
    profile.focus_skill = diagnostic.weakest_skill

    print(
        f"\nDiagnostic: {diagnostic.n_correct}/{diagnostic.n_items}  "
        f"mastery now ≈ {profile.mastery:.0%} "
        f"({['novice','intermediate','advanced'][mastery_bin(profile.mastery)]})"
    )
    print(f"Focus skill: {SKILL_LABELS.get(diagnostic.weakest_skill, diagnostic.weakest_skill)}")
    if diagnostic.active_misconceptions:
        print("Hints from misses:", ", ".join(diagnostic.active_misconceptions[:3]))

    context = make_context(profile.mastery)
    if int(bandit.counts.sum()) < 2:
        method_idx = int(np.argmax(bandit.mean_rewards(context)))
    else:
        method_idx = bandit.select(context)
    method = METHODS[method_idx]
    print(f"\n--- Step 2: Teaching method for you today ---")
    print(f"→ {METHOD_PLAIN[method]}")
    scores = {METHODS[i]: float(bandit.mean_rewards(context)[i]) for i in range(len(METHODS))}
    for m, s in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"   {METHOD_PLAIN[m]}: {s:.2f}")

    weak_miss: dict[str, int] = {}
    for t in diagnostic.trials:
        if t.skill == diagnostic.weakest_skill and not t.correct:
            for m in t.misconceptions:
                weak_miss[m] = weak_miss.get(m, 0) + 1
    misconception_id = (
        max(weak_miss, key=weak_miss.get)
        if weak_miss
        else (diagnostic.active_misconceptions[0] if diagnostic.active_misconceptions else None)
    )

    print("\n--- Step 3: Generating your lesson ---")
    if use_ollama:
        if not is_reachable():
            print("Ollama not reachable — using template lesson instead.")
            use_ollama = False
        else:
            print(f"Using local model {model}… (may take ~30–90s on GPU)")

    lesson = generate_lesson(
        method=method,
        skill=diagnostic.weakest_skill,
        misconception_id=misconception_id,
        bank=bank,
        use_ollama=use_ollama,
        ollama_model=model if use_ollama else None,
    )
    print(
        f"Lesson source: {lesson.source}  |  SymPy verified: {lesson.all_verified}"
        + (f"  |  model: {lesson.model_name}" if lesson.model_name else "")
    )
    _show_lesson(render_lesson_markdown(lesson))
    _pause("Read the lesson, then press Enter for practice…")

    practice_score = _practice_round(lesson, bank)
    print(f"\nPractice score: {practice_score:.0%} (not used to train the bandit)")

    print("\n--- Step 4: Unassisted check (no peeking) ---")
    print("This score trains how we teach you next time.\n")
    used = {t.question_id for t in diagnostic.trials} | {p["id"] for p in lesson.practice}
    delayed = run_delayed_check(
        bank,
        skill=diagnostic.weakest_skill,
        answer_fn=interactive_answer_fn,
        exclude_ids=used,
        n_items=3,
    )
    for item in delayed.items:
        mark = "✓" if item["correct"] else "✗"
        print(f"  {mark} {item['stem'][:70]}…  (you: {item['response']})")
    print(f"\nDelayed check: {delayed.n_correct}/{delayed.n_items} ({delayed.score:.0%})")

    # Bandit learns ONLY from delayed check.
    bandit.update(method_idx, context, delayed.score)
    profile.store_bandit(bandit)

    # Mastery nudge from delayed evidence.
    profile.mastery = float(
        np.clip(profile.mastery + 0.12 * (delayed.score - 0.5), 0.05, 0.95)
    )
    profile.sessions_completed += 1
    profile.history.append(
        SessionRecord(
            session=profile.sessions_completed,
            timestamp=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            mastery_before=round(mastery_before, 3),
            mastery_after=round(profile.mastery, 3),
            method=method,
            delayed_score=round(delayed.score, 3),
            skill=diagnostic.weakest_skill,
            diagnostic_score=f"{diagnostic.n_correct}/{diagnostic.n_items}",
            notes=f"practice={practice_score:.2f}; source={lesson.source}",
        )
    )
    path = save_profile(profile, learners_dir)

    print("\n" + "=" * 64)
    print("How I'm adapting to you")
    print("=" * 64)
    print(adaptation_summary(profile))
    print(f"\nSaved profile: {path}")
    print("Run again later — I'll keep learning from your answers.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=None, help="Your name / learner id")
    parser.add_argument("--items", type=int, default=5, help="Diagnostic sample size")
    parser.add_argument("--no-ollama", action="store_true", help="Template lessons only (skip GPU model)")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--status", action="store_true", help="Show profile and exit")
    parser.add_argument("--learners-dir", default=str(LEARNERS_DIR))
    args = parser.parse_args()

    learners_dir = Path(args.learners_dir)
    name = args.name or _ask("What should I call you", "Azhar")

    if args.status:
        profile = load_or_create(name, learners_dir)
        print(adaptation_summary(profile))
        if profile.history:
            print("\nSession history:")
            for h in profile.history:
                print(
                    f"  #{h.session}  mastery {h.mastery_before:.0%}→{h.mastery_after:.0%}  "
                    f"{h.method}  delayed={h.delayed_score:.0%}  skill={h.skill}"
                )
        return

    use_ollama = not args.no_ollama
    print("=" * 64)
    print("PerLearn — Learn with me")
    print("You answer. I adapt how I teach.")
    print("=" * 64)
    run_one_session(
        name,
        use_ollama=use_ollama,
        model=args.model,
        n_diagnostic=args.items,
        learners_dir=learners_dir,
    )


if __name__ == "__main__":
    main()
