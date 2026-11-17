#!/usr/bin/env python3
"""Run a Qwen learner-agent cohort through the delayed teaching-method loop.

This is the AI-platform proof path (respondent=llm_agent): agent learners
exercise diagnose → teach → delayed check → adapt — not a volunteer study.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import DiscountedContextualTS, make_context  # noqa: E402
from pll.config import CONTENT_VERSION, METHODS  # noqa: E402
from pll.diagnostic import run_diagnostic  # noqa: E402
from pll.events import append_event, log_item_response, new_session_id  # noqa: E402
from pll.learner_agent import LearnerAgent, agent_to_dict, make_cohort  # noqa: E402
from pll.lessons import generate_lesson, render_lesson_markdown  # noqa: E402
from pll.ollama_client import DEFAULT_MODEL, is_reachable  # noqa: E402
from pll.questions import QuestionBank  # noqa: E402
from pll.sympy_check import verify_answer  # noqa: E402


def _pick_form(bank: QuestionBank, skill: str, form: str, n: int, exclude: set[str]):
    pool = [q for q in bank.by_form(form, skill) if q.id not in exclude]
    if len(pool) < n:
        pool = [q for q in bank.by_skill(skill) if q.id not in exclude]
    return sorted(pool, key=lambda q: (q.difficulty, q.id))[:n]


def run_one(
    idx: int,
    persona,
    arm: str,
    bank: QuestionBank,
    *,
    model: str,
    seed: int,
    n_diag: int,
) -> dict:
    t0 = time.time()
    learner_id = f"qwen_{idx:02d}_{persona.id}"
    agent = LearnerAgent(persona, model=model, seed=seed)
    session_id = new_session_id()
    rng = np.random.default_rng(seed)

    append_event(
        session_id,
        "session_start",
        learner_id=learner_id,
        payload={
            "mode": "qwen_agent_pilot",
            "arm": arm,
            "content_version": CONTENT_VERSION,
            "respondent": "llm_agent",
            "model_id": model,
            "persona": agent_to_dict(persona),
            "note": "Synthetic Qwen agents — not human delayed evidence",
        },
    )

    print(f"\n=== {learner_id} arm={arm} persona={persona.id} ===", flush=True)
    diagnostic = run_diagnostic(bank, agent.answer_fn("diagnostic"), n_items=n_diag, seed=seed)
    for t in diagnostic.trials:
        log_item_response(
            session_id,
            learner_id=learner_id,
            item_id=t.question_id,
            skill=t.skill,
            method=None,
            response=t.response,
            correct=t.correct,
            outcome_type="diagnostic",
            content_version=CONTENT_VERSION,
            model_id=model,
            respondent="llm_agent",
            extra={"arm": arm, "persona": persona.id},
        )
    print(
        f"  diagnostic {diagnostic.n_correct}/{diagnostic.n_items} "
        f"weak={diagnostic.weakest_skill}",
        flush=True,
    )

    skill = diagnostic.weakest_skill
    context = make_context(diagnostic.ability)
    bandit = DiscountedContextualTS(rng=rng, warm_start=False)
    if arm == "fixed_worked_example":
        method_idx = 0
    elif arm == "matched_bias":
        # Oracle-ish: assign the persona's preferred style (upper-bound stress test)
        method_idx = METHODS.index(persona.style_bias) if persona.style_bias in METHODS else 0
    else:
        method_idx = bandit.select(context)
    method = METHODS[method_idx]
    append_event(
        session_id,
        "method_selected",
        learner_id=learner_id,
        payload={
            "method": method,
            "method_index": method_idx,
            "arm": arm,
            "context": context.tolist(),
            "persona_style_bias": persona.style_bias,
        },
    )

    lesson = generate_lesson(method=method, skill=skill, bank=bank, use_ollama=False)
    agent.remember_lesson(method, render_lesson_markdown(lesson))
    used = {t.question_id for t in diagnostic.trials} | {p["id"] for p in lesson.practice}

    # Practice (does not train policy)
    for p in lesson.practice[:2]:
        q = bank.get(p["id"])
        resp = agent.answer(q, phase="practice")
        ok = verify_answer(q.answer_sympy if q.answer_sympy is not None else q.answer, resp).ok
        log_item_response(
            session_id,
            learner_id=learner_id,
            item_id=q.id,
            skill=skill,
            method=method,
            response=resp,
            correct=ok,
            outcome_type="practice",
            content_version=CONTENT_VERSION,
            model_id=model,
            respondent="llm_agent",
            extra={"arm": arm, "persona": persona.id},
        )

    post_items = _pick_form(bank, skill, "B", 3, used)
    imm_ok = 0
    for q in post_items:
        resp = agent.answer(q, phase="immediate_post")
        ok = verify_answer(q.answer_sympy if q.answer_sympy is not None else q.answer, resp).ok
        imm_ok += int(ok)
        used.add(q.id)
        log_item_response(
            session_id,
            learner_id=learner_id,
            item_id=q.id,
            skill=skill,
            method=method,
            response=resp,
            correct=ok,
            outcome_type="immediate_post",
            content_version=CONTENT_VERSION,
            model_id=model,
            respondent="llm_agent",
            extra={"arm": arm, "persona": persona.id, "form": q.form},
        )
    immediate_score = imm_ok / max(len(post_items), 1)

    # Simulated 36h gap (no wall-clock wait) — delayed Form C with faded memory
    delayed_items = _pick_form(bank, skill, "C", 3, used)
    del_ok = 0
    for q in delayed_items:
        resp = agent.answer(q, phase="delayed_24h")
        ok = verify_answer(q.answer_sympy if q.answer_sympy is not None else q.answer, resp).ok
        del_ok += int(ok)
        log_item_response(
            session_id,
            learner_id=learner_id,
            item_id=q.id,
            skill=skill,
            method=method,
            response=resp,
            correct=ok,
            outcome_type="delayed_24h",
            content_version=CONTENT_VERSION,
            model_id=model,
            respondent="llm_agent",
            extra={"arm": arm, "persona": persona.id, "form": q.form, "gap_hours_claimed": 36},
        )
    delayed_score = del_ok / max(len(delayed_items), 1)

    if arm == "adaptive_method":
        bandit.update(method_idx, context, delayed_score)

    elapsed = time.time() - t0
    append_event(
        session_id,
        "session_end",
        learner_id=learner_id,
        payload={
            "arm": arm,
            "method": method,
            "skill": skill,
            "immediate_score": immediate_score,
            "delayed_score": delayed_score,
            "lesson_ok": lesson.lesson_ok,
            "respondent": "llm_agent",
            "persona": persona.id,
            "elapsed_sec": round(elapsed, 1),
        },
    )
    print(
        f"  method={method} immediate={immediate_score:.0%} "
        f"delayed={delayed_score:.0%} ({elapsed:.0f}s)",
        flush=True,
    )
    return {
        "learner": learner_id,
        "session_id": session_id,
        "arm": arm,
        "persona": persona.id,
        "style_bias": persona.style_bias,
        "method": method,
        "skill": skill,
        "immediate_score": immediate_score,
        "delayed_score": delayed_score,
        "match_bias": method == persona.style_bias,
        "elapsed_sec": round(elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=16, help="Agent cohort size (12–20)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--n-diag", type=int, default=5)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "pilot_qwen"))
    parser.add_argument(
        "--arms",
        default="adaptive_method,fixed_worked_example",
        help="Comma list. Optional: matched_bias",
    )
    args = parser.parse_args()

    if not is_reachable():
        raise SystemExit("Ollama not reachable. Start with: ollama serve")

    n = max(12, min(20, args.n))
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bank = QuestionBank.load()
    cohort = make_cohort(n)

    rows = []
    t_all = time.time()
    for i, persona in enumerate(cohort):
        arm = arms[i % len(arms)]
        row = run_one(
            i,
            persona,
            arm,
            bank,
            model=args.model,
            seed=args.seed + i * 19,
            n_diag=args.n_diag,
        )
        rows.append(row)
        # Incremental save
        (out_dir / "qwen_agent_summary.json").write_text(
            json.dumps({"rows": rows, "partial": True}, indent=2),
            encoding="utf-8",
        )

    by_arm: dict = {}
    for arm in arms:
        scores = [r["delayed_score"] for r in rows if r["arm"] == arm]
        by_arm[arm] = {
            "n": len(scores),
            "mean_delayed": float(np.mean(scores)) if scores else None,
            "std_delayed": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0,
        }

    matched = [r["delayed_score"] for r in rows if r["match_bias"]]
    mismatched = [r["delayed_score"] for r in rows if not r["match_bias"]]

    summary = {
        "note": "Qwen llm_agent cohort — NOT human efficacy. Pipeline + persona stress test.",
        "model": args.model,
        "n": n,
        "seed": args.seed,
        "content_version": CONTENT_VERSION,
        "elapsed_sec": round(time.time() - t_all, 1),
        "by_arm": by_arm,
        "method_match_vs_mismatch": {
            "matched_n": len(matched),
            "matched_mean_delayed": float(np.mean(matched)) if matched else None,
            "mismatched_n": len(mismatched),
            "mismatched_mean_delayed": float(np.mean(mismatched)) if mismatched else None,
        },
        "rows": rows,
    }
    path = out_dir / "qwen_agent_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# Qwen agent pilot",
                "",
                "**respondent=`llm_agent`** — synthetic local-LLM learners, not recruited humans.",
                "",
                "Use this to:",
                "- prove the Session1 → faded-memory Session2 pipeline runs end-to-end",
                "- inspect whether matched teaching styles beat mismatches for personas",
                "",
                "Do **not** cite these numbers as child/learner efficacy to companies.",
                "",
                f"Summary: `{path.name}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("\n=== DONE ===", flush=True)
    print(json.dumps(by_arm, indent=2), flush=True)
    print(json.dumps(summary["method_match_vs_mismatch"], indent=2), flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
