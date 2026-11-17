#!/usr/bin/env python3
"""Protocol dry-run: N simulated learners through Session1 + Session2 (Form C).

Labeled respondent=simulated. Produces event logs + summary under outputs/pilot/.
Replace with human Session 2 for real delayed_24h evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import DiscountedContextualTS, make_context  # noqa: E402
from pll.config import CONTENT_VERSION, METHODS  # noqa: E402
from pll.diagnostic import make_simulated_student, run_diagnostic  # noqa: E402
from pll.events import append_event, log_item_response, new_session_id  # noqa: E402
from pll.lessons import generate_lesson  # noqa: E402
from pll.questions import QuestionBank  # noqa: E402
from pll.sympy_check import verify_answer  # noqa: E402


def _pick_form(bank: QuestionBank, skill: str, form: str, n: int, exclude: set[str]) -> list:
    pool = [q for q in bank.by_form(form, skill) if q.id not in exclude]
    if len(pool) < n:
        pool = [q for q in bank.by_skill(skill) if q.id not in exclude and q.form == form] or [
            q for q in bank.by_skill(skill) if q.id not in exclude
        ]
    return sorted(pool, key=lambda q: (q.difficulty, q.id))[:n]


def run_one(learner: str, arm: str, bank: QuestionBank, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    session_id = new_session_id()
    answer_fn = make_simulated_student(true_ability=0.38 + 0.02 * (seed % 5), seed=seed)
    append_event(
        session_id,
        "session_start",
        learner_id=learner,
        payload={
            "mode": "pilot_dryrun",
            "arm": arm,
            "content_version": CONTENT_VERSION,
            "respondent": "simulated",
            "note": "Protocol dry-run — not human delayed evidence",
        },
    )

    # Prefer Form A items by biasing pick: temporarily filter bank skills via diagnostic on full bank
    diagnostic = run_diagnostic(bank, answer_fn, n_items=6, seed=seed)
    for t in diagnostic.trials:
        log_item_response(
            session_id,
            learner_id=learner,
            item_id=t.question_id,
            skill=t.skill,
            method=None,
            response=t.response,
            correct=t.correct,
            outcome_type="diagnostic",
            content_version=CONTENT_VERSION,
            respondent="simulated",
            extra={"arm": arm, "form_pref": "A"},
        )

    skill = diagnostic.weakest_skill
    context = make_context(diagnostic.ability)
    bandit = DiscountedContextualTS(rng=rng, warm_start=False)
    if arm == "fixed_worked_example":
        method_idx = 0
    else:
        # Thompson sample so dry-run explores methods (flat priors).
        method_idx = bandit.select(context)
    method = METHODS[method_idx]
    append_event(
        session_id,
        "method_selected",
        learner_id=learner,
        payload={"method": method, "method_index": method_idx, "arm": arm, "context": context.tolist()},
    )

    lesson = generate_lesson(method=method, skill=skill, bank=bank, use_ollama=False)
    used = {t.question_id for t in diagnostic.trials} | {p["id"] for p in lesson.practice}

    # Immediate post Form B
    post_items = _pick_form(bank, skill, "B", 3, used)
    immediate_correct = 0
    for q in post_items:
        resp = answer_fn(q)
        ok = verify_answer(q.answer_sympy if q.answer_sympy is not None else q.answer, resp).ok
        immediate_correct += int(ok)
        used.add(q.id)
        log_item_response(
            session_id,
            learner_id=learner,
            item_id=q.id,
            skill=skill,
            method=method,
            response=resp,
            correct=ok,
            outcome_type="immediate_post",
            content_version=CONTENT_VERSION,
            respondent="simulated",
            extra={"arm": arm, "form": q.form},
        )
    immediate_score = immediate_correct / max(len(post_items), 1)

    # Session 2 — Form C delayed_24h (simulated clock; still labeled simulated)
    delayed_items = _pick_form(bank, skill, "C", 3, used)
    delayed_correct = 0
    for q in delayed_items:
        resp = answer_fn(q)
        ok = verify_answer(q.answer_sympy if q.answer_sympy is not None else q.answer, resp).ok
        delayed_correct += int(ok)
        log_item_response(
            session_id,
            learner_id=learner,
            item_id=q.id,
            skill=skill,
            method=method,
            response=resp,
            correct=ok,
            outcome_type="delayed_24h",
            content_version=CONTENT_VERSION,
            respondent="simulated",
            extra={"arm": arm, "form": q.form, "gap_hours_claimed": 36},
        )
    delayed_score = delayed_correct / max(len(delayed_items), 1)
    if arm == "adaptive_method":
        bandit.update(method_idx, context, delayed_score)

    append_event(
        session_id,
        "session_end",
        learner_id=learner,
        payload={
            "arm": arm,
            "method": method,
            "skill": skill,
            "immediate_score": immediate_score,
            "delayed_score": delayed_score,
            "lesson_ok": lesson.lesson_ok,
            "answers_ok": lesson.answers_ok,
            "respondent": "simulated",
        },
    )
    return {
        "learner": learner,
        "session_id": session_id,
        "arm": arm,
        "method": method,
        "skill": skill,
        "immediate_score": immediate_score,
        "delayed_score": delayed_score,
        "lesson_ok": lesson.lesson_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "pilot"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bank = QuestionBank.load()

    rows = []
    for i in range(args.n):
        arm = "adaptive_method" if i % 2 == 0 else "fixed_worked_example"
        learner = f"dryrun_{i:02d}"
        row = run_one(learner, arm, bank, seed=args.seed + i * 17)
        rows.append(row)
        print(f"{learner} {arm} delayed={row['delayed_score']:.0%} method={row['method']}")

    summary = {
        "note": "SIMULATED protocol dry-run. Not human efficacy evidence.",
        "n": args.n,
        "seed": args.seed,
        "content_version": CONTENT_VERSION,
        "rows": rows,
        "by_arm": {},
    }
    for arm in ("adaptive_method", "fixed_worked_example"):
        scores = [r["delayed_score"] for r in rows if r["arm"] == arm]
        summary["by_arm"][arm] = {
            "n": len(scores),
            "mean_delayed": float(np.mean(scores)) if scores else None,
            "std_delayed": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0,
        }

    path = out_dir / "dryrun_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "DRYRUN_README.md").write_text(
        "\n".join(
            [
                "# Pilot dry-run",
                "",
                "This run uses **simulated respondents** to validate forms, event schema, and analysis.",
                "Replace with consented humans and true 24–72h gaps before claiming delayed learning outcomes.",
                "",
                f"See `{path.name}` and `outputs/events/`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
