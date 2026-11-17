#!/usr/bin/env python3
"""Serve the docs/ demo site on localhost."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not DOCS.exists():
        raise SystemExit("docs/ missing. Run: python scripts/build_demo_site.py")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"PerLearn demo → http://127.0.0.1:{args.port}/")
        print("Parent dashboard → http://127.0.0.1:{}/parent.html".format(args.port))
        print("Ctrl+C to stop")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
