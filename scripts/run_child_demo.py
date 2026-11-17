#!/usr/bin/env python3
"""Simulate multi-week child trajectories and save JSON for the demo site."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.trajectory import CHILD_PROFILES, simulate_all_profiles, simulate_child


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=list(CHILD_PROFILES) + ["all"], default="all")
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(ROOT / "outputs" / "trajectories" / "children.json"))
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.child == "all":
        payload = simulate_all_profiles(n_sessions=args.sessions, seed=args.seed)
    else:
        traj = simulate_child(args.child, n_sessions=args.sessions, seed=args.seed)
        payload = {
            "title": "How PerLearn adapts to a real child over time",
            "subtitle": traj.blurb,
            "children": {args.child: traj.to_dict()},
            "default_child": args.child,
        }

    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {out}")
    for pid, child in payload["children"].items():
        print(
            f"  {child['display_name']}: "
            f"{child['sessions'][0]['mastery_before']:.0%} → "
            f"{child['sessions'][-1]['mastery_after']:.0%}  "
            f"switches={len(child['method_switches'])}  "
            f"methods={[s['method'] for s in child['sessions']]}"
        )
        print(f"    {child['final_summary']}")


if __name__ == "__main__":
    main()
