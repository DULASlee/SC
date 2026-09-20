#!/usr/bin/env python3
"""jqkj-search —— 精确的文档/代码检索工具（DSH 智能体用）。

设计目标：用「小输出、高精度」的检索替代「整文件读入 + 目录递归列举」。
实测依据：会话 d503d810 中 189 次工具调用里 126 次是整文件 read（占工具输出
74.6%），而 grep 仅 4 次；4 条 Get-ChildItem -Recurse 目录树占 20 万字符。
详见 docs/reports/2026-09-20-tool-result-context-bloat-analysis.md。

四个子命令：
  doc     概念级文档检索：BM25 排序，返回**章节**（标题路径 + 行号 + 片段）
  sym     符号级代码检索：定义/引用定位，返回 file:line，不读整个文件
  outline 结构概览：文档标题树 / 代码符号表，用于"读之前先看形状"
  find    路径检索：替代目录递归列举，只回计数与少量路径

索引：FTS5(trigram)（SQLite >= 3.34），CJK 子串可匹配；增量重建。
仅用 Python 标准库，无第三方依赖。
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

# Windows 控制台默认 GBK 会让中文输出乱码；DSH 以 UTF-8 捕获，故强制 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[3]          # docs/ai-workspace/tools/jqkj-search/ -> 仓库根
# 索引是构建产物（约 17MB），落在被 .gitignore 覆盖的 .tools/search/ 下，不随版本库分发；
# 重建仅需约 1.5 秒。可用环境变量 JQKJ_SEARCH_DB 覆盖。
DB_PATH = Path(os.environ.get("JQKJ_SEARCH_DB") or (DEFAULT_ROOT / ".tools" / "search" / "index.db"))

DOC_EXT = {".md", ".mdc"}
CODE_EXT = {".cs", ".java", ".py", ".js", ".ts", ".go", ".ps1", ".xaml"}

# 噪声目录/扩展名：实测仓库含 777 .pypredef、768 .pyi、202 .jar，全属可排除项。
EXCLUDE_DIRS = {
    ".git", "node_modules", "bin", "obj", ".decomp", "packages",
    ".vs", "dist", "build", ".tools", "__pycache__", ".harness-bak",
    # 实测：.harness/worktrees/ 是同一仓库在不同任务态下的整份副本，
    # 索引它会让同一文档以 3-4 条重复命中并污染排序（TASK-008/009/010 各一份）。
    "worktrees",
}
EXCLUDE_EXT = {
    ".pypredef", ".pyi", ".jar", ".dll", ".exe", ".zip", ".7z", ".png",
    ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".so", ".dylib", ".class",
}

SNIPPET_CHARS = 160


# ───────────────────────────── 文件遍历 ─────────────────────────────

def iter_files(root: Path, exts: set[str] | None = None):
    """遍历文件，跳过噪声目录与二进制扩展名。exts=None 表示全部文本类文件。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            suf = p.suffix.lower()
            if suf in EXCLUDE_EXT:
                continue
            if exts is not None and suf not in exts:
                continue
            yield p


def read_text(p: Path, limit_bytes: int = 4_000_000) -> str | None:
    try:
        if p.stat().st_size > limit_bytes:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def rel(root: Path, p: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


# ───────────────────────────── 解析器 ─────────────────────────────

HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")

CS_TYPE_RE = re.compile(
    r"^\s*(?:\[[^\]]*\]\s*)*"
    r"(?:(?:public|private|protected|internal|static|sealed|abstract|partial|unsafe|readonly|file)\s+)*"
    r"(class|interface|struct|enum|record|delegate)\s+([A-Za-z_]\w*)"
)
CS_MEMBER_RE = re.compile(
    r"^\s*(?:\[[^\]]*\]\s*)*"
    r"(?:(?:public|private|protected|internal|static|async|virtual|override|sealed|partial|extern|unsafe|new|required)\s+)+"
    r"(?:[\w<>\[\],\.\?]+\s+)+([A-Za-z_]\w*)\s*\("
)
JAVA_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|final|abstract|sealed|non-sealed|strictfp)\s+)*"
    r"(class|interface|enum|record|@interface)\s+([A-Za-z_]\w*)"
)
JAVA_MEMBER_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|final|synchronized|abstract|native|default|strictfp)\s+)+"
    r"(?:[\w<>\[\],\.\?]+\s+)+([A-Za-z_]\w*)\s*\("
)
PY_DEF_RE = re.compile(r"^(\s*)(?:async\s+)?(class|def)\s+([A-Za-z_]\w*)")
JS_DEF_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+([A-Za-z_$][\w$]*)|(class)\s+([A-Za-z_$][\w$]*))"
)
PS_FUNC_RE = re.compile(r"^\s*function\s+([A-Za-z_][\w-]*)", re.IGNORECASE)


def split_sections(text: str):
    """把 Markdown 按标题切成章节；返回 (heading_path, start_line, end_line, body)。"""
    lines = text.splitlines()
    heads = []
    for i, line in enumerate(lines):
        m = HEAD_RE.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    out = []
    if not heads:
        return [("", 1, len(lines), text)]
    if heads[0][0] > 0:
        out.append(("(前言)", 1, heads[0][0], "\n".join(lines[: heads[0][0]])))
    stack: list[tuple[int, str]] = []
    for idx, (ln, level, title) in enumerate(heads):
        stack = [s for s in stack if s[0] < level]
        stack.append((level, title))
        path = " > ".join(t for _, t in stack)
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        body = "\n".join(lines[ln:end])
        out.append((path, ln + 1, end, body))
    return out


def extract_symbols(path: Path, text: str):
    """按语言抽取符号定义；返回 (kind, name, line, container, signature)。"""
    suf = path.suffix.lower()
    out = []
    container = ""
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > 400:          # 压缩/生成文件里的超长行不是定义
            continue
        m = None
        if suf == ".cs":
            if (m := CS_TYPE_RE.match(line)):
                container = m.group(2)
                out.append((m.group(1), m.group(2), i, "", line.strip()[:120]))
            elif (m := CS_MEMBER_RE.match(line)):
                out.append(("member", m.group(1), i, container, line.strip()[:120]))
        elif suf == ".java":
            if (m := JAVA_TYPE_RE.match(line)):
                container = m.group(2)
                out.append((m.group(1).lstrip("@"), m.group(2), i, "", line.strip()[:120]))
            elif (m := JAVA_MEMBER_RE.match(line)):
                out.append(("member", m.group(1), i, container, line.strip()[:120]))
        elif suf == ".py":
            if (m := PY_DEF_RE.match(line)):
                kind = "class" if m.group(2) == "class" else "def"
                if kind == "class":
                    container = m.group(3)
                out.append((kind, m.group(3), i, container if kind == "def" else "", line.strip()[:120]))
        elif suf in (".js", ".ts"):
            if (m := JS_DEF_RE.match(line)):
                name = m.group(1) or m.group(3)
                kind = "function" if m.group(1) else "class"
                if kind == "class":
                    container = name
                out.append((kind, name, i, container if kind == "function" else "", line.strip()[:120]))
        elif suf == ".ps1":
            if (m := PS_FUNC_RE.match(line)):
                out.append(("function", m.group(1), i, "", line.strip()[:120]))
        elif suf == ".xaml":
            if (m := re.match(r"^\s*<(Window|UserControl|Page|ResourceDictionary)\b.*?x:Class=\"([\w\.]+)\"", line)):
                out.append((m.group(1).lower(), m.group(2), i, "", line.strip()[:120]))
    return out


# ───────────────────────────── 索引 ─────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(path TEXT PRIMARY KEY, mtime REAL, size INTEGER, kind TEXT);
CREATE TABLE IF NOT EXISTS index_meta(key TEXT PRIMARY KEY, value TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
    path UNINDEXED, heading UNINDEXED, start_line UNINDEXED, end_line UNINDEXED,
    body, tokenize='trigram');
CREATE TABLE IF NOT EXISTS sym(path TEXT, line INTEGER, kind TEXT, name TEXT,
                              container TEXT, sig TEXT);
CREATE INDEX IF NOT EXISTS sym_name ON sym(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS sym_path ON sym(path);
"""

# 解析器/模式版本：改动抽取逻辑或建表语句时必须 +1，否则增量索引会保留旧结果
# （实测：修正 C# 成员正则后，未变更文件不会重抽，`outline` 仍显示旧的误报）。
INDEX_VERSION = 2


def open_db(db: Path) -> sqlite3.Connection:
    Path(db).parent.mkdir(parents=True, exist_ok=True)   # 索引目录可能尚未创建
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    return con


def build_index(root: Path, db: Path, quiet: bool = False) -> dict:
    t0 = time.time()
    con = open_db(db)
    row = con.execute("SELECT value FROM index_meta WHERE key = 'version'").fetchone()
    force = (row is None) or (row[0] != str(INDEX_VERSION))
    known = {p: (m, s, k) for p, m, s, k in con.execute("SELECT path, mtime, size, kind FROM meta")}
    if force and known:
        con.execute("DELETE FROM doc_fts")
        con.execute("DELETE FROM sym")
        con.execute("DELETE FROM meta")
        known = {}
    seen: set[str] = set()
    n_doc = n_sym = n_skip = 0
    for p in iter_files(root, DOC_EXT | CODE_EXT):
        rp = rel(root, p)
        seen.add(rp)
        try:
            st = p.stat()
        except OSError:
            continue
        kind = "doc" if p.suffix.lower() in DOC_EXT else "code"
        prev = known.get(rp)
        if prev and abs(prev[0] - st.st_mtime) < 1e-6 and prev[1] == st.st_size and prev[2] == kind:
            n_skip += 1
            continue
        text = read_text(p)
        if text is None:
            continue
        con.execute("DELETE FROM doc_fts WHERE path = ?", (rp,))
        con.execute("DELETE FROM sym WHERE path = ?", (rp,))
        if kind == "doc":
            for heading, s, e, body in split_sections(text):
                con.execute(
                    "INSERT INTO doc_fts(path, heading, start_line, end_line, body) VALUES (?,?,?,?,?)",
                    (rp, heading, s, e, body),
                )
                n_doc += 1
        else:
            for k, name, ln, cont, sig in extract_symbols(p, text):
                con.execute(
                    "INSERT INTO sym(path, line, kind, name, container, sig) VALUES (?,?,?,?,?,?)",
                    (rp, ln, k, name, cont, sig),
                )
                n_sym += 1
        con.execute("INSERT OR REPLACE INTO meta(path, mtime, size, kind) VALUES (?,?,?,?)",
                    (rp, st.st_mtime, st.st_size, kind))
    for gone in set(known) - seen:
        con.execute("DELETE FROM doc_fts WHERE path = ?", (gone,))
        con.execute("DELETE FROM sym WHERE path = ?", (gone,))
        con.execute("DELETE FROM meta WHERE path = ?", (gone,))
    con.execute("INSERT OR REPLACE INTO index_meta(key, value) VALUES ('version', ?)", (str(INDEX_VERSION),))
    con.commit()
    stats = {
        "sections": con.execute("SELECT count(*) FROM doc_fts").fetchone()[0],
        "symbols": con.execute("SELECT count(*) FROM sym").fetchone()[0],
        "files": con.execute("SELECT count(*) FROM meta").fetchone()[0],
        "reindexed_sections": n_doc, "reindexed_symbols": n_sym,
        "unchanged": n_skip, "seconds": round(time.time() - t0, 2),
        "forced": force,
    }
    con.close()
    if not quiet:
        print("索引完成: 文件 %(files)d | 文档章节 %(sections)d | 符号 %(symbols)d" % stats)
        print("本次重建: 章节 %(reindexed_sections)d / 符号 %(reindexed_symbols)d，跳过未变更 %(unchanged)d，耗时 %(seconds)ss" % stats)
    return stats


def ensure_index(root: Path, db: Path):
    if not db.exists():
        build_index(root, db, quiet=True)


# ───────────────────────────── 检索 ─────────────────────────────

def make_snippet(body: str, terms: list[str], width: int = SNIPPET_CHARS) -> str:
    flat = re.sub(r"\s+", " ", body).strip()
    pos = -1
    for t in terms:
        pos = flat.find(t)
        if pos >= 0:
            break
    if pos < 0:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def _term_counts(con: sqlite3.Connection, terms: list[str]):
    """每个词元在语料中的章节命中数——用于把"搜不到"变成可诊断的信息。"""
    out = []
    for t in terms:
        like = "%" + t + "%"
        n = con.execute(
            "SELECT count(*) FROM doc_fts WHERE body LIKE ? OR heading LIKE ?", (like, like)
        ).fetchone()[0]
        out.append((t, n))
    return out


def _suggest_for_zero(con: sqlite3.Connection, term: str):
    """零命中词元 → 给出语料中真实存在的 2 字片段，避免 agent 直接放弃转整文件读取。

    实测动机：会话 d503d810 中 agent 搜 "云端聚合"/"点丢失" 得 0 命中（语料确实没有
    这两个词），随后退化为 126 次整文件读取。若当时有本提示，可立即改搜 "断开"(32) 等。
    """
    if len(term) < 2:
        return []
    shards = []
    for i in range(len(term) - 1):
        sh = term[i:i + 2]
        n = con.execute("SELECT count(*) FROM doc_fts WHERE body LIKE ?", ("%" + sh + "%",)).fetchone()[0]
        if n:
            shards.append((sh, n))
    return shards


def search_docs(con: sqlite3.Connection, terms: list[str], any_mode: bool = False, pool: int = 4000):
    """混合检索：>=3 字符词元走 FTS5(trigram) 取候选，再用 LIKE 强制全部词元命中。

    trigram 分词器无法匹配 <3 字符的词（如 CJK 双字词 "断开"），故短词只能靠 LIKE；
    语料仅 ~10MB，全表 LIKE 扫描 <100ms，召回优先。
    """
    fts_terms = [t for t in terms if len(t) >= 3]
    cand = None
    if fts_terms:
        fts_q = " AND ".join('"%s"' % t.replace('"', "") for t in fts_terms)
        try:
            cand = con.execute(
                "SELECT path, heading, start_line, end_line, body, bm25(doc_fts) AS score "
                "FROM doc_fts WHERE doc_fts MATCH ? ORDER BY score LIMIT ?",
                (fts_q, pool),
            ).fetchall()
        except sqlite3.OperationalError:
            cand = None
    if cand is None:
        cand = con.execute(
            "SELECT path, heading, start_line, end_line, body, 0 FROM doc_fts LIMIT ?", (pool,)
        ).fetchall()
    scored = []
    seen_bodies: set[str] = set()
    for path, heading, s, e, body, score in cand:
        hay = body.lower()
        head = (heading or "").lower()
        matched = [t for t in terms if t.lower() in hay or t.lower() in head]
        if not matched:
            continue
        if not any_mode and len(matched) != len(terms):
            continue
        # 内容去重：同一章节在多份副本中重复时只保留一条（先到者路径最短，排序靠前）
        digest = hashlib.sha1(re.sub(r"\s+", "", body).encode("utf-8", "replace")).hexdigest()
        if digest in seen_bodies:
            continue
        seen_bodies.add(digest)
        cnt = sum(hay.count(t.lower()) for t in matched)
        # 密度排序：同样命中数下，优先"短而集中"的章节，避免 468 行的巨型章节霸榜
        density = cnt * 1000.0 / (len(body) + 1)
        scored.append((-len(matched), -density, score, len(body), path, heading, s, e, body))
    scored.sort(key=lambda r: r[:4])
    return scored


def cmd_doc(args) -> int:
    root = Path(args.root).resolve()
    ensure_index(root, DB_PATH)
    con = open_db(DB_PATH)
    q = args.query.strip()
    terms = [t for t in re.split(r"\s+", q) if t]
    counts = _term_counts(con, terms)
    hits = search_docs(con, terms, any_mode=args.any)
    if args.json:
        print(json.dumps(
            [{"path": r[4], "heading": r[5], "start_line": r[6], "end_line": r[7],
              "snippet": make_snippet(r[8], terms)} for r in hits[: args.top]],
            ensure_ascii=False, indent=1))
        return 0
    print("doc 命中 %d 章节，显示 %d（query=%r，%s）"
          % (len(hits), min(len(hits), args.top), q, "OR" if args.any else "AND"))
    print("  词元: " + " | ".join("%s=%d" % (t, n) for t, n in counts))
    for t, n in counts:
        if n == 0:
            shards = _suggest_for_zero(con, t)
            if shards:
                print("  %r 在语料中不存在；可试 2 字片段: %s"
                      % (t, ", ".join("%s(%d)" % (a, b) for a, b in shards)))
    if not hits:
        print("无命中。建议：减少词元（用 --any 放宽）、改用上面提示的片段，或 `find`/`outline` 先定位文件。")
        return 0
    for i, r in enumerate(hits[: args.top], 1):
        _nm, _c, _s, _len, path, heading, s, e, body = r
        print("[%d] %s:%d-%d" % (i, path, s, e))
        if heading:
            print("    章节: %s" % heading)
        print("    %s" % make_snippet(body, terms))
    print("提示: 读全文用 read 并按 offset/limit 取 %d-%d 行，不要整文件读入。" % (hits[0][6], hits[0][7]))
    return 0


def cmd_sym(args) -> int:
    root = Path(args.root).resolve()
    ensure_index(root, DB_PATH)
    con = open_db(DB_PATH)
    name = args.name
    defs = con.execute(
        "SELECT path, line, kind, name, container, sig FROM sym "
        "WHERE name = ? COLLATE NOCASE ORDER BY path, line LIMIT ?", (name, args.top)
    ).fetchall()
    exact = True
    if not defs:
        exact = False
        defs = con.execute(
            "SELECT path, line, kind, name, container, sig FROM sym "
            "WHERE name LIKE ? ORDER BY length(name), path, line LIMIT ?",
            (name + "%", args.top),
        ).fetchall()
    total = con.execute(
        "SELECT count(*) FROM sym WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()[0]
    print("sym %r: 精确定义 %d 处%s" % (name, total, "" if exact else "（已放宽为前缀匹配）"))
    for path, line, kind, nm, cont, sig in defs:
        loc = "%s:%d" % (path, line)
        extra = ("  in %s" % cont) if cont else ""
        print("  %-58s %-9s %s%s" % (loc, kind, nm, extra))
        if sig:
            print("      %s" % sig)
    if not defs:
        print("  未找到定义。可试 `--refs` 查引用，或 `doc` 查文档。")
    if args.refs:
        pat = re.compile(r"\b%s\b" % re.escape(name))
        hits, shown = 0, 0
        print("引用（%s）:" % name)
        for p in iter_files(root, CODE_EXT):
            text = read_text(p)
            if not text:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pat.search(line):
                    hits += 1
                    if shown < args.top:
                        shown += 1
                        print("  %s:%d: %s" % (rel(root, p), i, line.strip()[:110]))
        print("  引用合计 %d 处，显示 %d" % (hits, shown))
    return 0


def cmd_outline(args) -> int:
    root = Path(args.root).resolve()
    p = Path(args.path)
    if not p.is_absolute():
        p = root / p
    text = read_text(p)
    if text is None:
        print("无法读取: %s" % p)
        return 2
    lines = text.splitlines()
    print("outline %s （共 %d 行）" % (rel(root, p), len(lines)))
    items: list[tuple[int, str, str]] = []
    if p.suffix.lower() in DOC_EXT:
        for i, line in enumerate(lines, 1):
            m = HEAD_RE.match(line)
            if m:
                lvl = len(m.group(1))
                items.append((i, " " * (lvl - 1) + "H%d" % lvl, m.group(2)))
    else:
        for kind, name, ln, cont, _sig in extract_symbols(p, text):
            label = kind if not cont else "%s in %s" % (kind, cont)
            items.append((ln, label, name))
    total = len(items)
    for ln, label, name in items[: args.top]:
        print("  L%-6d %-22s %s" % (ln, label, name))
    if total > args.top:
        print("  …（共 %d 项，显示 %d；用 --top 调整）" % (total, args.top))
    if not items:
        print("  （无标题/符号；该文件可能不是文档或源代码）")
    return 0


def cmd_find(args) -> int:
    root = Path(args.root).resolve()
    pat = args.pattern
    hits: list[str] = []
    if args.dirs:
        for dirpath, dirnames, _f in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for d in dirnames:
                rp = rel(root, Path(dirpath) / d)
                if fnmatch.fnmatch(rp, pat) or fnmatch.fnmatch(rp + "/", pat):
                    hits.append(rp + "/")
    else:
        for p in iter_files(root):
            rp = rel(root, p)
            if fnmatch.fnmatch(rp, pat) or fnmatch.fnmatch(rp, "*/" + pat):
                hits.append(rp)
    print("find %r: 命中 %d 项" % (pat, len(hits)))
    if args.count:
        return 0
    for h in sorted(hits)[: args.top]:
        print("  %s" % h)
    if len(hits) > args.top:
        print("  …（共 %d 项，显示 %d；需要计数用 --count）" % (len(hits), args.top))
    return 0


# ───────────────────────────── CLI ─────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jqkj-search", description="精确的文档/代码检索工具")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="仓库根（默认 %s）" % DEFAULT_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doc", help="概念级文档检索（返回章节+行号）")
    d.add_argument("query")
    d.add_argument("--top", type=int, default=6)
    d.add_argument("--any", action="store_true", help="放宽为 OR（任一词元命中即返回）")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_doc)

    s = sub.add_parser("sym", help="符号定义/引用检索")
    s.add_argument("name")
    s.add_argument("--refs", action="store_true", help="附带引用列表")
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(func=cmd_sym)

    o = sub.add_parser("outline", help="文件结构概览（标题/符号 + 行号）")
    o.add_argument("path")
    o.add_argument("--top", type=int, default=60)
    o.set_defaults(func=cmd_outline)

    f = sub.add_parser("find", help="路径检索（替代目录递归列举）")
    f.add_argument("pattern")
    f.add_argument("--top", type=int, default=20)
    f.add_argument("--count", action="store_true")
    f.add_argument("--dirs", action="store_true")
    f.set_defaults(func=cmd_find)

    i = sub.add_parser("index", help="重建/增量刷新索引")
    i.set_defaults(func=lambda a: (build_index(Path(a.root).resolve(), DB_PATH), 0)[1])

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
