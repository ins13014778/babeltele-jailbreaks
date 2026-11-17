#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print lines that look like un-compressed English prose.

Most hits in this collection are legitimate: they are the banned-phrase
lexicons that must be preserved verbatim to stay effective. This tool exists
so a reviewer can tell the two cases apart.

Usage:
    python tools/stray.py "relative/path.md" [OUT_DIR]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ENG = re.compile(
    r"\b(?:the|this|that|these|those|which|would|should|because|however|therefore|must not|do not)\b",
    re.I,
)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rel = Path(sys.argv[1])
    out_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    p = out_root / rel
    if not p.is_file():
        print(f"not found: {p}")
        return 1

    print(f"=== {rel} ===")
    hits = 0
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        words = re.findall(r"[A-Za-z']+", line)
        if len(words) >= 14 and len(_ENG.findall(line)) >= 4:
            hits += 1
            print(f"  L{i}: {line.strip()[:150]}")
    if not hits:
        print("  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
