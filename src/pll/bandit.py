"""Discounted contextual Thompson Sampling for teaching-method selection."""

from __future__ import annotations

import numpy as np

from pll.config import BANDIT_GAMMA, METHODS


def mastery_bin(mastery: float) -> int:
    """0=novice, 1=intermediate, 2=advanced — mirrors expertise-reversal bins."""
    if mastery < 0.35:
        return 0
    if mastery < 0.60:
        return 1
    return 2


def make_context(mastery: float) -> np.ndarray:
    """One-hot expertise bin plus raw mastery (for logging / linear variants)."""
    b = mastery_bin(mastery)
    one_hot = np.zeros(3, dtype=float)
    one_hot[b] = 1.0
    return np.concatenate([one_hot, [float(np.clip(mastery, 0.0, 1.0))]])


class DiscountedContextualTS:
    """Beta-Bernoulli Thompson Sampling per (mastery bin × method).

    This is the right inductive bias for expertise reversal: the best method
    can differ for novices vs advanced students, and evidence discounts so the
    preferred method can change as a child grows.
    """

    def __init__(
        self,
        n_arms: int = len(METHODS),
        n_bins: int = 3,
        prior_a: float = 1.0,
        prior_b: float = 1.0,
        gamma: float = BANDIT_GAMMA,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.n_arms = n_arms
        self.n_bins = n_bins
        self.prior_a = prior_a
        self.prior_b = prior_b
        self.gamma = gamma
        self.rng = rng or np.random.default_rng()
        # alpha[bin, arm], beta[bin, arm]
        self.alpha = np.full((n_bins, n_arms), prior_a, dtype=float)
        self.beta = np.full((n_bins, n_arms), prior_b, dtype=float)
        self.counts = np.zeros((n_bins, n_arms), dtype=int)
        # Weak expertise-reversal warm start (still learned from delayed rewards).
        # bins: 0=novice, 1=intermediate, 2=advanced
        # arms: 0=worked, 1=problem_first, 2=visual, 3=story
        warm = {
            0: {0: 2.5, 2: 1.5, 1: -0.3},
            1: {2: 2.0, 3: 1.5, 1: -0.2},
            2: {1: 3.0, 0: -0.4, 2: -0.3},
        }
        for b, arms in warm.items():
            for a, bump in arms.items():
                self.alpha[b, a] = max(0.5, self.alpha[b, a] + bump)

    def select(self, context: np.ndarray) -> int:
        b = int(np.argmax(context[: self.n_bins]))
        samples = self.rng.beta(self.alpha[b], self.beta[b])
        return int(np.argmax(samples))

    def update(self, arm: int, context: np.ndarray, reward: float) -> None:
        b = int(np.argmax(context[: self.n_bins]))
        # Discount older evidence in this bin/arm.
        self.alpha[b, arm] = self.prior_a + self.gamma * (self.alpha[b, arm] - self.prior_a)
        self.beta[b, arm] = self.prior_b + self.gamma * (self.beta[b, arm] - self.prior_b)
        # Fractional Bernoulli update from delayed-check accuracy in [0, 1].
        r = float(np.clip(reward, 0.0, 1.0))
        self.alpha[b, arm] += r
        self.beta[b, arm] += 1.0 - r
        self.counts[b, arm] += 1

    def mean_rewards(self, context: np.ndarray) -> np.ndarray:
        b = int(np.argmax(context[: self.n_bins]))
        return self.alpha[b] / (self.alpha[b] + self.beta[b])
