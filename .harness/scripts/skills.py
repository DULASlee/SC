#!/usr/bin/env python3
"""Phase2 skill 内联加载 + 预算 + TDD 证据规则。"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# 诊断流：所有 [skills] 诊断行都走这里，而不是 sys.stderr。
# 强制 UTF-8 重配 + 异常兜底（encode 失败 → ASCII 兜底）：诊断行必须"永远可读"，
# 不因宿主控制台编码（GBK/UTF-8/管道/CI 断言）改变可读性。
_DIAG = None


def _diag(msg: str) -> None:
    """写一行诊断到 stderr；UTF-8 优先，宿主编码不可用时 ASCII 兜底。"""
    global _DIAG
    if _DIAG is None:
        try:
            f = sys.stderr
            if hasattr(f, "reconfigure"):
                f.reconfigure(encoding="utf-8")
            _DIAG = f
        except Exception:
            _DIAG = io.TextIOWrapper(sys.stderr.buffer, encoding="ascii",
                                     errors="replace") if hasattr(sys.stderr, "buffer") else sys.stderr
    try:
        print(msg, file=_DIAG)
    except Exception:
        # 最后兜底：纯 ASCII（msg 里避免 CJK）
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
        except Exception:
            pass

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
    """候选按"最具体优先"生成：显式前缀路径 > 裸名/场景子目录 > 文件式 > 裸目录。

    顺序约定（误命中/优先级排查看这里）：
    1. 带 "superpowers/" 前缀时，base/superpowers/<n>/SKILL.md 排最前——
       前缀写法命中的是它，而不是裸名目录；
    2. 裸名 base/<n>/SKILL.md 与场景子目录 base/superpowers/<n>/SKILL.md
       （裸名写法的最后候选，即裸名目录优先于场景子目录——
       裸名目录若存在就是最具体定义，场景子目录只是补"按场景组织"布局的洞）；
    3. 文件式 base/<n>.md；4. 裸目录 base/<n>。

    **隐含假设（优先级类 bug 的灾难场景：命中了错的那个，而不是没命中）**：
    "最具体路径上的 SKILL.md 一定是对的"。这个假设在文件被误改/复制覆盖
    时不成立——优先级越高错得越坚定。为封住这个边界，`load_skill_texts` 在
    命中候选后做内容健全性校验（`_skill_md_plausible`）：校验不通过时降级到
    次选候选（场景子目录 / 裸目录），并向 stderr 打 `[skills] CONTENT-BAD`
    诊断行。校验仍失败（所有候选都内容异常）才按 MISS 跳过。
    本假设与降级策略是"命中错的那一个"的唯一防线，勿在后续重构中删掉。
    """
    cands: list[Path] = []
    stripped = name
    has_prefix = name.startswith("superpowers/")
    if has_prefix:
        stripped = stripped[len("superpowers/"):]
        cands.append(base / name / "SKILL.md")
        cands.append(base / stripped / "SKILL.md")
        cands.append(base / (stripped + ".md"))
        cands.append(base / stripped)
    else:
        cands.append(base / name / "SKILL.md")
        cands.append(base / (name + ".md"))
        cands.append(base / name)
        scene = base / "superpowers"
        if scene.is_dir():
            cands.append(scene / name / "SKILL.md")
    # 去重保序
    seen: set[str] = set()
    out: list[Path] = []
    for p in cands:
        k = p.as_posix()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _skill_md_plausible(raw: str) -> bool:
    """SKILL.md 内容健全性校验（防"命中了错的那个"：最具体路径上的 SKILL.md
    被误改/复制覆盖后，优先级越高错得越坚定）。

    规则：至少满足其一——
      a. 开头含 YAML frontmatter（首个非空行为 `---`）；或
      b. 开头含 `# skill` / `# <skill-name>` 形式的 H1 标题；或
      c. 非空字节长度 > 0 且含 "## " 小节（说明是结构化说明文档）。
    全部不满足 → 视为内容异常（空白文件、误覆盖成别的文档等），由调用方降级。
    注意：这是启发式，不是解析校验；真正常规 skill 极少会误伤。
    """
    s = (raw or "").lstrip()
    if not s:
        return False
    first = s.split("\n", 1)[0]
    if first.strip() == "---":
        return True
    if first.lstrip().startswith("# "):
        return True
    return "## " in s


def load_skill_texts(names, skills_dir, cap_bytes) -> tuple[dict, dict]:
    """加载 skill 文本；**契约**：诊断信息（MISS/READ-FAIL/CONTENT-BAD）只写
    stderr（经 _diag 统一 UTF-8 + 编码兜底），stdout 永远干净，
    管道/CI 断言可安全依赖 stdout。

    降级策略：某候选读到的 SKILL.md 内容校验失败（`_skill_md_plausible`）时
    不直接弃用，而是继续用 `_candidate_paths` 的下一个候选；全部候选都
    内容异常 → 按 MISS 跳过并记 CONTENT-BAD 诊断行。
    """
    base = Path(skills_dir)
    texts: dict[str, str] = {}
    truncated: dict[str, bool] = {}
    for name in names or []:
        all_cands = _candidate_paths(base, str(name))
        chosen: Path | None = None
        raw = ""
        for cand in all_cands:
            if not cand.is_file():
                continue
            try:
                raw = cand.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                _diag(f"[skills] READ-FAIL: {name!r} -> {cand}: {e}")
                continue
            if _skill_md_plausible(raw):
                chosen = cand
                break
            else:
                _diag(f"[skills] CONTENT-BAD: {name!r} -> {cand} lacks frontmatter/name; falling back")
        if chosen is None:
            _diag(f"[skills] MISS: {name!r} not found under {base} (candidates incl. superpowers/ scene dir)")
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
