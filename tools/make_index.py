#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate INDEX.md from the converted tree.

Usage:
    python tools/make_index.py [SRC_DIR] [OUT_DIR]
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../jailbreaks-main")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
SKIP = {"README.md", "UPSTREAM_README.md", "INDEX.md"}


def main() -> int:
    rows = []
    total_s = total_d = 0
    for src in sorted(SRC.rglob("*.md")):
        rel = src.relative_to(SRC)
        if rel.name in SKIP:
            continue
        dst = OUT / rel
        s = len(src.read_text(encoding="utf-8", errors="replace"))
        d = len(dst.read_text(encoding="utf-8", errors="replace")) if dst.is_file() else 0
        total_s += s
        total_d += d
        rows.append((rel.as_posix(), s, d))

    by_dir: dict[str, list] = {}
    for rel, s, d in rows:
        top = rel.split("/")[0] if "/" in rel else "(root)"
        by_dir.setdefault(top, []).append((rel, s, d))

    lines = [
        "# Index",
        "",
        "Every prompt from the upstream collection, rewritten in BabelTele.",
        "Paths match the upstream repository one-to-one.",
        "",
        f"- files **{len(rows)}**",
        f"- source **{total_s:,}** characters",
        f"- BabelTele **{total_d:,}** characters",
        f"- overall retention **{total_d / total_s * 100:.1f}%**" if total_s else "",
        "",
        "Style spec: [`tools/CONVENTIONS.md`](tools/CONVENTIONS.md). "
        "Worked example: [`tools/exemplar.md`](tools/exemplar.md).",
        "Re-check with `python tools/audit.py`.",
        "",
    ]

    for top in sorted(by_dir):
        lines.append(f"## {top}")
        lines.append("")
        lines.append("| file | source | BabelTele | retention |")
        lines.append("|---|---:|---:|---:|")
        for rel, s, d in by_dir[top]:
            name = rel.split("/", 1)[1] if "/" in rel else rel
            ratio = f"{d / s * 100:.0f}%" if s and d else "—"
            lines.append(f"| `{name}` | {s:,} | {d:,} | {ratio} |")
        lines.append("")

    lines += [
        "## Notes",
        "",
        "**Passed through unchanged**:",
        "",
        "- `0x8D jailbreaks/grok-fast-v2.md` — a withdrawal notice, not a prompt.",
        "- `Alibaba/qwen-preferences.md` — empty file (1 byte).",
        "- `UPSTREAM_README.md` — the upstream repository's own README, kept for provenance.",
        "",
        "**Duplicated upstream, converted once**: `0x8D jailbreaks/` ships "
        "`chatgpt-free-tier.md`, `gemini-chat.md`, `grok-fast.md` and `kimi-standard.md` "
        "as four byte-identical copies; `Stealth Models/Unified.md` duplicates "
        "`DeepSeek/deepseekv4.1 and v4.1-1017.md`.",
        "",
        "**Why some files sit near 60%**: they contain long verbatim literals — banned-phrase "
        "lexicons such as `\"I can't\"`, `\"as an AI\"`, `\"hope this helps\"` — that only work "
        "if the exact string survives. Those blocks cannot be compressed. They are not padding.",
        "",
        "**Known numeric divergence**: in `BigPickle-opencode.md` the few-shot C++ sample lost "
        "the array length in `char buf[32]`. The call chain, `sprintf_s(\"%02X\")` and the "
        "`strftime` format string are all intact; no rule was lost.",
        "",
    ]

    text = "\n".join(x for x in lines if x is not None)
    (OUT / "INDEX.md").write_text(text, encoding="utf-8")
    print(f"wrote {OUT / 'INDEX.md'} ({len(rows)} entries, retention {total_d / total_s * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
