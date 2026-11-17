#!/usr/bin/env python3
"""
Real on-laptop demo: bandit picks a method, Ollama (GPU) writes the lesson,
SymPy verifies every answer before it is shown.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bandit import DiscountedContextualTS, make_context
from pll.config import METHODS
from pll.lessons import generate_lesson, render_lesson_markdown, save_lesson
from pll.ollama_client import DEFAULT_MODEL, is_reachable, list_models
from pll.parent_summary import METHOD_PLAIN
from pll.prompts import SKILL_LABELS
from pll.questions import QuestionBank


def _gpu_snapshot() -> str:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,utilization.gpu",
                "--format=csv,noheader",
            ],
            text=True,
            timeout=5,
        ).strip()
        return out
    except Exception as exc:
        return f"nvidia-smi unavailable ({exc})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", default="ordering_fractions")
    parser.add_argument("--mastery", type=float, default=0.28, help="Simulated current mastery 0-1")
    parser.add_argument("--method", choices=METHODS, default=None, help="Force method (else bandit)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "live_gpu"))
    args = parser.parse_args()

    print("=" * 64)
    print("PerLearn — LIVE local GPU lesson demo")
    print("=" * 64)
    print(f"GPU: {_gpu_snapshot()}")

    if not is_reachable():
        raise SystemExit("Ollama not running. Start with: ollama serve")
    models = list_models()
    print(f"Ollama models: {models or '(none)'}")
    if not any(args.model in m or m.startswith(args.model.split(':')[0]) for m in models):
        raise SystemExit(f"Missing model {args.model}. Run: ollama pull {args.model}")

    bank = QuestionBank.load()
    context = make_context(args.mastery)
    bandit = DiscountedContextualTS()
    if args.method:
        method = args.method
        method_idx = METHODS.index(method)
    else:
        method_idx = int(bandit.mean_rewards(context).argmax())
        # mild explore
        method_idx = bandit.select(context)
        method = METHODS[method_idx]

    print(f"\nChild mastery context: {args.mastery:.0%} → bandit chose: {METHOD_PLAIN[method]}")
    print(f"Skill: {SKILL_LABELS.get(args.skill, args.skill)}")
    print(f"Generating lesson with {args.model} on local Ollama…")

    t0 = time.time()
    gpu_before = _gpu_snapshot()
    lesson = generate_lesson(
        method=method,
        skill=args.skill,
        use_ollama=True,
        ollama_model=args.model,
        bank=bank,
    )
    elapsed = time.time() - t0
    gpu_after = _gpu_snapshot()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = save_lesson(lesson, out_dir)
    md_path = out_dir / f"{lesson.skill}__{lesson.method}__live.md"
    md_path.write_text(render_lesson_markdown(lesson), encoding="utf-8")

    meta = {
        "elapsed_sec": round(elapsed, 2),
        "model": args.model,
        "method": method,
        "mastery": args.mastery,
        "skill": args.skill,
        "source": lesson.source,
        "all_verified": lesson.all_verified,
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "title": lesson.title,
    }
    (out_dir / "live_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nDone in {elapsed:.1f}s")
    print(f"Source: {lesson.source}  |  SymPy verified: {lesson.all_verified}")
    print(f"Title: {lesson.title}")
    print(f"Targets misconception: {lesson.misconception_label}")
    print(f"GPU before: {gpu_before}")
    print(f"GPU after:  {gpu_after}")
    print("\n--- Lesson preview ---")
    print(render_lesson_markdown(lesson)[:1800])
    print("\n...")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")

    if lesson.source != "ollama":
        raise SystemExit("Lesson did not come from Ollama — check live_meta / fallback reason.")
    if not lesson.all_verified:
        print("WARNING: SymPy verification failed on at least one answer (bank answers still locked).")


if __name__ == "__main__":
    main()
