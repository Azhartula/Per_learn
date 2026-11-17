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


def _latest_session(sessions_dir: Path) -> Path | None:
    files = sorted(sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-session",
        action="store_true",
        help="Run a fresh Phase 3 demo session before building",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--name", default="Alex")
    args = parser.parse_args()

    web = ROOT / "web"
    docs = ROOT / "docs"
    assets = docs / "assets"
    sessions = ROOT / "outputs" / "sessions"
    chart = ROOT / "outputs" / "phase1_time_to_mastery.png"

    if args.refresh_session:
        print("Running Phase 3 demo session…")
        session = run_session(student_name=args.name, mode="demo", seed=args.seed)
        save_session(session, sessions)

    session_path = _latest_session(sessions)
    if session_path is None:
        raise SystemExit("No session JSON found. Run scripts/run_phase3.py first.")
    if not chart.exists():
        raise SystemExit("Missing Phase 1 chart. Run scripts/run_phase1.py first.")

    if docs.exists():
        shutil.rmtree(docs)
    assets.mkdir(parents=True)

    for name in ("index.html", "parent.html", "parent.js", "styles.css"):
        shutil.copy2(web / name, docs / name)

    shutil.copy2(chart, assets / "phase1_time_to_mastery.png")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    # Keep a stable demo copy in outputs + embed for the static site.
    demo_copy = sessions / "demo_session.json"
    demo_copy.write_text(json.dumps(session, indent=2), encoding="utf-8")
    (assets / "session.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    (assets / "session.js").write_text(
        "window.PERLEARN_SESSION = " + json.dumps(session) + ";\n",
        encoding="utf-8",
    )

    # GitHub Pages needs no jekyll quirks for underscore paths etc.
    (docs / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built site in {docs}")
    print(f"Session source: {session_path.name}")
    print("Serve locally:  PYTHONPATH=src python scripts/serve_demo.py")
    print("Or open:        docs/index.html")


if __name__ == "__main__":
    main()
