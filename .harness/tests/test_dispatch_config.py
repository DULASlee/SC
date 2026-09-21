"""TASK-055 验收测试：.harness/dispatch.yaml 模型路由配置自洽。

守护"模型行"治理面（TASK-046 遗留的 LIVE 待定项）。两条不变量：
  1) primary 不得出现在 fallback 链里（否则升级退化成自回退）；
  2) primary + fallback 的每个条目都必须能在 dsh 的 provider 表里解析
     （provider 必须已配置，且 model id 在该 provider 的 models 列表中）。
     环境无 ~/.dsh/settings.yaml 时跳过（CI 机器上不误判）。

注：本测试只能抓"未配置"类坏死；"已配置但上游停用"（如 OpenRouter 把
free 档下线返回 404）静态测不出来，那类要靠 canary/实跑信号。

执行者不得修改本文件（验收测试已冻结）。
"""
import unittest
from pathlib import Path

import yaml

CONFIG = (Path(__file__).resolve().parent.parent.parent
          / ".harness" / "dispatch.yaml")
SETTINGS = Path.home() / ".dsh" / "settings.yaml"


def load():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def known_models():
    """{provider: {model_id, ...}}；无 dsh settings 时返回 None。"""
    if not SETTINGS.is_file():
        return None
    doc = yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {}
    providers = ((doc.get("llm-pi-ai") or {}).get("providers")) or {}
    out = {}
    for name, conf in providers.items():
        ids = set()
        for m in (conf or {}).get("models") or []:
            if isinstance(m, dict) and m.get("id"):
                ids.add(str(m["id"]))
        out[str(name)] = ids
    return out


class TestDispatchConfig(unittest.TestCase):
    def test_primary_is_provider_model_form(self):
        m = load()["model"]
        self.assertIsInstance(m, str)
        self.assertEqual(m, m.strip())
        self.assertIn("/", m, "model 必须是 provider/model 形式")

    def test_fallbacks_are_non_empty_strings(self):
        fbs = load().get("model_fallbacks") or []
        self.assertTrue(fbs, "model_fallbacks 不应为空（升级链需要备选）")
        for f in fbs:
            self.assertIsInstance(f, str)
            self.assertEqual(f, f.strip())
            self.assertIn("/", f)

    def test_fallbacks_do_not_include_primary(self):
        cfg = load()
        self.assertNotIn(
            cfg["model"], cfg.get("model_fallbacks") or [],
            "fallback 链不得包含 primary 自身（会退化成自回退）")

    def test_fallbacks_unique(self):
        fbs = load().get("model_fallbacks") or []
        self.assertEqual(len(fbs), len(set(fbs)), "fallback 链存在重复条目")

    def test_all_model_refs_resolvable(self):
        km = known_models()
        if km is None:
            self.skipTest("no ~/.dsh/settings.yaml in this environment")
        cfg = load()
        refs = [cfg["model"], *(cfg.get("model_fallbacks") or [])]
        for ref in refs:
            provider, _, model = ref.partition("/")
            self.assertIn(provider, km, "未知 provider（缺前缀或拼错）: %s" % ref)
            self.assertIn(model, km[provider],
                          "provider %s 未配置该 model: %s" % (provider, ref))


if __name__ == "__main__":
    unittest.main()