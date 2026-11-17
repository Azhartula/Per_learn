#!/usr/bin/env python3
"""Build a shareable static demo site into docs/ (GitHub Pages)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pll.loop import run_session, save_session
from pll.trajectory import simulate_all_profiles


def _latest_session(sessions_dir: Path) -> Path | None:
    demo = sessions_dir / "demo_session.json"
    if demo.exists():
        return demo
    files = sorted(sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-session",
        action="store_true",
        help="Run a fresh Phase 3 one-shot session before building",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--name", default="Alex")
    parser.add_argument("--sessions", type=int, default=10, help="Weeks in child trajectories")
    args = parser.parse_args()

    web = ROOT / "web"
    docs = ROOT / "docs"
    assets = docs / "assets"
    sessions = ROOT / "outputs" / "sessions"
    traj_dir = ROOT / "outputs" / "trajectories"
    chart = ROOT / "outputs" / "phase1_time_to_mastery.png"

    if args.refresh_session:
        print("Running Phase 3 demo session…")
        session = run_session(student_name=args.name, mode="demo", seed=args.seed)
        save_session(session, sessions)

    print("Simulating multi-week child trajectories…")
    children = simulate_all_profiles(n_sessions=args.sessions, seed=args.seed)
    traj_dir.mkdir(parents=True, exist_ok=True)
    (traj_dir / "children.json").write_text(json.dumps(children, indent=2), encoding="utf-8")

    session_path = _latest_session(sessions)
    if session_path is None:
        # Create a one-shot snapshot if missing.
        session = run_session(student_name=args.name, mode="demo", seed=args.seed)
        paths = save_session(session, sessions)
        session_path = paths["json"]
    if not chart.exists():
        raise SystemExit("Missing Phase 1 chart. Run scripts/run_phase1.py first.")

    if docs.exists():
        shutil.rmtree(docs)
    assets.mkdir(parents=True)

    for name in (
        "index.html",
        "parent.html",
        "parent.js",
        "child.html",
        "child.js",
        "styles.css",
    ):
        shutil.copy2(web / name, docs / name)

    shutil.copy2(chart, assets / "phase1_time_to_mastery.png")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    demo_copy = sessions / "demo_session.json"
    demo_copy.write_text(json.dumps(session, indent=2), encoding="utf-8")
    (assets / "session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    (assets / "session.js").write_text(
        "window.PERLEARN_SESSION = " + json.dumps(session) + ";\n",
        encoding="utf-8",
    )
    (assets / "children.json").write_text(json.dumps(children, indent=2), encoding="utf-8")
    (assets / "children.js").write_text(
        "window.PERLEARN_CHILDREN = " + json.dumps(children) + ";\n",
        encoding="utf-8",
    )
    (docs / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built site in {docs}")
    for pid, child in children["children"].items():
        methods = [s["method"] for s in child["sessions"]]
        print(
            f"  {child['display_name']}: "
            f"{child['sessions'][0]['mastery_before']:.0%}→{child['sessions'][-1]['mastery_after']:.0%} "
            f"switches={len(child['method_switches'])} {methods}"
        )
    print("Open: docs/child.html  or  PYTHONPATH=src python scripts/serve_demo.py")


if __name__ == "__main__":
    main()
