"""Core BKT / bandit unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pll.bandit import DiscountedContextualTS, make_context, mastery_bin
from pll.bkt import update_mastery


def test_mastery_bins():
    assert mastery_bin(0.1) == 0
    assert mastery_bin(0.4) == 1
    assert mastery_bin(0.8) == 2


def test_bandit_update_moves_mean():
    rng = np.random.default_rng(0)
    bandit = DiscountedContextualTS(rng=rng, warm_start=False)
    ctx = make_context(0.2)
    before = float(bandit.mean_rewards(ctx)[0])
    for _ in range(20):
        bandit.update(0, ctx, 1.0)
    after = float(bandit.mean_rewards(ctx)[0])
    assert after > before


def test_bandit_select_in_range():
    bandit = DiscountedContextualTS(rng=np.random.default_rng(1), warm_start=False)
    arm = bandit.select(make_context(0.5))
    assert 0 <= arm < bandit.n_arms


def test_update_mastery_increases_on_correct():
    m0 = 0.3
    m1 = update_mastery(m0, True, p_t=0.2, p_g=0.2, p_s=0.1)
    assert m1 >= m0
