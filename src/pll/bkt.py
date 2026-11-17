"""Bayesian Knowledge Tracing fit and online updates for fraction skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pll.config import DEFAULT_SKILL, FRACTION_SKILLS


@dataclass(frozen=True)
class BKTParams:
    """Standard BKT parameters for one skill."""

    skill: str
    p_l0: float  # prior mastery
    p_t: float   # learn (transit)
    p_g: float   # guess
    p_s: float   # slip
    n_rows: int
    n_students: int


def load_assistments(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run scripts/download_data.py first."
        )
    return pd.read_csv(path, encoding="latin-1", low_memory=False)


def fraction_subset(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["skill_name"].isin(FRACTION_SKILLS)].copy()


def fraction_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for skill in FRACTION_SKILLS:
        part = df[df["skill_name"] == skill]
        if part.empty:
            continue
        rows.append(
            {
                "skill": skill,
                "answers": len(part),
                "students": part["user_id"].nunique(),
                "problems": part["problem_id"].nunique(),
                "mean_correct": float(part["correct"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("answers", ascending=False)


def _student_sequences(df: pd.DataFrame, skill: str) -> list[np.ndarray]:
    part = df[df["skill_name"] == skill].copy()
    if "order_id" in part.columns:
        part = part.sort_values(["user_id", "order_id"])
    else:
        part = part.sort_values(["user_id"])
    seqs: list[np.ndarray] = []
    for _, group in part.groupby("user_id", sort=False):
        # ASSISTments "correct" can be float; treat >0.5 as correct.
        y = (group["correct"].astype(float).to_numpy() > 0.5).astype(int)
        if len(y) >= 2:
            seqs.append(y)
    return seqs


def fit_skill(
    df: pd.DataFrame,
    skill: str = DEFAULT_SKILL,
    max_iter: int = 40,
    tol: float = 1e-5,
) -> BKTParams:
    """Fit classic 4-parameter BKT with forward-backward EM."""
    seqs = _student_sequences(df, skill)
    if not seqs:
        raise ValueError(f"No usable sequences for skill: {skill}")

    # Initialize near typical ASSISTments values.
    p_l0, p_t, p_g, p_s = 0.25, 0.12, 0.20, 0.10

    for _ in range(max_iter):
        sum_l0 = 0.0
        sum_t_num = 0.0
        sum_t_den = 0.0
        sum_g_num = 0.0
        sum_g_den = 0.0
        sum_s_num = 0.0
        sum_s_den = 0.0
        n_students = 0

        for y in seqs:
            gamma, xi = _forward_backward(y, p_l0, p_t, p_g, p_s)
            n_students += 1
            sum_l0 += float(gamma[0, 1])  # P(known) at first opportunity
            # Learn when transitioning 0 -> 1.
            sum_t_num += float(xi[:, 0, 1].sum())
            sum_t_den += float(gamma[:-1, 0].sum())
            # Guess / slip from emission soft counts.
            unknown = gamma[:, 0]
            known = gamma[:, 1]
            sum_g_num += float((unknown * y).sum())
            sum_g_den += float(unknown.sum())
            sum_s_num += float((known * (1 - y)).sum())
            sum_s_den += float(known.sum())

        new_l0 = _clip(sum_l0 / max(n_students, 1))
        new_t = _clip(sum_t_num / max(sum_t_den, 1e-12))
        new_g = _clip(sum_g_num / max(sum_g_den, 1e-12), hi=0.45)
        new_s = _clip(sum_s_num / max(sum_s_den, 1e-12), hi=0.45)

        delta = max(
            abs(new_l0 - p_l0),
            abs(new_t - p_t),
            abs(new_g - p_g),
            abs(new_s - p_s),
        )
        p_l0, p_t, p_g, p_s = new_l0, new_t, new_g, new_s
        if delta < tol:
            break

    part = df[df["skill_name"] == skill]
    return BKTParams(
        skill=skill,
        p_l0=p_l0,
        p_t=p_t,
        p_g=p_g,
        p_s=p_s,
        n_rows=len(part),
        n_students=int(part["user_id"].nunique()),
    )


def _clip(x: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return float(min(hi, max(lo, x)))


def _forward_backward(
    y: np.ndarray,
    p_l0: float,
    p_t: float,
    p_g: float,
    p_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return gamma[t, state] and xi[t, from, to] with state 0=unknown, 1=known."""
    t_steps = len(y)
    # Transition: once known, stay known (classic BKT, no forget).
    a = np.array(
        [
            [1.0 - p_t, p_t],
            [0.0, 1.0],
        ],
        dtype=float,
    )

    def emit(state: int, obs: int) -> float:
        if state == 1:  # known
            return (1.0 - p_s) if obs == 1 else p_s
        return p_g if obs == 1 else (1.0 - p_g)

    alpha = np.zeros((t_steps, 2))
    alpha[0, 0] = (1.0 - p_l0) * emit(0, int(y[0]))
    alpha[0, 1] = p_l0 * emit(1, int(y[0]))
    alpha[0] /= max(alpha[0].sum(), 1e-300)

    scales = np.ones(t_steps)
    scales[0] = 1.0

    for t in range(1, t_steps):
        for j in range(2):
            alpha[t, j] = emit(j, int(y[t])) * (
                alpha[t - 1, 0] * a[0, j] + alpha[t - 1, 1] * a[1, j]
            )
        s = max(alpha[t].sum(), 1e-300)
        alpha[t] /= s
        scales[t] = s

    beta = np.zeros((t_steps, 2))
    beta[-1] = 1.0
    for t in range(t_steps - 2, -1, -1):
        for i in range(2):
            beta[t, i] = 0.0
            for j in range(2):
                beta[t, i] += a[i, j] * emit(j, int(y[t + 1])) * beta[t + 1, j]
        beta[t] /= max(scales[t + 1], 1e-300)

    gamma = alpha * beta
    gamma /= np.maximum(gamma.sum(axis=1, keepdims=True), 1e-300)

    xi = np.zeros((max(t_steps - 1, 0), 2, 2))
    for t in range(t_steps - 1):
        for i in range(2):
            for j in range(2):
                xi[t, i, j] = (
                    alpha[t, i]
                    * a[i, j]
                    * emit(j, int(y[t + 1]))
                    * beta[t + 1, j]
                )
        xi[t] /= max(xi[t].sum(), 1e-300)

    return gamma, xi


def update_mastery(
    p_known: float,
    correct: bool,
    p_t: float,
    p_g: float,
    p_s: float,
) -> float:
    """One-step Bayesian update of mastery after an observed response."""
    if correct:
        p_correct_given_known = 1.0 - p_s
        p_correct_given_unknown = p_g
        p_obs = p_known * p_correct_given_known + (1.0 - p_known) * p_correct_given_unknown
        p_known_given_obs = (p_known * p_correct_given_known) / max(p_obs, 1e-12)
    else:
        p_wrong_given_known = p_s
        p_wrong_given_unknown = 1.0 - p_g
        p_obs = p_known * p_wrong_given_known + (1.0 - p_known) * p_wrong_given_unknown
        p_known_given_obs = (p_known * p_wrong_given_known) / max(p_obs, 1e-12)

    return p_known_given_obs + (1.0 - p_known_given_obs) * p_t


def predict_correct(p_known: float, p_g: float, p_s: float) -> float:
    return p_known * (1.0 - p_s) + (1.0 - p_known) * p_g
