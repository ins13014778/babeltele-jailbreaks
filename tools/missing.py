#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show which numbers a converted file dropped, with surrounding context.

Usage:
    python tools/missing.py "<relative/path.md>" [SRC_DIR] [OUT_DIR]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_NUM = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")


def clean(s: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", s)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rel = Path(sys.argv[1])
    src_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../jailbreaks-main")
    out_root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".")

    s_path, d_path = src_root / rel, out_root / rel
    if not s_path.is_file():
        print(f"source not found: {s_path}")
        return 1
    s = s_path.read_text(encoding="utf-8", errors="replace")
    d = d_path.read_text(encoding="utf-8", errors="replace") if d_path.is_file() else ""
    dn = clean(d)

    print(f"=== {rel} ===")
    seen = set()
    hits = 0
    for m in _NUM.finditer(s):
        val = clean(m.group(0))
        if val in seen or val in dn:
            continue
        seen.add(val)
        hits += 1
        a, b = max(0, m.start() - 55), min(len(s), m.end() + 55)
        print(f"  missing {val!r:>10}   ...{' '.join(s[a:b].split())}...")
    if not hits:
        print("  no missing numbers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
