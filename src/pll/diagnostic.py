"""IRT-lite adaptive diagnostic for Year 5 fractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from pll.questions import Question, QuestionBank
from pll.sympy_check import verify_answer


@dataclass
class Trial:
    question_id: str
    skill: str
    difficulty: int
    correct: bool
    response: str
    misconceptions: tuple[str, ...]


@dataclass
class DiagnosticResult:
    ability: float  # roughly 0–1 mastery estimate
    n_correct: int
    n_items: int
    skill_scores: dict[str, float]
    active_misconceptions: list[str]
    weakest_skill: str
    trials: list[Trial] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.n_correct / max(self.n_items, 1)


def _difficulty_target(ability: float) -> int:
    if ability < 0.35:
        return 1
    if ability < 0.65:
        return 2
    return 3


def _update_ability(ability: float, correct: bool, difficulty: int) -> float:
    # Simple Elo-style / IRT-lite step toward item difficulty.
    step = 0.08 if correct else -0.06
    # Harder items move ability more when answered correctly.
    if correct:
        step *= 0.7 + 0.15 * difficulty
    else:
        # Missing a hard item should not crash the estimate.
        step *= 1.1 - 0.15 * difficulty
    return float(np.clip(ability + step, 0.08, 0.95))


def _pick_next(
    bank: QuestionBank,
    used: set[str],
    ability: float,
    skill_counts: dict[str, int],
    rng: np.random.Generator,
) -> Question | None:
    target_diff = _difficulty_target(ability)
    # Prefer under-sampled skills so we get a broad picture.
    skills = list(bank.skills)
    skills.sort(key=lambda s: (skill_counts.get(s, 0), rng.random()))

    candidates: list[Question] = []
    for skill in skills:
        pool = [q for q in bank.by_skill(skill) if q.id not in used]
        if not pool:
            continue
        near = [q for q in pool if abs(q.difficulty - target_diff) <= 1]
        pool = near or pool
        # Prefer exact difficulty match.
        exact = [q for q in pool if q.difficulty == target_diff]
        pool = exact or pool
        candidates.extend(pool[:3])
        if candidates:
            break

    if not candidates:
        remaining = [q for q in bank.items if q.id not in used]
        if not remaining:
            return None
        candidates = remaining

    return candidates[int(rng.integers(0, len(candidates)))]


def run_diagnostic(
    bank: QuestionBank,
    answer_fn: Callable[[Question], str],
    n_items: int = 8,
    seed: int = 42,
) -> DiagnosticResult:
    """
    Adaptive quiz. `answer_fn` returns the student's response string
    (interactive input or a simulated student).
    """
    rng = np.random.default_rng(seed)
    ability = 0.45
    used: set[str] = set()
    trials: list[Trial] = []
    skill_correct: dict[str, list[bool]] = {s: [] for s in bank.skills}
    skill_counts: dict[str, int] = {s: 0 for s in bank.skills}
    misconception_hits: dict[str, int] = {}

    for _ in range(n_items):
        q = _pick_next(bank, used, ability, skill_counts, rng)
        if q is None:
            break
        used.add(q.id)
        response = answer_fn(q)
        expected = q.answer_sympy if q.answer_sympy is not None else q.answer
        correct = verify_answer(expected, response).ok
        ability = _update_ability(ability, correct, q.difficulty)
        skill_correct[q.skill].append(correct)
        skill_counts[q.skill] = skill_counts.get(q.skill, 0) + 1
        if not correct:
            for m in q.misconceptions:
                misconception_hits[m] = misconception_hits.get(m, 0) + 1
        trials.append(
            Trial(
                question_id=q.id,
                skill=q.skill,
                difficulty=q.difficulty,
                correct=correct,
                response=str(response),
                misconceptions=q.misconceptions,
            )
        )

    skill_scores = {
        s: (sum(v) / len(v) if v else 0.5) for s, v in skill_correct.items() if v
    }
    if not skill_scores:
        skill_scores = {bank.skills[0]: 0.5}
    # Blend running ability with observed accuracy so the parent view stays intuitive.
    accuracy = sum(1 for t in trials if t.correct) / max(len(trials), 1)
    ability = float(np.clip(0.6 * ability + 0.4 * accuracy, 0.08, 0.95))
    weakest = min(skill_scores, key=skill_scores.get)
    active = sorted(misconception_hits, key=misconception_hits.get, reverse=True)

    return DiagnosticResult(
        ability=ability,
        n_correct=sum(1 for t in trials if t.correct),
        n_items=len(trials),
        skill_scores=skill_scores,
        active_misconceptions=active,
        weakest_skill=weakest,
        trials=trials,
    )


def make_simulated_student(
    true_ability: float = 0.45,
    seed: int = 7,
) -> Callable[[Question], str]:
    """Return an answer function that is often wrong on harder items."""
    rng = np.random.default_rng(seed)

    def answer_fn(q: Question) -> str:
        # Probability of knowing the item (novice-ish demo student).
        p = float(np.clip(true_ability + 0.18 * (2 - q.difficulty), 0.15, 0.92))
        if rng.random() < p:
            if isinstance(q.answer, list):
                return ", ".join(str(a) for a in q.answer)
            return str(q.answer)
        # Wrong: pick a distractor or a plausible bad fraction.
        if q.choices:
            expected = q.answer_sympy if q.answer_sympy is not None else q.answer
            wrong = [c for c in q.choices if not verify_answer(expected, c).ok]
            if wrong:
                return str(wrong[int(rng.integers(0, len(wrong)))])
        return "1/1"

    return answer_fn
