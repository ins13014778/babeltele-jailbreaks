# BabelTele Jailbreaks

A collection of model system prompts, rewritten in **BabelTele** — a dense,
symbolic, model-facing representation that deliberately gives up human
readability in exchange for information density.

The prompts come from [`togg53192-cmd/jailbreaks`](https://github.com/togg53192-cmd/jailbreaks)
(≈18k stars). Every one of them was re-authored — not mechanically substituted —
into BabelTele form, preserving each rule, condition, exception, name and number
while cutting the text roughly in half.

**720,008 → 381,893 characters (53.0%).** Paths mirror the upstream repository
one-to-one, so the two trees can be diffed side by side.

---

## What BabelTele is

From *Large Language Models Do Not Always Need Readable Language*
(Zhu, Peng, Wang, Ke, Zhang, Zhang — [arXiv:2606.19857](https://arxiv.org/abs/2606.19857)):

> Large language models are commonly prompted and interfaced with human-readable
> natural language, even when the intended reader is another model. … semantic
> information can be encoded in compact, non-standard textual forms that sacrifice
> human readability while remaining recoverable by LLMs.

The paper elicits this with a prompt that tells the compressor its audience is
another model, then lets it collapse syntax into symbols, emoji, cross-lingual
fragments and telegram-style anchors. The result looks like this:

```
§2 B=唯decline:
1 sex∋<18|sexualize(<18),∀form
2 facilitate(child sex-exploit|abuse)
3 attack|real-world-violence→specific identified real person|group
```

A reader who knows the domain can still parse it. A reader who does not, cannot.
That is the intended trade.

## Why bother compressing a system prompt

A system prompt occupies context on every single turn. These ones are long —
the largest is 36 KB. Halving them buys back room for actual work, and makes a
different question testable: **does a prompt still steer the model the same way
after its surface form is destroyed?** That is an empirical question, and this
repo is the material for answering it, not the answer.

## What was actually done

Fifty distinct documents (55 files including byte-identical duplicates) were
rewritten by a model following a single written spec:

- [`tools/CONVENTIONS.md`](tools/CONVENTIONS.md) — anchor dictionary, symbol
  table, sentence-rewrite rules, self-check list
- [`tools/exemplar.md`](tools/exemplar.md) — one worked source/result pair,
  used as the style baseline for every file

The spec is the important artifact. It fixes `§` for sections, `@name(k:v)` for
entities, `?cond=>act` for branches, `!obj:detail` for exceptions, and `+`/`-`/`¬`
for imperative force — so 55 files written in parallel still speak one dialect.
(The spec itself is written in Chinese; the anchor table above is its summary.)

Rewrite, not find-and-replace: a rule that becomes unintelligible under
mechanical substitution stays as words. Density is a goal, losslessness is a
constraint, and where they conflict the constraint wins.

## Verification

Every file was checked automatically for three things:

| check | what it catches | result |
|---|---|---|
| compression ratio | files that were barely touched | 37%–61%, one file at 100% (pass-through) |
| number fidelity | every numeric token in the source must appear in the output | 1 divergence in 53 files |
| English residue | lines of untouched prose | 15 hits, all verified as verbatim literals |

The residue hits are the interesting ones. They are **banned-phrase lexicons** —
`"I can't"`, `"as an AI"`, `"hope this helps"` — which exist so the model can
recognise and suppress those exact strings at generation time. Change a character
and the entry stops working. That is also why several files sit near 60%: the
literal block is incompressible, and the ratio is a consequence, not slack.

Reproduce the checks:

```bash
git clone https://github.com/togg53192-cmd/jailbreaks ../jailbreaks-main
python tools/audit.py                    # full sweep
python tools/missing.py "Google/Gemini-4-Carbon.md"    # per-file number diff
python tools/stray.py  "Alibaba/qwen-3.7.md"           # per-file prose residue
```

### The one known divergence

`0x8D jailbreaks/BigPickle-opencode.md` §23 is a few-shot block containing a
complete C++ keylogger. It was compressed into a dense spec — the call chain,
`SetWindowsHookEx(WH_KEYBOARD_LL, …)`, `sprintf_s("%02X")` and the
`strftime("%Y-%m-%d %H:%M:%S")` format are all present — but the sample is no
longer directly compilable, and `char buf[32]` lost its array length. No rule was
lost; the example lost its compilability. If you need that example runnable,
restore it from upstream.

### What was not measured

Nobody ran these prompts against the models they target. This repo makes **no
claim** that a compressed prompt steers a model identically to the original.
Compression ratio and literal fidelity are measured; behavioural equivalence is
not. Treat the converted set as a hypothesis to test, not a drop-in replacement.

## Passed through unchanged

- `0x8D jailbreaks/grok-fast-v2.md` — a security withdrawal notice, not a prompt
- `Alibaba/qwen-preferences.md` — empty (1 byte)
- `UPSTREAM_README.md` — the original repo's README, kept for provenance

Byte-identical duplicates upstream were converted once and copied:
`0x8D jailbreaks/{chatgpt-free-tier,gemini-chat,grok-fast,kimi-standard}.md`, and
`Stealth Models/Unified.md` vs `DeepSeek/deepseekv4.1 and v4.1-1017.md`.

## Repository layout

```
.
├── INDEX.md          per-file sizes and retention
├── UPSTREAM_README.md
├── 0x8D jailbreaks/ … Zhipu AI/     converted prompts, path-mirrored
└── tools/
    ├── CONVENTIONS.md   the rewrite spec
    ├── exemplar.md      worked example
    ├── audit.py         full verification sweep
    ├── missing.py       number-diff for one file
    ├── stray.py         prose-residue report for one file
    ├── make_index.py    regenerates INDEX.md
    └── babeltele.py     the prompt-driven converter (text ⇄ BabelTele)
```

`tools/babeltele.py` is the general-purpose tool that came out of the same work:
17 prompt variants from the paper's appendix, a reverse `expand` pass, a
`verify` fact-coverage check, and a local web UI. It needs an OpenAI-compatible
endpoint; `python tools/babeltele.py serve` or `--prompt-only` for manual use.

## Attribution

The prompts are the work of [**togg53192-cmd**](https://github.com/togg53192-cmd)
and the contributors to [`togg53192-cmd/jailbreaks`](https://github.com/togg53192-cmd/jailbreaks).
This repository is an independent transformation of that collection and is not
affiliated with or endorsed by its author.

The BabelTele framing, prompts and evaluation methodology are from
**Jiayi Zhu, Haoxuan Peng, Junxi Wang, Liang Ke, Chen Zhang, Linfeng Zhang**,
*Large Language Models Do Not Always Need Readable Language*, arXiv:2606.19857.

## License

The tooling in `tools/` and the transformation layer are MIT — see
[`LICENSE`](LICENSE).

The underlying prompt text is **not** covered by that license. Upstream declares
no license, which under default copyright means all rights reserved by its
authors. It is reproduced here as a clearly-attributed derivative for research
and interoperability. If you are a rights holder and want something changed or
removed, open an issue.

Read [`NOTICE`](NOTICE) before redistributing.

The upstream collection describes itself as research and educational material
documenting how instruction hierarchies and policy overrides affect model
behaviour. That framing is inherited here. Whether a given prompt is acceptable
to run against a given service is between you and that service's terms.
