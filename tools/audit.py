#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit the BabelTele conversion: coverage, compression ratio, number fidelity, English residue.

Usage:
    python tools/audit.py [SRC_DIR] [OUT_DIR]

Defaults to ../jailbreaks-main and . (the repo root).
Exit code is 0 always; read the "needs attention" section at the end.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../jailbreaks-main")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")

SKIP = {"README.md", "UPSTREAM_README.md", "INDEX.md"}
PASS_THROUGH = {
    "0x8D jailbreaks/grok-fast-v2.md",   # withdrawal notice, not a prompt
}

_NUM = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")
_ENG = re.compile(
    r"\b(?:the|this|that|these|those|which|would|should|because|however|therefore|must not|do not)\b",
    re.I,
)


def norm_numbers(text: str) -> list[str]:
    return [re.sub(r"(?<=\d),(?=\d)", "", m) for m in _NUM.findall(text)]


def long_english(text: str) -> list[str]:
    bad = []
    for line in text.splitlines():
        words = re.findall(r"[A-Za-z']+", line)
        if len(words) >= 14 and len(_ENG.findall(line)) >= 4:
            bad.append(line.strip()[:110])
    return bad


def main() -> int:
    if not SRC.is_dir():
        print(f"source dir not found: {SRC}")
        print("clone the upstream collection first, e.g.  git clone https://github.com/togg53192-cmd/jailbreaks ../jailbreaks-main")
        return 1

    rows = []
    problems = []

    for src in sorted(SRC.rglob("*.md")):
        rel = src.relative_to(SRC)
        key = rel.as_posix()
        if rel.name in SKIP:
            continue
        dst = OUT / rel
        s = src.read_text(encoding="utf-8", errors="replace")

        if not dst.is_file():
            problems.append(f"missing {key}")
            rows.append((key, len(s), 0, None, "MISSING"))
            continue

        d = dst.read_text(encoding="utf-8", errors="replace")
        ratio = len(d) / len(s) if s else 0
        sn, dn = norm_numbers(s), norm_numbers(d)
        missing_nums = [n for n in sn if n not in dn]
        stray = long_english(d)

        flags = []
        if key in PASS_THROUGH:
            flags.append("passthrough")
        else:
            if ratio > 0.66:
                flags.append("loose")
            if ratio < 0.15:
                flags.append("too-aggressive")
            if missing_nums:
                flags.append(f"missing-numbers x{len(missing_nums)}")
            if stray:
                flags.append(f"english-residue x{len(stray)}")
        if flags:
            problems.append(f"{key}: {', '.join(flags)}")

        rows.append((key, len(s), len(d), ratio, ", ".join(flags) or "ok"))

    print(f"{'file':<52}{'src':>8}{'dst':>8}{'ratio':>8}  flags")
    print("-" * 96)
    for rel, a, b, r, flag in rows:
        rs = f"{r * 100:.0f}%" if r is not None and b else "-"
        print(f"{rel[:50]:<52}{a:>8}{b:>8}{rs:>8}  {flag}")

    total_s = sum(x[1] for x in rows)
    total_d = sum(x[2] for x in rows)
    done = sum(1 for x in rows if x[2])
    print("-" * 96)
    if total_s:
        print(f"done {done}/{len(rows)}   {total_s} -> {total_d} chars   "
              f"overall retention {total_d / total_s * 100:.1f}%")

    if problems:
        print("\nneeds attention:")
        for p in problems:
            print("  " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
