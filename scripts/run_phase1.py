#!/usr/bin/env python3
"""Phase 1: fit BKT on fractions, simulate policies, save the pitch chart."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bkt import fit_skill, fraction_subset, fraction_summary, load_assistments
from pll.config import DATA_PATH, DEFAULT_SKILL, N_STUDENTS, OUTPUT_DIR, RNG_SEED
from pll.plotting import plot_time_to_mastery, summarize
from pll.simulator import run_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    parser.add_argument("--students", type=int, default=N_STUDENTS)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    parser.add_argument("--data", default=str(ROOT / DATA_PATH))
    parser.add_argument("--out-dir", default=str(ROOT / OUTPUT_DIR))
    parser.add_argument(
        "--profile",
        default="demo",
        choices=("demo", "neutral", "adversarial"),
        help="Sim effect profile. demo=pitch-scaled; neutral/adversarial for honest stress tests.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading ASSISTments…")
    df = load_assistments(args.data)
    frac = fraction_subset(df)
    summary = fraction_summary(frac)
    print("\nFraction skill coverage:")
    print(summary.to_string(index=False))
    summary.to_csv(out_dir / "fraction_skill_summary.csv", index=False)

    print(f"\nFitting BKT on: {args.skill}")
    params = fit_skill(frac, skill=args.skill)
    print(
        f"  n_rows={params.n_rows:,}  students={params.n_students:,}\n"
        f"  P(L0)={params.p_l0:.3f}  P(T)={params.p_t:.3f}  "
        f"P(G)={params.p_g:.3f}  P(S)={params.p_s:.3f}"
    )

    print(f"\nSimulating {args.students} students (seed={args.seed}, profile={args.profile})…")
    results = run_comparison(
        params, n_students=args.students, seed=args.seed, profile=args.profile
    )
    print(summarize(results))

    chart = plot_time_to_mastery(
        results,
        out_dir / "phase1_time_to_mastery.png",
        skill=args.skill,
    )
    print(f"\nChart saved: {chart}")

    payload = {
        "skill": args.skill,
        "bkt": params.__dict__,
        "n_students": args.students,
        "seed": args.seed,
        "profile": args.profile,
        "note": "demo profile is pitch-scaled; use outputs/eval for scientific ablations",
        "policies": {
            name: {
                "mean_sessions": float(sum(r.sessions_to_mastery) / len(r.sessions_to_mastery)),
                "median_sessions": float(sorted(r.sessions_to_mastery)[len(r.sessions_to_mastery) // 2]),
                "choice_match_rate": float(sum(r.choice_match_rate) / len(r.choice_match_rate)),
                "end_preference_recovery": float(sum(r.recovered_best) / len(r.recovered_best)),
                "mean_reward": float(sum(r.mean_reward) / len(r.mean_reward)),
            }
            for name, r in results.items()
        },
    }
    metrics_path = out_dir / "phase1_metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2))
    print(f"Metrics saved: {metrics_path}")


if __name__ == "__main__":
    main()
