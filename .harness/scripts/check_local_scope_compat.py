"""按文件路径加载 check-local-scope.py，导出纯函数 glob_to_regex。

check-local-scope.py 文件名含连字符，无法直接 import；poll.py 只复用它的
glob→regex 纯函数，不改原文件（二进制/脚本重建原则：复用不复制）。
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "harness_check_local_scope",
    Path(__file__).resolve().parent / "check-local-scope.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
glob_to_regex = _mod.glob_to_regex
