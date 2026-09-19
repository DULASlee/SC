#!/usr/bin/env python3
"""Phase2 skill 内联加载 + 预算 + TDD 证据规则。"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SKILLS_BY_STAGE = {
    "analysis": [],
    "spec": [],
    "plan": ["writing-plans"],
    "execute": ["test-driven-development"],
}

_TRUNC_PREFIX = "…[截断]"


def cap_text(s, limit) -> str:
    if s is None:
        return ""
    s = str(s)
    limit = int(limit)
    if limit <= 0:
        return ""
    if len(s) <= limit:
        return s
    if limit == 1:
        return "…"
    return "…" + s[-(limit - 1):]


def _cap_bytes(s, cap) -> str:
    if s is None:
        return ""
    s = str(s)
    cap = int(cap)
    if cap <= 0:
        return ""
    raw = s.encode("utf-8")
    if len(raw) <= cap:
        return s
    prefix = _TRUNC_PREFIX
    pb = len(prefix.encode("utf-8"))
    budget = cap - pb
    if budget <= 0:
        return prefix
    tail_chars: list[str] = []
    acc = 0
    for ch in reversed(s):
        cb = len(ch.encode("utf-8"))
        if acc + cb > budget:
            break
        tail_chars.append(ch)
        acc += cb
    tail_chars.reverse()
    return prefix + "".join(tail_chars)


def _candidate_paths(base: Path, name: str) -> list[Path]:
    cands: list[Path] = []
    stripped = name
    if stripped.startswith("superpowers/"):
        stripped = stripped[len("superpowers/"):]
    for n in (name, stripped):
        cands.append(base / n / "SKILL.md")
        cands.append(base / (n + ".md"))
        cands.append(base / n)
    # 去重保序
    seen: set[str] = set()
    out: list[Path] = []
    for p in cands:
        k = p.as_posix()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def load_skill_texts(names, skills_dir, cap_bytes) -> tuple[dict, dict]:
    base = Path(skills_dir)
    texts: dict[str, str] = {}
    truncated: dict[str, bool] = {}
    for name in names or []:
        found: Path | None = None
        for cand in _candidate_paths(base, str(name)):
            if cand.is_file():
                found = cand
                break
        if found is None:
            continue
        try:
            raw = found.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        capped = _cap_bytes(raw, int(cap_bytes))
        texts[str(name)] = capped
        truncated[str(name)] = capped != raw
    return texts, truncated


def check_skill_evidence(skill: str, files, card: dict) -> tuple[bool, str]:
    if skill != "test-driven-development":
        return (True, "instruction-only（仅 prompt 指令，无机器证据）")
    acceptance = (card or {}).get("acceptance_tests") or []
    flist = files or []
    for f in flist:
        fs = str(f)
        for a in acceptance:
            a_s = str(a)
            if fs == a_s or fs.endswith("/" + a_s):
                return (True, f"tdd-evidence-ok：触碰 acceptance_tests {a_s}")
    return (False, f"未触碰 acceptance_tests 任一文件：{acceptance}")
