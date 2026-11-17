"""Simulated Year-5-style fraction learners with expertise-reversal effects."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pll.bandit import DiscountedContextualTS, make_context, mastery_bin
from pll.bkt import BKTParams, update_mastery
from pll.config import (
    DELAYED_CHECK_ITEMS,
    MASTERY_THRESHOLD,
    MATCH_BOOST,
    MAX_SESSIONS,
    METHODS,
    MISMATCH_PENALTY,
    NEAR_MATCH,
    N_STUDENTS,
    PRACTICE_ITEMS,
    STREAK_REQUIRED,
)

# Canonical best method by expertise bin (expertise reversal).
# 0=worked_example, 1=problem_first, 2=visual, 3=story_analogy
BIN_BEST = {
    0: 0,  # novice → worked example
    1: 2,  # intermediate → visual
    2: 1,  # advanced → problem first
}


@dataclass
class Student:
    student_id: int
    prior_mastery: float
    mastery: float
    latent_known: bool
    # Personal preference among near-optimal methods in a bin (individual noise).
    preference_noise: dict[int, int]


@dataclass
class SimResult:
    policy: str
    sessions_to_mastery: list[float]
    recovered_best: list[bool]
    mean_reward: list[float]
    final_mastery: list[float]
    choice_match_rate: list[float]


def oracle_method(mastery: float, preference_noise: dict[int, int]) -> int:
    b = mastery_bin(mastery)
    return preference_noise.get(b, BIN_BEST[b])


def make_students(n: int, params: BKTParams, rng: np.random.Generator) -> list[Student]:
    students: list[Student] = []
    # Near-optimal alternatives per bin (individual variation).
    alts = {
        0: (0, 2),  # worked or visual for novices
        1: (2, 3),  # visual or story for intermediate
        2: (1,),    # problem-first for advanced
    }
    for i in range(n):
        # Mix of novices and intermediates so fixed scaffolding eventually hurts.
        prior = float(np.clip(rng.beta(2.2, 3.2), 0.08, 0.62))
        pref = {b: int(rng.choice(opts)) for b, opts in alts.items()}
        students.append(
            Student(
                student_id=i,
                prior_mastery=prior,
                mastery=prior,
                latent_known=bool(rng.random() < prior),
                preference_noise=pref,
            )
        )
    return students


def _effective_learn_rate(base_pt: float, method: int, best: int) -> float:
    base = float(np.clip(base_pt * 0.50, 0.02, 0.22))
    if method == best:
        return float(np.clip(base * MATCH_BOOST, 0.02, 0.80))
    family = {
        0: {0, 2},
        1: {1},
        2: {0, 2, 3},
        3: {2, 3},
    }
    # Expertise reversal: scaffolding methods actively slow advanced learners.
    if best == 1 and method in (0, 2, 3):
        return float(np.clip(base * 0.18, 0.005, 0.80))
    # Problem-first frustrates novices.
    if best in (0, 2) and method == 1:
        return float(np.clip(base * 0.22, 0.005, 0.80))
    if method in family.get(best, set()):
        return float(np.clip(base * NEAR_MATCH, 0.02, 0.80))
    return float(np.clip(base * MISMATCH_PENALTY, 0.01, 0.80))


def _answer(student: Student, p_g: float, p_s: float, rng: np.random.Generator) -> bool:
    if student.latent_known:
        return bool(rng.random() > p_s)
    return bool(rng.random() < p_g)


def _learn_step(student: Student, p_t_eff: float, rng: np.random.Generator) -> None:
    if not student.latent_known and rng.random() < p_t_eff:
        student.latent_known = True


def run_one_student(
    student: Student,
    params: BKTParams,
    policy_name: str,
    bandit: DiscountedContextualTS | None,
    fixed_method: int,
    rng: np.random.Generator,
    max_sessions: int = MAX_SESSIONS,
) -> tuple[float, bool, float, float]:
    rewards: list[float] = []
    matches = 0
    decisions = 0
    streak = 0
    last_context = make_context(student.mastery)

    for session in range(1, max_sessions + 1):
        context = make_context(student.mastery)
        last_context = context
        best_now = oracle_method(student.mastery, student.preference_noise)

        if policy_name == "fixed":
            method = fixed_method
        elif policy_name == "random":
            method = int(rng.integers(0, len(METHODS)))
        elif policy_name == "bandit":
            assert bandit is not None
            method = bandit.select(context)
        else:
            raise ValueError(policy_name)

        decisions += 1
        matches += int(method == best_now)

        p_t_eff = _effective_learn_rate(params.p_t, method, best_now)

        for _ in range(PRACTICE_ITEMS):
            _learn_step(student, p_t_eff, rng)
            correct = _answer(student, params.p_g, params.p_s, rng)
            student.mastery = update_mastery(
                student.mastery, correct, p_t_eff, params.p_g, params.p_s
            )

        check_correct = 0
        for _ in range(DELAYED_CHECK_ITEMS):
            ok = _answer(student, params.p_g, params.p_s, rng)
            check_correct += int(ok)
            student.mastery = update_mastery(
                student.mastery, ok, params.p_t * 0.15, params.p_g, params.p_s
            )
        reward = check_correct / DELAYED_CHECK_ITEMS
        rewards.append(reward)

        if bandit is not None and policy_name == "bandit":
            bandit.update(method, context, reward)

        strong_check = reward >= 0.75
        if student.mastery >= MASTERY_THRESHOLD and strong_check:
            streak += 1
        else:
            streak = 0

        if streak >= STREAK_REQUIRED:
            recovered = _policy_prefers_oracle(
                policy_name, bandit, last_context, student, fixed_method
            )
            match_rate = matches / max(decisions, 1)
            return float(session), recovered, float(np.mean(rewards)), match_rate

    recovered = _policy_prefers_oracle(
        policy_name, bandit, last_context, student, fixed_method
    )
    match_rate = matches / max(decisions, 1)
    return (
        float(max_sessions + 1),
        recovered,
        float(np.mean(rewards) if rewards else 0.0),
        match_rate,
    )


def _policy_prefers_oracle(
    policy_name: str,
    bandit: DiscountedContextualTS | None,
    context: np.ndarray,
    student: Student,
    fixed_method: int,
) -> bool:
    best = oracle_method(float(context[-1]), student.preference_noise)
    if policy_name == "bandit" and bandit is not None:
        return int(np.argmax(bandit.mean_rewards(context))) == best
    if policy_name == "fixed":
        return fixed_method == best
    # Random has no preference; treat as miss for this metric.
    return False


def run_policy(
    policy_name: str,
    base_students: list[Student],
    params: BKTParams,
    rng: np.random.Generator,
    fixed_method: int = 0,
) -> SimResult:
    sessions: list[float] = []
    recovered: list[bool] = []
    means: list[float] = []
    finals: list[float] = []
    match_rates: list[float] = []

    bandit = (
        DiscountedContextualTS(rng=np.random.default_rng(int(rng.integers(1, 1_000_000))))
        if policy_name == "bandit"
        else None
    )

    for proto in base_students:
        student = Student(
            student_id=proto.student_id,
            prior_mastery=proto.prior_mastery,
            mastery=proto.prior_mastery,
            latent_known=bool(rng.random() < proto.prior_mastery),
            preference_noise=dict(proto.preference_noise),
        )
        s, rec, mean_r, match_rate = run_one_student(
            student, params, policy_name, bandit, fixed_method, rng
        )
        sessions.append(s)
        recovered.append(rec)
        means.append(mean_r)
        finals.append(student.mastery)
        match_rates.append(match_rate)

    return SimResult(
        policy=policy_name,
        sessions_to_mastery=sessions,
        recovered_best=recovered,
        mean_reward=means,
        final_mastery=finals,
        choice_match_rate=match_rates,
    )


def run_comparison(
    params: BKTParams,
    n_students: int = N_STUDENTS,
    seed: int = 42,
) -> dict[str, SimResult]:
    rng = np.random.default_rng(seed)
    base = make_students(n_students, params, rng)
    results = {}
    for name in ("fixed", "random", "bandit"):
        policy_rng = np.random.default_rng(seed + (hash(name) % 10_000))
        results[name] = run_policy(name, base, params, policy_rng)
    return results
