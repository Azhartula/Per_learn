#!/usr/bin/env python3
"""Analyze pilot / dry-run event logs into a company-facing pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.events import load_all_events  # noqa: E402


def _ci(xs: list[float], seed: int = 0) -> list[float]:
    if not xs:
        return [None, None]
    arr = np.asarray(xs, float)
    rng = np.random.default_rng(seed)
    boots = [float(rng.choice(arr, size=len(arr), replace=True).mean()) for _ in range(500)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return [float(lo), float(hi)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default=str(ROOT / "outputs" / "events"))
    parser.add_argument("--out-dir", default=str(ROOT / "outputs" / "pilot"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = load_all_events(Path(args.events))

    by_session: dict[str, dict] = {}
    for e in events:
        sid = e.get("session_id")
        if not sid:
            continue
        slot = by_session.setdefault(
            sid,
            {
                "learner_id": e.get("learner_id"),
                "arm": None,
                "method": None,
                "respondent": e.get("respondent"),
                "immediate": [],
                "delayed": [],
                "diagnostic": [],
                "practice": [],
            },
        )
        if e.get("event_type") == "session_start":
            slot["arm"] = e.get("arm") or slot["arm"]
            slot["respondent"] = e.get("respondent", slot["respondent"])
        if e.get("event_type") == "method_selected":
            slot["method"] = e.get("method")
            slot["arm"] = e.get("arm") or slot["arm"]
        if e.get("event_type") == "session_end":
            slot["arm"] = e.get("arm") or slot["arm"]
            slot["method"] = e.get("method") or slot["method"]
            slot["immediate_score_end"] = e.get("immediate_score")
            slot["delayed_score_end"] = e.get("delayed_score")
        if e.get("event_type") == "item_response":
            ot = e.get("outcome_type")
            if ot in slot and isinstance(slot[ot], list):
                slot[ot].append(bool(e.get("correct")))
            slot["arm"] = e.get("arm") or slot["arm"]
            slot["respondent"] = e.get("respondent", slot["respondent"])

    rows = []
    for sid, s in by_session.items():
        imm = s["immediate"]
        dely = s["delayed"]
        # support delayed_24h key
        if not dely:
            dely = []
        # gather delayed_24h from raw if needed
        delayed_events = [
            e
            for e in events
            if e.get("session_id") == sid
            and e.get("event_type") == "item_response"
            and e.get("outcome_type") == "delayed_24h"
        ]
        delayed_scores = [bool(e.get("correct")) for e in delayed_events]
        imm_events = [
            e
            for e in events
            if e.get("session_id") == sid
            and e.get("event_type") == "item_response"
            and e.get("outcome_type") == "immediate_post"
        ]
        imm_scores = [bool(e.get("correct")) for e in imm_events]
        rows.append(
            {
                "session_id": sid,
                "learner_id": s["learner_id"],
                "arm": s.get("arm") or "unknown",
                "method": s.get("method"),
                "respondent": s.get("respondent"),
                "immediate_score": float(np.mean(imm_scores)) if imm_scores else s.get("immediate_score_end"),
                "delayed_score": float(np.mean(delayed_scores)) if delayed_scores else s.get("delayed_score_end"),
                "n_delayed_items": len(delayed_scores),
            }
        )

    arms: dict[str, list[float]] = {}
    for r in rows:
        if r["delayed_score"] is None:
            continue
        arms.setdefault(r["arm"], []).append(float(r["delayed_score"]))

    report = {
        "note": "If respondent=simulated, treat as protocol dry-run only.",
        "n_sessions": len(rows),
        "n_events": len(events),
        "by_arm": {
            arm: {
                "n": len(scores),
                "mean_delayed": float(np.mean(scores)),
                "ci95": _ci(scores),
            }
            for arm, scores in arms.items()
        },
        "sessions": rows,
        "limitations": [
            "Small N; not a powered RCT.",
            "Dry-run respondents are simulated unless labeled human.",
            "Immediate_post is not delayed mastery.",
        ],
    }

    json_path = out_dir / "analysis_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [
        "# Pilot analysis pack",
        "",
        report["note"],
        "",
        f"- Sessions: **{report['n_sessions']}**",
        f"- Events: **{report['n_events']}**",
        "",
        "## Delayed scores by arm",
        "",
    ]
    for arm, block in report["by_arm"].items():
        md.append(
            f"- **{arm}**: n={block['n']}, mean={block['mean_delayed']:.3f}, "
            f"95% CI={block['ci95']}"
        )
    md += ["", "## Limitations", ""] + [f"- {x}" for x in report["limitations"]]
    md_path = out_dir / "TECHNICAL_NOTE.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(report["by_arm"], indent=2))


if __name__ == "__main__":
    main()
