#!/usr/bin/env python3
"""Download ASSISTments 2009 skill-builder CSV used for BKT calibration."""

from __future__ import annotations

import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/CAHLR/pyBKT-examples/master/data/as.csv"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "as.csv"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and OUT.stat().st_size > 1_000_000:
        print(f"Already present: {OUT} ({OUT.stat().st_size:,} bytes)")
        return
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, OUT)
    print(f"Saved {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
