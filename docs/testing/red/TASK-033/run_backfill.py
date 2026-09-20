"""TASK-033 判据 2：回填校验——全 active+drafts 跑，列出缺 approver / 未声明字段。

产出 backfill-report.md（逐卡：卡号 / 是否含 approver / 未声明字段 / 回填值来源）。
11 张 in-progress 历史卡 approver 缺失时标记「历史缺失」（不补填推断值，架构师裁定）。
"""
import importlib.util
import glob
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]


def main():
    spec = importlib.util.spec_from_file_location("v", REPO / ".harness/scripts/validate-task-card.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    declared_top = {x.split(".")[0] for x in m.load_declarations()}

    rows = []
    files = sorted(glob.glob(str(REPO / ".harness/tasks/active/TASK-*.yaml"))) + \
        sorted(glob.glob(str(REPO / ".harness/tasks/drafts/TASK-*.yaml")))
    for f in files:
        p = Path(f)
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        status = d.get("status", "?")
        has_app = "approver" in d
        approver_val = d.get("approver")
        und = [k for k in d if k not in declared_top]
        in_prog = status in ("in-progress",)
        if not has_app:
            source = "历史缺失（不补填推断值，走 R1 逐卡裁定）" if in_prog else "待签发"
        else:
            source = "023 迁移签发记录（approver=architect）"
        rows.append((p.name, status, "Y" if has_app else "N", approver_val, und, source))

    lines = [
        "# TASK-033 判据 2 回填清单",
        f"生成：{datetime.now(timezone.utc).isoformat(timesep='T') if False else datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "说明：approver 值域实测仅 architect（Q3）。未声明字段 = 检测面缺口（本次修复后应为空）。",
        "11 张 in-progress 历史卡 approver 缺失标记「历史缺失」，不补填推断值（架构师裁定 R1）。",
        "",
        "| 卡 | status | 含approver | 值 | 未声明字段 | 回填值来源 |",
        "|---|---|---|---|---|---|",
    ]
    for name, st, y, val, und, src in rows:
        lines.append(f"| {name} | {st} | {y} | {val} | {und if und else '—'} | {src} |")
    n_missing = sum(1 for r in rows if r[2] == "N")
    n_hist = sum(1 for r in rows if r[2] == "N" and r[1] == "in-progress")
    lines += ["", f"缺 approver 卡 = {n_missing}；其中 in-progress 历史卡 = {n_hist}。"]
    out = Path(__file__).with_name("backfill-report.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] {out}  (缺 {n_missing}，历史 {n_hist})")


if __name__ == "__main__":
    main()
