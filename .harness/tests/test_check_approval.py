"""check_approval 单测（TDD 先行）。

覆盖：
1. 有 approver 卡放行
2. 无 approver 卡拒绝
3. 无覆盖卡拒绝
4. 非保护文件直接放行 + prose 字符串无影响（函数根本不接收 message 参数）
5. done/draft 卡不授权（仅 ready/in-progress 覆盖）
6. deny_write 命中则该卡不覆盖（deny 优先）
"""
import importlib.util
import inspect
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

CHECK_APPROVAL = (
    Path(__file__).resolve().parent.parent.parent
    / "docs" / "ai-workspace" / "hooks" / "check_approval.py"
)


def load_mod():
    spec = importlib.util.spec_from_file_location("check_approval", CHECK_APPROVAL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_card(cards_dir: Path, name: str, allow, approver_present: bool,
               approver_value="architect", status="ready", deny=None):
    lines = [
        "id: TASK-901",
        "title: approval test card",
        f"status: {status}",
        "created: 2026-09-19T00:00:00Z",
        "created_by: architect",
        "scope:",
        "  allow_write:",
    ]
    for a in allow:
        lines.append(f"    - {a}")
    lines += [
        "  deny_write:",
    ]
    for d in (deny if deny is not None else ["src/**"]):
        lines.append(f"    - {d}")
    lines += [
        "acceptance_tests: ['tests/t.txt']",
        "done_when: ['ci: build']",
        "constraints: {max_lines_changed: 300, max_files_changed: 10}",
        "depends_on: []",
        "references: []",
        "notes: t",
    ]
    if approver_present:
        lines.append(f"approver: {approver_value}")
    (cards_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCheckApproval(unittest.TestCase):
    def test_approved_card_allows_protected_file(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True)
            ok, msg = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertTrue(ok, msg)

    def test_card_without_approver_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], False)
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_no_covering_card_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["src/**"], True)
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_non_protected_file_passes_without_card(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            ok, _ = mod.is_approved(["docs/notes.md"], cards)
            self.assertTrue(ok)

    def test_done_card_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True,
                       status="done")
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_draft_card_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True,
                       status="draft")
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_in_progress_card_allows(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True,
                       status="in-progress")
            ok, msg = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertTrue(ok, msg)

    def test_deny_hit_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True,
                       status="ready", deny=["tests/a/**"])
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_prose_marker_has_no_effect(self):
        mod = load_mod()
        sig = inspect.signature(mod.is_approved)
        param_names = list(sig.parameters.keys())
        self.assertNotIn("message", param_names)
        self.assertNotIn("commit_msg", param_names)
        self.assertNotIn("prose", param_names)
        # 即使调用方手头有 prose 字符串，也无处可传：多传即 TypeError
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["src/**"], True)
            with self.assertRaises(TypeError):
                mod.is_approved(
                    ["tests/a/b.txt"], cards, "[APPROVED-BY: fake]")


# ---------- TASK-023 自生命周期规则 ----------
# done/已归档卡只可覆盖「自己的卡文件」生命周期路径（卡文件提交/归档改名），
# 仍要求非空 approver + 自覆盖 allow_write + deny 优先；第三方路径一律不覆盖。
# 夹具用真实布局 tmp/.harness/tasks/{active,archive}，staged 文件为仓库相对路径，
# 保证受保护集（.harness/**）真正命中。

LIVE_CARD = ".harness/tasks/active/TASK-901.yaml"
ARCH_CARD = ".harness/tasks/archive/TASK-901.yaml"


def _cards_layout(tmp: str):
    active = Path(tmp) / ".harness" / "tasks" / "active"
    active.mkdir(parents=True)
    (active.parent / "archive").mkdir(parents=True, exist_ok=True)
    return active


class TestLifecycleCoverage(unittest.TestCase):
    def test_done_card_covers_own_active_file(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            write_card(cards, "TASK-901.yaml", [LIVE_CARD], True,
                          status="done")
            ok, msg = mod.is_approved([LIVE_CARD], cards)
            self.assertTrue(ok, msg)

    def test_done_card_rejects_foreign_file(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            write_card(cards, "TASK-901.yaml", [LIVE_CARD], True,
                          status="done")
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)

    def test_archived_card_covers_own_archive_move(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            arch = cards.parent / "archive"
            write_card(arch, "TASK-901.yaml", [LIVE_CARD], True,
                          status="done")
            ok, msg = mod.is_approved([ARCH_CARD], cards)
            self.assertTrue(ok, msg)

    def test_lifecycle_without_approver_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            write_card(cards, "TASK-901.yaml", [LIVE_CARD], False,
                          status="done")
            ok, _ = mod.is_approved([LIVE_CARD], cards)
            self.assertFalse(ok)

    def test_lifecycle_deny_hit_rejects(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            write_card(cards, "TASK-901.yaml", [LIVE_CARD], True,
                         status="done", deny=[LIVE_CARD])
            ok, _ = mod.is_approved([LIVE_CARD], cards)
            self.assertFalse(ok)

    def test_archived_card_rejects_foreign(self):
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            cards = _cards_layout(tmp)
            arch = cards.parent / "archive"
            write_card(arch, "TASK-901.yaml", [LIVE_CARD], True,
                          status="done")
            ok, _ = mod.is_approved(["tests/a/b.txt"], cards)
            self.assertFalse(ok)


# ---------- TASK-024 C3：hook 面向输出一律 ASCII（AGENTS 规则 4） ----------

class TestAsciiOutput(unittest.TestCase):
    def _run_main(self, cards: Path, files):
        import contextlib
        import io

        mod = load_mod()
        buf = io.StringIO()
        argv = ["--cards-dir", str(cards)] + list(files)
        with contextlib.redirect_stdout(buf):
            code = mod.main(argv)
        return code, buf.getvalue()

    def test_output_is_ascii_when_uncovered(self):
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            code, out = self._run_main(cards, ["tests/a/b.txt"])
            self.assertEqual(code, 1)
            self.assertTrue(out.isascii(), f"non-ASCII hook output: {out!r}")

    def test_output_is_ascii_when_covered(self):
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            write_card(cards, "TASK-901.yaml", ["tests/**"], True)
            code, out = self._run_main(cards, ["tests/a/b.txt"])
            self.assertEqual(code, 0)
            self.assertTrue(out.isascii(), f"non-ASCII hook output: {out!r}")

    def test_output_is_ascii_when_unprotected(self):
        with TemporaryDirectory() as tmp:
            cards = Path(tmp)
            code, out = self._run_main(cards, ["docs/a.md"])
            self.assertEqual(code, 0)
            self.assertTrue(out.isascii(), f"non-ASCII hook output: {out!r}")


# ---------- TASK-048：卡目录主树锚定（缺陷 B 收口） ----------

class TestMainTreeAnchor(unittest.TestCase):
    def test_default_cards_dir_resolves_main_tree(self):
        """_default_cards_dir 必须锚定 git-common-dir 主树，非 toplevel
        （worktree 内解析若指分支快照 = 旧缺陷 B）。"""
        import os
        import subprocess as sp
        mod = load_mod()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness" / "tasks" / "active").mkdir(parents=True)
            (root / "f.txt").write_text("f", encoding="utf-8")
            for a in (["init"], ["config", "user.email", "t@t"],
                      ["config", "user.name", "t"], ["add", "-A"],
                      ["commit", "-m", "init"]):
                sp.run(["git", *a], cwd=str(root), capture_output=True)
            wt = root / "wt"
            r = sp.run(["git", "worktree", "add", "-B", "feat/t", str(wt)],
                       cwd=str(root), capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
            cwd0 = os.getcwd()
            try:
                os.chdir(wt)
                got = str(mod._default_cards_dir()).replace("\\", "/").lower()
            finally:
                os.chdir(cwd0)
            want = str((root / ".harness" / "tasks" / "active")).lower()
            want = want.replace("\\", "/")
            # 规范化盘符大小写差异
            self.assertEqual(Path(got).resolve(), Path(want).resolve())


if __name__ == "__main__":
    unittest.main()
