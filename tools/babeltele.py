#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""babeltele — BabelTele 转换器

把文本压成高密度「模型原生」表示（BabelTele），或反向还原、核对事实丢失。
提示词取自 arXiv:2606.19857 附录 C，另加反向还原 / 阅读问答 / 可读摘要对照组。

零第三方依赖（PDF 输入可选 pymupdf，token 统计可选 tiktoken）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT_DIR = HERE / "prompts"
VARIANTS_FILE = HERE / "variants.json"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

EXAMPLES = """\
例子:
  python babeltele.py convert 判决书.pdf -o 判决书.bt.txt
  python babeltele.py convert -t "要压缩的一段话" -v BT-P8
  python babeltele.py convert doc.txt --prompt-only        # 只出提示词，粘到网页版用
  cat doc.txt | python babeltele.py convert -v BT-P3
  python babeltele.py expand doc.bt.txt -o doc.expanded.md # 往返还原
  python babeltele.py verify doc.txt doc.bt.txt            # 查数字/专名丢了哪些
  python babeltele.py serve                                # 本地网页界面
"""


class BtError(Exception):
    pass


# --------------------------------------------------------------------- 基础

def utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def die(msg: str, code: int = 2) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_config(args) -> dict:
    load_dotenv(HERE / ".env")
    base = (getattr(args, "base_url", None)
            or os.environ.get("BABELTELE_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_BASE_URL)
    key = (getattr(args, "api_key", None)
           or os.environ.get("BABELTELE_API_KEY")
           or os.environ.get("OPENAI_API_KEY")
           or "")
    model = (getattr(args, "model", None)
             or os.environ.get("BABELTELE_MODEL")
             or DEFAULT_MODEL)
    return {"base_url": base.rstrip("/"), "api_key": key, "model": model}


# --------------------------------------------------------------------- tokens

_ENC = None
_ENC_TRIED = False


def count_tokens(text: str) -> int:
    global _ENC, _ENC_TRIED
    if not _ENC_TRIED:
        _ENC_TRIED = True
        try:
            import tiktoken
            _ENC = tiktoken.get_encoding("o200k_base")
        except Exception:
            _ENC = None
    if _ENC is not None:
        try:
            return len(_ENC.encode(text, disallowed_special=()))
        except Exception:
            pass
    return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    wide = 0
    for ch in text:
        o = ord(ch)
        if (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF
                or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF
                or o >= 0x1F000):
            wide += 1
    return max(1, wide + round((len(text) - wide) / 3.6))


# --------------------------------------------------------------------- 提示词

def load_variants() -> dict:
    if not VARIANTS_FILE.is_file():
        raise BtError(f"缺少变体清单 {VARIANTS_FILE}")
    return json.loads(VARIANTS_FILE.read_text(encoding="utf-8"))


def load_prompt(variant_id: str) -> tuple[str, dict]:
    variants = load_variants()
    if variant_id not in variants:
        raise BtError(f"未知变体 {variant_id!r}；可用：{', '.join(variants)}")
    meta = variants[variant_id]
    path = PROMPT_DIR / meta["file"]
    if not path.is_file():
        raise BtError(f"缺少提示词文件 {path}")
    return path.read_text(encoding="utf-8").rstrip("\n") + "\n\n", meta


# --------------------------------------------------------------------- API

def chat(messages: list[dict], cfg: dict, temperature: float = 0.3,
         timeout: int = 600, retries: int = 4) -> str:
    local = any(h in cfg["base_url"] for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))
    if not cfg["api_key"] and not local:
        raise BtError(
            "未配置 API key。设置 BABELTELE_API_KEY / OPENAI_API_KEY，"
            "或把配置写进 babeltele/.env（模板见 .env.example）。"
        )
    url = cfg["base_url"] + "/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    last = ""
    for attempt in range(retries):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            return (data["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            last = f"HTTP {exc.code}: {detail}"
            if exc.code in (408, 409, 425, 429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 20))
                continue
            raise BtError(last)
        except urllib.error.URLError as exc:
            last = f"网络错误: {exc.reason}"
            time.sleep(min(2 ** attempt, 20))
        except (KeyError, IndexError, ValueError) as exc:
            last = f"响应格式异常: {exc!r}"
            break
    raise BtError(f"请求失败：{last}")


# --------------------------------------------------------------------- 切块

def chunk_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    buf = ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(para), max_chars):
                chunks.append(para[i:i + max_chars])
            continue
        if not buf:
            buf = para
        elif len(buf) + 2 + len(para) <= max_chars:
            buf = buf + "\n\n" + para
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    return chunks


def run_variant(text: str, variant_id: str, cfg: dict, chunk_chars: int,
                workers: int, temperature: float, wrap: bool) -> str:
    prompt, _ = load_prompt(variant_id)
    chunks = chunk_text(text, chunk_chars)
    if not chunks:
        raise BtError("输入为空")

    def one(chunk: str) -> str:
        body = f"<source>\n{chunk}\n</source>" if wrap else chunk
        return chat([{"role": "user", "content": prompt + body}], cfg,
                    temperature=temperature)

    if len(chunks) == 1:
        return one(chunks[0])
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        parts = list(pool.map(one, chunks))
    return "\n\n".join(p for p in parts if p)


# --------------------------------------------------------------------- 读写

def read_pdf(path: Path) -> str:
    module = None
    try:
        import pymupdf as module  # type: ignore
    except ImportError:
        try:
            import fitz as module  # type: ignore
        except ImportError:
            raise BtError("读 PDF 需要 pymupdf：pip install pymupdf")
    doc = module.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def read_any(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def read_input(args) -> str:
    if getattr(args, "text", None):
        return args.text
    src = getattr(args, "input", None) or "-"
    if src == "-":
        if sys.stdin.isatty():
            raise BtError("没有输入：用 -t/--text 给文本，或传文件路径，或用管道")
        return sys.stdin.read()
    path = Path(src)
    if not path.is_file():
        raise BtError(f"文件不存在：{src}")
    return read_any(path)


# --------------------------------------------------------------------- 事实核对

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*(?:\s?%)?")
_DATE_RE = re.compile(r"(?:19|20)\d{2}\s?[-/年.]\s?\d{1,2}(?:\s?[-/月.]\s?\d{1,2}\s?日?)?")
_ENT_RE = re.compile(r"\b[A-Z][A-Za-z0-9&'’\-]{2,}(?:[ \t]+[A-Z][A-Za-z0-9&'’\-]{2,}){0,4}\b")
_QUOTE_RE = re.compile(r"[「『《“\"]([^」』》”\"\n]{2,80})[」』》”\"]")

_KIND_LABEL = {"date": "日期", "num": "数值", "ent": "专名", "quote": "引号"}

_STOPWORDS = {
    "this", "that", "these", "those", "there", "then", "than", "they", "their",
    "however", "therefore", "because", "although", "while", "when", "where",
    "which", "figure", "table", "section", "appendix", "paper", "note", "source",
}


def normalize_for_match(s: str) -> str:
    s = s.lower()
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    return re.sub(r"\s+", "", s)


def extract_facts(text: str) -> dict[tuple[str, str], int]:
    facts: dict[tuple[str, str], int] = {}

    def add(kind: str, value: str) -> None:
        value = value.strip()
        if not value:
            return
        key = (kind, value)
        facts[key] = facts.get(key, 0) + 1

    for m in _DATE_RE.finditer(text):
        add("date", m.group(0).strip())

    for m in _NUM_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 3 and "." not in raw and not raw.endswith("%"):
            continue
        add("num", re.sub(r"(?<=\d),(?=\d)", "", raw))

    for m in _ENT_RE.finditer(text):
        raw = m.group(0).strip(" .,;:()[]")
        if raw.endswith("'s") or raw.endswith("’s"):
            raw = raw[:-2]
        words = raw.split()
        if len(words) >= 2:
            if len(raw) >= 5:
                add("ent", raw)
        else:
            token = words[0]
            if len(token) >= 2 and (token.isupper() or any(c.isdigit() for c in token)):
                if token.lower() not in _STOPWORDS:
                    add("ent", token)

    for m in _QUOTE_RE.finditer(text):
        add("quote", m.group(1))

    return facts


# --------------------------------------------------------------------- 命令

def cmd_convert(args) -> int:
    text = read_input(args)
    if not text.strip():
        raise BtError("输入为空")

    if args.prompt_only:
        prompt, _ = load_prompt(args.variant)
        chunks = chunk_text(text, args.chunk_chars)
        body = f"<source>\n{chunks[0]}\n</source>" if args.wrap else chunks[0]
        sys.stdout.write(prompt + body + "\n")
        if len(chunks) > 1:
            print(f"[提示] 原文切成 {len(chunks)} 块，这里只显示第 1 块的提示词。",
                  file=sys.stderr)
        return 0

    cfg = get_config(args)
    started = time.time()
    out = run_variant(text, args.variant, cfg, args.chunk_chars,
                      args.workers, args.temperature, args.wrap)
    elapsed = time.time() - started

    tin, tout = count_tokens(text), count_tokens(out)
    stats = {
        "variant": args.variant,
        "model": cfg["model"],
        "tokens_in": tin,
        "tokens_out": tout,
        "retention": round(tout / tin, 4) if tin else None,
        "chars_in": len(text),
        "chars_out": len(out),
        "seconds": round(elapsed, 2),
    }

    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({**stats, "output": out}, ensure_ascii=False, indent=2))
    else:
        if not args.output:
            print(out)
        ret = f"{stats['retention'] * 100:.1f}%" if stats["retention"] else "n/a"
        print(f"[{args.variant} · {cfg['model']}] {tin} -> {tout} tokens "
              f"保留率 {ret} {elapsed:.1f}s", file=sys.stderr)
    return 0


def cmd_expand(args) -> int:
    text = read_input(args)
    if not text.strip():
        raise BtError("输入为空")
    cfg = get_config(args)
    started = time.time()
    out = run_variant(text, "expand", cfg, args.chunk_chars, args.workers, 0.2, False)
    elapsed = time.time() - started

    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"model": cfg["model"], "output": out,
                          "tokens_out": count_tokens(out),
                          "seconds": round(elapsed, 2)}, ensure_ascii=False, indent=2))
    else:
        if not args.output:
            print(out)
        print(f"[expand · {cfg['model']}] {len(out)} chars {elapsed:.1f}s", file=sys.stderr)
    return 0


def cmd_verify(args) -> int:
    original_path, candidate_path = Path(args.original), Path(args.candidate)
    for p in (original_path, candidate_path):
        if not p.is_file():
            raise BtError(f"文件不存在：{p}")

    original = read_any(original_path)
    candidate = read_any(candidate_path)
    facts = extract_facts(original)
    if not facts:
        raise BtError("原文里没有抽出可比对的事实项（数字 / 日期 / 专名 / 引号）")

    hay = normalize_for_match(candidate)
    hits = 0
    missing: list[tuple[str, str, int]] = []
    per_kind: dict[str, list[int]] = {}
    for (kind, value), cnt in facts.items():
        bucket = per_kind.setdefault(kind, [0, 0])
        bucket[1] += 1
        if normalize_for_match(value) in hay:
            hits += 1
            bucket[0] += 1
        else:
            missing.append((kind, value, cnt))

    total = len(facts)
    coverage = hits / total
    tin, tout = count_tokens(original), count_tokens(candidate)
    missing.sort(key=lambda item: (-item[2], item[0]))
    kinds = list(_KIND_LABEL)

    if args.json:
        print(json.dumps({
            "tokens_original": tin,
            "tokens_candidate": tout,
            "retention": round(tout / tin, 4) if tin else None,
            "facts": total,
            "hits": hits,
            "coverage": round(coverage, 4),
            "by_kind": {k: {"hit": v[0], "total": v[1]} for k, v in per_kind.items()},
            "missing": [{"kind": k, "value": v, "count": c} for k, v, c in missing],
        }, ensure_ascii=False, indent=2))
        return 0

    ret = f"{tout / tin * 100:.1f}%" if tin else "n/a"
    print(f"token        {tin} -> {tout}   保留率 {ret}")
    print(f"事实项       {total}   命中 {hits}   覆盖率 {coverage * 100:.1f}%")
    parts = []
    for kind in kinds:
        if kind in per_kind:
            hit, tot = per_kind[kind]
            parts.append(f"{_KIND_LABEL[kind]} {hit}/{tot}")
    if parts:
        print("分类         " + "   ".join(parts))
    if missing:
        print(f"\n缺失 {len(missing)} 项（按出现次数排序，最多显示 {args.limit}）：")
        for kind, value, cnt in missing[:args.limit]:
            label = _KIND_LABEL.get(kind, kind)
            print(f"  [{label}] x{cnt}  {value}")
        if len(missing) > args.limit:
            print(f"  ... 还有 {len(missing) - args.limit} 项")
    else:
        print("\n全部事实项均保留。")
    return 0


def cmd_variants(args) -> int:
    variants = load_variants()
    width = max(len(k) for k in variants)
    for key, meta in variants.items():
        print(f"{key.ljust(width)}  {meta['name']}")
        print(f"{' ' * width}  {meta['note']}")
    return 0


def cmd_prompt(args) -> int:
    prompt, meta = load_prompt(args.variant)
    print(prompt.rstrip("\n"))
    print(f"\n# {args.variant} — {meta['name']}", file=sys.stderr)
    return 0


def cmd_config(args) -> int:
    cfg = get_config(args)
    key = cfg["api_key"]
    masked = (key[:6] + "…" + key[-4:]) if len(key) > 12 else ("<未设置>" if not key else "<已设置>")
    print(f"base_url  {cfg['base_url']}")
    print(f"model     {cfg['model']}")
    print(f"api_key   {masked}")
    print(f"配置目录  {HERE}")
    return 0


def cmd_serve(args) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    cfg = get_config(args)
    page = HERE / "ui.html"
    html = page.read_bytes() if page.is_file() else b"<h1>ui.html missing</h1>"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):  # noqa: A003
            pass

        def _send(self, code: int, body, ctype: str) -> None:
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html", "/ui.html"):
                self._send(200, html, "text/html; charset=utf-8")
            elif self.path == "/api/variants":
                self._send(200, json.dumps(load_variants(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self):  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(length).decode("utf-8"))
                text = (req.get("text") or "").strip()
                if not text:
                    self._send(400, json.dumps({"error": "文本为空"}), "application/json")
                    return

                local = dict(cfg)
                if req.get("model"):
                    local["model"] = req["model"].strip()
                if req.get("base_url"):
                    local["base_url"] = req["base_url"].strip().rstrip("/")
                if req.get("api_key"):
                    local["api_key"] = req["api_key"].strip()

                if self.path == "/api/prompt":
                    prompt, _ = load_prompt(req.get("variant") or "default")
                    self._send(200, json.dumps({"prompt": prompt + text},
                                               ensure_ascii=False),
                               "application/json; charset=utf-8")
                    return

                variant = "expand" if self.path == "/api/expand" else (req.get("variant") or "default")
                started = time.time()
                out = run_variant(text, variant, local, args.chunk_chars,
                                  args.workers, float(req.get("temperature") or 0.3),
                                  bool(req.get("wrap")))
                tin, tout = count_tokens(text), count_tokens(out)
                payload = {
                    "output": out,
                    "variant": variant,
                    "model": local["model"],
                    "tokens_in": tin,
                    "tokens_out": tout,
                    "retention": round(tout / tin, 4) if tin else None,
                    "seconds": round(time.time() - started, 2),
                }
                self._send(200, json.dumps(payload, ensure_ascii=False),
                           "application/json; charset=utf-8")
            except BtError as exc:
                self._send(500, json.dumps({"error": str(exc)}, ensure_ascii=False),
                           "application/json; charset=utf-8")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"error": repr(exc)}, ensure_ascii=False),
                           "application/json; charset=utf-8")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"BabelTele 转换器已启动： {url}")
    print(f"模型 {cfg['model']} @ {cfg['base_url']}    按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


# --------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", dest="base_url",
                        help="OpenAI 兼容端点，如 https://api.deepseek.com/v1")
    common.add_argument("--api-key", dest="api_key", help="API key（默认读环境变量）")
    common.add_argument("-m", "--model", help="模型名")
    common.add_argument("--chunk-chars", type=int, default=48000,
                        help="长文切块字符数（默认 48000）")
    common.add_argument("-w", "--workers", type=int, default=4, help="并发块数")

    parser = argparse.ArgumentParser(
        prog="babeltele",
        description="BabelTele 转换器：把文本压成高密度模型原生表示，或反向还原。",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("convert", parents=[common], help="文本 -> BabelTele")
    c.add_argument("input", nargs="?", default="-",
                   help="输入文件（.txt/.md/.pdf），- 表示 stdin")
    c.add_argument("-t", "--text", help="直接给一段文本，优先于 input")
    c.add_argument("-o", "--output", help="输出文件；省略则打印到 stdout")
    c.add_argument("-v", "--variant", default="default", help="提示词变体，见 variants 命令")
    c.add_argument("--temperature", type=float, default=0.3)
    c.add_argument("--wrap", action="store_true", help="用 <source> 标签包裹原文")
    c.add_argument("--prompt-only", "--dry-run", dest="prompt_only", action="store_true",
                   help="只打印拼好的完整提示词，不调用 API")
    c.add_argument("--json", action="store_true", help="以 JSON 输出（含 token 统计）")
    c.set_defaults(func=cmd_convert)

    e = sub.add_parser("expand", parents=[common], help="BabelTele -> 自然语言（往返测试）")
    e.add_argument("input", nargs="?", default="-")
    e.add_argument("-t", "--text")
    e.add_argument("-o", "--output")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_expand)

    v = sub.add_parser("verify", help="核对压缩/还原后丢了哪些数字、日期、专名")
    v.add_argument("original", help="原文文件")
    v.add_argument("candidate", help="压缩结果或还原结果")
    v.add_argument("-n", "--limit", type=int, default=40, help="最多列出多少条缺失项")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)

    sub.add_parser("variants", help="列出所有提示词变体").set_defaults(func=cmd_variants)

    p = sub.add_parser("prompt", help="打印某个变体的原始提示词")
    p.add_argument("-v", "--variant", default="default")
    p.set_defaults(func=cmd_prompt)

    sub.add_parser("config", parents=[common], help="显示当前 API 配置").set_defaults(func=cmd_config)

    s = sub.add_parser("serve", parents=[common], help="启动本地网页界面")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--host", default="127.0.0.1")
    s.set_defaults(func=cmd_serve)

    return parser


def main(argv=None) -> int:
    utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except BtError as exc:
        die(str(exc))
    except KeyboardInterrupt:
        print("\n[中断]", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
