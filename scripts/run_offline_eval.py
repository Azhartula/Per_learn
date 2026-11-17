#!/usr/bin/env python3
"""Offline evaluation: ASSISTments BKT holdout + non-circular policy sims.

Outputs under outputs/eval/. Simulation results are algorithm stress tests —
NOT learning-efficacy claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.bkt import (  # noqa: E402
    fit_skill,
    fraction_subset,
    load_assistments,
    predict_correct,
    update_mastery,
)
from pll.config import DATA_PATH, DEFAULT_SKILL, SIM_PROFILES  # noqa: E402
from pll.simulator import get_effect_profile, run_comparison  # noqa: E402


def _student_holdout_sequences(df, skill: str, test_frac: float, seed: int):
    part = df[df["skill_name"] == skill].copy()
    if "order_id" in part.columns:
        part = part.sort_values(["user_id", "order_id"])
    users = sorted(part["user_id"].unique().tolist())
    rng = np.random.default_rng(seed)
    rng.shuffle(users)
    n_test = max(1, int(len(users) * test_frac))
    test_users = set(users[:n_test])
    train_users = set(users[n_test:])
    return part, train_users, test_users


def evaluate_bkt_holdout(df, skill: str, seed: int = 42, test_frac: float = 0.2) -> dict:
    part, train_users, test_users = _student_holdout_sequences(df, skill, test_frac, seed)
    train_df = part[part["user_id"].isin(train_users)]
    params = fit_skill(train_df, skill=skill)

    y_true: list[int] = []
    p_bkt: list[float] = []
    p_emp: list[float] = []
    # Empirical skill rate from train
    emp = float((train_df["correct"].astype(float) > 0.5).mean())

    # Features for logistic: step index + rolling accuracy so far
    X_rows: list[list[float]] = []
    y_log: list[int] = []

    test = part[part["user_id"].isin(test_users)]
    for _, group in test.groupby("user_id", sort=False):
        y = (group["correct"].astype(float).to_numpy() > 0.5).astype(int)
        if len(y) < 2:
            continue
        mastery = params.p_l0
        correct_so_far = 0
        for t, yt in enumerate(y):
            p = predict_correct(mastery, params.p_g, params.p_s)
            y_true.append(int(yt))
            p_bkt.append(float(p))
            p_emp.append(emp)
            X_rows.append([t, correct_so_far / max(t, 1), emp])
            y_log.append(int(yt))
            mastery = update_mastery(mastery, bool(yt), params.p_t, params.p_g, params.p_s)
            correct_so_far += int(yt)

    y_arr = np.array(y_true)
    p_bkt_a = np.clip(np.array(p_bkt), 1e-6, 1 - 1e-6)
    p_emp_a = np.clip(np.array(p_emp), 1e-6, 1 - 1e-6)

    # Fit logistic on first half of test chronologically as a weak baseline
    # (honest: train logistic on train sequences instead)
    X_train: list[list[float]] = []
    y_train: list[int] = []
    for _, group in train_df.groupby("user_id", sort=False):
        y = (group["correct"].astype(float).to_numpy() > 0.5).astype(int)
        if len(y) < 2:
            continue
        correct_so_far = 0
        for t, yt in enumerate(y):
            X_train.append([t, correct_so_far / max(t, 1), emp])
            y_train.append(int(yt))
            correct_so_far += int(yt)
    clf = LogisticRegression(max_iter=200)
    clf.fit(np.array(X_train), np.array(y_train))
    p_log = np.clip(clf.predict_proba(np.array(X_rows))[:, 1], 1e-6, 1 - 1e-6)

    def _metrics(p):
        return {
            "log_loss": float(log_loss(y_arr, p)),
            "brier": float(brier_score_loss(y_arr, p)),
            "accuracy_at_0.5": float(np.mean((p >= 0.5) == y_arr)),
            "n": int(len(y_arr)),
        }

    # Calibration buckets for BKT
    bins = np.linspace(0, 1, 6)
    cal = []
    for i in range(len(bins) - 1):
        mask = (p_bkt_a >= bins[i]) & (p_bkt_a < bins[i + 1])
        if mask.sum() == 0:
            continue
        cal.append(
            {
                "bin": f"{bins[i]:.1f}-{bins[i+1]:.1f}",
                "n": int(mask.sum()),
                "mean_p": float(p_bkt_a[mask].mean()),
                "mean_y": float(y_arr[mask].mean()),
            }
        )

    return {
        "skill": skill,
        "note": "Student-level holdout on ASSISTments. Predictive quality ≠ learning efficacy.",
        "bkt_params_train": params.__dict__,
        "n_train_students": len(train_users),
        "n_test_students": len(test_users),
        "models": {
            "bkt": _metrics(p_bkt_a),
            "empirical_rate": _metrics(p_emp_a),
            "logistic_baseline": _metrics(p_log),
        },
        "bkt_calibration": cal,
    }


def _ci_mean(xs: list[float], n_boot: int = 400, seed: int = 0) -> dict:
    arr = np.asarray(xs, dtype=float)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means.append(float(sample.mean()))
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        "ci95": [float(lo), float(hi)],
    }


def evaluate_policies(params, profiles: list[str], n_students: int, seed: int) -> dict:
    out = {"note": "Simulation stress test only — not efficacy evidence.", "profiles": {}}
    for profile in profiles:
        effect = get_effect_profile(profile)
        results = run_comparison(params, n_students=n_students, seed=seed, profile=profile)
        block = {
            "effect": {
                "match_boost": effect.match_boost,
                "near_match": effect.near_match,
                "mismatch_penalty": effect.mismatch_penalty,
                "bandit_warm_start": effect.bandit_warm_start,
                "description": SIM_PROFILES[profile]["description"],
            },
            "policies": {},
        }
        for name, r in results.items():
            block["policies"][name] = {
                "sessions_to_mastery": _ci_mean(r.sessions_to_mastery, seed=seed + 7),
                "mean_reward": _ci_mean(r.mean_reward, seed=seed + 11),
                "choice_match_rate": _ci_mean(r.choice_match_rate, seed=seed + 13),
                "end_preference_recovery": float(np.mean(r.recovered_best)),
            }
        out["profiles"][profile] = block
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    parser.add_argument("--students", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data", default=str(ROOT / DATA_PATH))
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "eval"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading ASSISTments…")
    df = load_assistments(args.data)
    frac = fraction_subset(df)

    print(f"BKT holdout eval on {args.skill}…")
    bkt_report = evaluate_bkt_holdout(frac, args.skill, seed=args.seed)
    bkt_path = out_dir / "bkt_holdout.json"
    bkt_path.write_text(json.dumps(bkt_report, indent=2), encoding="utf-8")
    print(json.dumps(bkt_report["models"], indent=2))
    print(f"Wrote {bkt_path}")

    print("Fitting BKT on full fraction skill for policy sims…")
    params = fit_skill(frac, skill=args.skill)
    print("Running policy ablations (demo / neutral / adversarial)…")
    policy_report = evaluate_policies(
        params,
        profiles=["demo", "neutral", "adversarial"],
        n_students=args.students,
        seed=args.seed,
    )
    policy_report["skill"] = args.skill
    policy_report["n_students"] = args.students
    policy_report["seed"] = args.seed
    pol_path = out_dir / "policy_ablations.json"
    pol_path.write_text(json.dumps(policy_report, indent=2), encoding="utf-8")
    print(f"Wrote {pol_path}")

    readme = out_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Offline evaluation",
                "",
                "These artifacts support **technical** claims only:",
                "",
                "1. `bkt_holdout.json` — predictive quality of BKT vs baselines on ASSISTments student holdout.",
                "2. `policy_ablations.json` — bandit vs fixed/random under demo / neutral / adversarial effect sizes.",
                "",
                "**Not efficacy.** Simulation rewards are synthetic. Human delayed outcomes live in the pilot pack.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {readme}")


if __name__ == "__main__":
    main()
