# F5 命令对账证据（2026-10-05）

- 冻结口径：`python -m unittest discover -s .harness/tests -t .harness`
- 实测：Ran 247 tests，failures=1
- 唯一失败：`test_gen_task_cards_integrity...test_generated_card_has_no_allow_deny_overlap`（基线即存在，与本次修订无关，见 T0 基线 235 跑 1 败）
- 新增 12 例（归属身份 4、主树门禁 4、本地范围 4）全部通过
- 结论：云端任务已收敛到冻结口径；旧 `-t .harness/tests` 写法作废
