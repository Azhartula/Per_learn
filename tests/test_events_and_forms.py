"""Event logging and parallel-form bank tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pll.events import append_event, load_all_events, log_item_response, new_session_id, read_events
from pll.questions import QuestionBank


def test_event_roundtrip(tmp_path):
    sid = new_session_id()
    path = append_event(
        sid,
        "session_start",
        learner_id="t1",
        payload={"mode": "test"},
        log_dir=tmp_path,
    )
    log_item_response(
        sid,
        learner_id="t1",
        item_id="eq_01",
        skill="equivalent_fractions",
        method="worked_example",
        response="2/4",
        correct=True,
        outcome_type="diagnostic",
        log_dir=tmp_path,
    )
    rows = read_events(path)
    assert len(rows) == 2
    assert rows[0]["schema_version"] == "1.0"
    assert rows[1]["outcome_type"] == "diagnostic"


def test_bank_has_parallel_forms():
    bank = QuestionBank.load()
    assert len(bank.items) >= 80
    assert len(bank.by_form("A")) >= 30
    assert len(bank.by_form("B")) >= 10
    assert len(bank.by_form("C")) >= 10


def test_distractor_misconception_map():
    bank = QuestionBank.load()
    q = next(x for x in bank.items if x.distractor_misconceptions)
    choice = next(iter(q.distractor_misconceptions))
    mapped = bank.misconception_from_response(q, choice)
    assert mapped == [q.distractor_misconceptions[choice]]
