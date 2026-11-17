"""Answer verification tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pll.sympy_check import values_equal, verify_answer


def test_simple_fractions_equal():
    assert values_equal("1/2", "2/4")
    assert verify_answer("3/7", "3/7").ok


def test_mixed_number():
    assert values_equal("1 1/4", "5/4")


def test_ordering_list():
    assert verify_answer(["1/5", "1/3", "1/2"], "1/5, 1/3, 1/2").ok


def test_mismatch():
    assert not verify_answer("1/2", "1/3").ok


def test_true_false():
    assert verify_answer("false", "false").ok
    assert not verify_answer("false", "true").ok
