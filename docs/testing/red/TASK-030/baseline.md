# TASK-030 baseline（改动前证据）

### docs/ai-workspace/hooks/pre-push

- L2 [注释/文档] 非ASCII=['全', '前', '必', '推', '禁', '过', '送', '通', '部', '重', '量', '门', '须', '：'] :: # 重量门禁：推送前必须全部通过
- L3 [注释/文档] 非ASCII=['§', '一', '师', '方', '构', '架', '案', '（', '）'] :: # 架构师 §一 方案 1（pre-push hook）
- L12 [输出] 非ASCII=['禁', '门'] :: echo "=== pre-push 门禁 ==="
- L14 [注释/文档] 非ASCII=['个', '为', '人', '决', '分', '则', '制', '助', '发', '取', '定', '师', '开', '式', '强', '支', '改', '构', '架', '模', '流', '消', '程', '规', '辅', '（', '）', '，', '：'] :: # 0. 分支规则（架构师决定：取消 PR 强制流程，改为个人 + AI 辅助开发模式）
- L15 [注释/文档] 非ASCII=['。', '不', '仍', '保', '再', '后', '推', '构', '架', '次', '止', '每', '测', '由', '的', '直', '禁', '编', '译', '试', '质', '量', '障', '（', '）', '，'] :: #    不再禁止直推 main/develop。质量仍由每次 push 后的 CI 保障（编译/测试/架构），
- L16 [注释/文档] 非ASCII=['。', '为', '仅', '做', '录', '提', '收', '断', '止', '灯', '的', '示', '红', '而', '记', '醒', '阻', '非', '验'] :: #    红灯为"提醒"而非"阻止 push"。feat/*|fix/* 仅做非阻断的验收记录提示。
- L17 [输出] 非ASCII=['参', '名', '数', '是', '第', '（', '）'] :: remote="$1"  # pre-push hook 第 1 参数是 remote 名（origin）
- L23 [输出] 非ASCII=['不', '为', '交', '付', '任', '到', '务', '可', '归', '录', '推', '收', '断', '档', '若', '记', '送', '阻', '验', '（', '）', '，', '：'] :: info "推送到 $branch：若为任务交付，验收记录可归档到 .harness/tasks/（不阻断）"
- L29 [注释/文档] 非ASCII=['个', '仓', '全', '工', '库', '无', '测', '程', '试', '逐', '（', '）', '，'] :: # 1. 全测试（仓库无 .sln，逐个工程）
- L37 [输出] 非ASCII=['全', '失', '测', '试', '败', '：'] :: dotnet test "${args[@]}" || fail "全测试失败：$proj"
- L40 [注释/文档] 非ASCII=['分', '在', '如', '存', '差', '本', '果', '率', '盖', '脚', '覆', '（', '）'] :: # 2. 覆盖率差分（如果存在脚本）
- L42 [输出] 非ASCII=['分', '察', '差', '期', '未', '率', '盖', '覆', '观', '过', '通', '（', '）'] :: bash scripts/check-coverage-diff.sh || warn "覆盖率差分未通过（观察期）"
- L44 [输出] 非ASCII=['不', '启', '在', '存', '未', '本', '段', '用', '脚', '跳', '过', '阶', '（', '）', '，'] :: info "coverage-diff 脚本不存在，跳过（L2-B partial 阶段未启用）"
- L47 [注释/文档] 非ASCII=['变', '在', '如', '存', '异', '果', '测', '置', '试', '配', '（', '）'] :: # 3. 变异测试（如果配置存在）
- L49 [输出] 非ASCII=['为', '变', '察', '异', '断', '期', '段', '测', '观', '试', '跳', '过', '阶', '阻', '（', '）', '，'] :: info "变异测试为观察期，跳过阻断（L2-B 阶段，break=15）"
- L51 [输出] 非ASCII=['不', '变', '在', '存', '异', '测', '试', '跳', '过', '，'] :: info "stryker-config.json 不存在，跳过变异测试"
- L54 [注释/文档] 非ASCII=['仅', '具', '可', '在', '工', '性', '时', '用', '跑', '链', '靠', '（', '）'] :: # 4. 可靠性工具链（仅在 Docker daemon 可用时跑）
- L56 [输出] 非ASCII=['具', '到', '可', '工', '性', '检', '测', '行', '运', '链', '靠', '，'] :: info "检测到 Docker daemon，运行可靠性工具链"
- L58 [输出] 非ASCII=['具', '可', '察', '工', '性', '期', '未', '观', '过', '通', '链', '靠', '（', '）'] :: || warn "可靠性工具链未通过（观察期）"
- L60 [输出] 非ASCII=['§', '五', '允', '地', '师', '无', '本', '构', '架', '级', '许', '跳', '过', '降', '（', '）', '，'] :: info "本地无 Docker daemon，跳过 ReliabilityTests（架构师 §五 允许降级）"
- L63 [输出] 非ASCII=['全', '过', '通', '部'] :: ok "pre-push 全部通过"

（该文件非 ASCII 行共 21 行）

### .harness/scripts/validate-task-card.py

- L3 [注释/文档] 非ASCII=['任', '务', '卡', '器', '校', '验'] :: L3 任务卡校验器
- L5 [注释/文档] 非ASCII=['法', '用', '：'] :: 用法：
- L7 [注释/文档] 非ASCII=['任', '务', '卡', '所', '有', '校', '验'] :: python .harness/scripts/validate-task-card.py --all   # 校验所有 active 任务卡
- L9 [注释/文档] 非ASCII=['出', '码', '退', '：'] :: 退出码：
- L10 [注释/文档] 非ASCII=['过', '通'] :: 0 - 通过
- L11 [注释/文档] 非ASCII=['失', '校', '败', '验'] :: 1 - 校验失败
- L12 [注释/文档] 非ASCII=['参', '数', '误', '错'] :: 2 - 参数错误
- L23 [注释/文档] 非ASCII=['α', '—', '免', '制', '强', '录', '收', '码', '翻', '解', '认', '记', '车', '过', '避', '验', '默', '（', '）'] :: # 强制 UTF-8（避免 Windows GBK 默认解码翻车——L1-α 验收记录过）
- L40 [注释/文档] 非ASCII=['失', '析', '解', '败', '：'] :: return [f"YAML 解析失败：{e}"]
- L42 [注释/文档] 非ASCII=['串', '会', '字', '对', '成', '把', '析', '符', '解', '认', '象', '默'] :: # PyYAML 默认会把 ISO 8601 字符串解析成 datetime 对象
- L43 [注释/文档] 非ASCII=['为', '了', '望', '期', '校', '让', '过', '通', '验', '（', '）', '，'] :: # 为了让 Schema 校验（json schema 期望 string）通过，
- L44 [注释/文档] 非ASCII=['→', '一', '次', '这', '里', '（', '）'] :: # 这里 round-trip 一次 json dump（datetime → string）
- L48 [注释/文档] 非ASCII=['内', '列', '化', '可', '型', '容', '常', '序', '异', '无', '法', '类', '能', '（', '）', '：'] :: errors.append(f"YAML 内容无法 JSON 序列化（可能类型异常）：{e}")
- L51 [注释/文档] 非ASCII=['校', '验'] :: # 1. Schema 校验
- L55 [注释/文档] 非ASCII=['失', '径', '校', '败', '路', '验', '（', '）', '：'] :: errors.append(f"Schema 校验失败：{e.message}（路径：{list(e.absolute_path)}）")
- L58 [注释/文档] 非ASCII=['业', '则', '务', '外', '规', '额'] :: # 2. 额外业务规则
- L59 [注释/文档] 非ASCII=['可', '式', '时', '析', '格', '解', '间'] :: # 2.1 时间格式可解析
- L63 [注释/文档] 非ASCII=['式', '时', '格', '误', '错', '间', '：'] :: errors.append(f"created 时间格式错误：{card['created']}")
- L65 [注释/文档] 非ASCII=['不', '于', '全', '写', '包', '可', '含', '完', '径', '必', '留', '能', '路', '须', '（', '）'] :: # 2.2 allow_write 不能完全包含于 deny_write（必须留可写路径）
- L69 [注释/文档] 非ASCII=['于', '任', '何', '全', '写', '包', '可', '含', '完', '径', '无', '路', '，'] :: errors.append("allow_write 完全包含于 deny_write，无任何可写路径")
- L71 [注释/文档] 非ASCII=['下', '在', '工', '录', '必', '测', '目', '程', '落', '试', '须'] :: # 2.3 acceptance_tests 必须落在测试工程目录下
- L72 [注释/文档] 非ASCII=['名', '如', '局', '工', '布', '是', '本', '测', '目', '程', '试', '适', '配', '项', '（', '）', '，', '：'] :: # 适配本项目布局：测试工程名是 *.Tests/（如 GenCollector.Tests/），
- L73 [注释/文档] 非ASCII=['。', '不', '中', '则', '原', '始', '宽', '师', '式', '录', '放', '是', '构', '架', '目', '而', '规', '集', '需'] :: # 而不是集中式 tests/ 目录。架构师原始规则需放宽。
- L76 [注释/文档] 非ASCII=['以', '内', '在', '头', '工', '开', '必', '或', '程', '落', '须', '：'] :: errors.append(f"acceptance_tests 必须以 tests/ 开头或落在 *.Tests/ 工程内：{t}")
- L78 [注释/文档] 非ASCII=['不', '义', '定', '有', '未', '的', '能', '里'] :: # 2.4 done_when 里不能有未定义的 gate
- L87 [注释/文档] 非ASCII=['引', '未', '用', '知', '：'] :: errors.append(f"done_when 引用未知 gate：{gate}")
- L97 [输出] 非ASCII=['下', '任', '务', '卡', '有', '没'] :: print("[WARN] .harness/tasks/active/ 下没有任务卡")
- L117 [输出] 非ASCII=['个', '共', '误', '错'] :: print(f"\n共 {total_errors} 个错误")
- L119 [输出] 非ASCII=['任', '务', '卡', '所', '有', '校', '过', '通', '验'] :: print("\n所有任务卡校验通过")

（该文件非 ASCII 行共 29 行）

### scripts/check-contract-consistency.py

- L3 [注释/文档] 非ASCII=['α', '—', '。', '一', '契', '小', '性', '最', '架', '校', '约', '致', '验', '骨'] :: L1-α 契约一致性校验 — 最小骨架。
- L5 [注释/文档] 非ASCII=['个', '仅', '围', '校', '范', '验', '（', '）', '：'] :: 校验范围（仅 1 个 schema 1 个 openapi）：
- L6 [注释/文档] 非ASCII=['合', '是', '法'] :: 1. contracts/schemas/*.json 是合法 JSON
- L7 [注释/文档] 非ASCII=['合', '是', '法'] :: 2. contracts/openapi.yaml 是合法 YAML
- L8 [注释/文档] 非ASCII=['中', '件', '到', '子', '对', '应', '径', '所', '文', '有', '析', '能', '解', '路', '都'] :: 3. openapi.yaml 中所有 $ref 都能解析到对应文件 + 子路径
- L9 [注释/文档] 非ASCII=['个', '到', '后', '字', '少', '找', '析', '止', '段', '空', '能', '至', '解', '防', '（', '）'] :: 4. $ref 解析后能找到至少 1 个 required 字段（防止空 schema）
- L11 [注释/文档] 非ASCII=['出', '码', '退', '：'] :: 退出码：
- L12 [注释/文档] 非ASCII=['过', '通'] :: 0 - 通过
- L13 [注释/文档] 非ASCII=['一', '不', '致'] :: 1 - 不一致
- L14 [注释/文档] 非ASCII=['件', '失', '式', '文', '格', '缺', '误', '错'] :: 2 - 文件缺失/格式错误
- L16 [注释/文档] 非ASCII=['α', 'β', '不', '围', '在', '留', '给', '范', '（', '）', '：'] :: 不在 L1-α 范围（留给 L1-β）：
- L17 [注释/文档] 非ASCII=['图', '派', '生', '视'] :: - AsyncAPI / MQTT topics / data-models 派生视图
- L18 [注释/文档] 非ASCII=['一', '名', '契', '字', '性', '校', '段', '约', '致', '跨', '验'] :: - 跨契约字段名一致性校验
- L19 [注释/文档] 非ASCII=['字', '对', '校', '段', '验', '齐'] :: - required 字段对齐校验
- L29 [注释/文档] 非ASCII=['—', '免', '制', '告', '强', '报', '翻', '见', '认', '车', '避', '默', '（', '）'] :: # 强制 UTF-8（避免 Windows 默认 GBK 翻车 — 见 L0 报告 .editorconfig UTF-8）
- L42 [注释/文档] 非ASCII=['。', '式', '形', '析', '解'] :: """解析 $ref: './schemas/xxx.json#/properties' 形式。"""
- L49 [注释/文档] 非ASCII=['不', '件', '在', '存', '文'] :: return None, f"$ref 文件不存在: {target}"
- L60 [注释/文档] 非ASCII=['合', '法'] :: # 1. JSON schemas 合法
- L68 [注释/文档] 非ASCII=['—', '法', '非'] :: errors.append(f"JSON 非法: {p.name} — {e}")
- L70 [注释/文档] 非ASCII=['可', '合', '析', '法', '解'] :: # 2. openapi.yaml 合法 + $ref 可解析
- L73 [输出] 非ASCII=['❌', '不', '在', '存'] :: print(f"❌ {openapi_path} 不存在"); return 2
- L99 [注释/文档] 非ASCII=['—'] :: #    If someone renames these fields, the test FAILS — proving the mechanism bites.

（该文件非 ASCII 行共 22 行）

## run: validate-task-card.py --all（改前）
exit=0
```
[OK]   TASK-001.yaml
[OK]   TASK-008.yaml
[OK]   TASK-009.yaml
[OK]   TASK-010.yaml
[OK]   TASK-011.yaml
[OK]   TASK-012.yaml
[OK]   TASK-013.yaml
[OK]   TASK-014.yaml
[OK]   TASK-017.yaml
[OK]   TASK-018.yaml
[OK]   TASK-019.yaml
[OK]   TASK-020.yaml
[OK]   TASK-021-base-url-domain-error.yaml
[OK]   TASK-022-harness-scripts-cover.yaml
[OK]   TASK-023.yaml
[OK]   TASK-024.yaml
[OK]   TASK-029.yaml
[OK]   TASK-030.yaml
[OK]   TASK-031.yaml

所有任务卡校验通过
```

## run: validate-task-card.py 裸运行（print(__doc__)，改前）
exit=2
```
L3 任务卡校验器

用法：
  python .harness/scripts/validate-task-card.py <path-to-task-card.yaml>
  python .harness/scripts/validate-task-card.py --all   # 校验所有 active 任务卡

退出码：
  0 - 通过
  1 - 校验失败
  2 - 参数错误
```

## run: check-contract-consistency.py（改前）
exit=0
```
[OK] L1-alpha check passed: all $ref resolvable, all schemas non-empty.
```

## 故意违规 a：validate-task-card 坏卡（改前）
exit=1
```
[FAIL] bad-card.yaml
       - Schema 校验失败：'scope' is a required property（路径：[]）

共 1 个错误
```
判定：拦截生效

## 故意违规 b：check-contract-consistency 注入非法 JSON（改前）
exit=1（注入文件 zz-030-evidence.json 已删，git status 无残留）
```
[FAIL] L1-alpha check failed (1 error(s)):
  - JSON 非法: zz-030-evidence.json — Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
```
判定：拦截生效

## 故意违规 c：pre-push dotnet stub 强制失败（改前）
exit=1
```
=== pre-push 门禁 ===
stub: forced fail
[FAIL] 全测试失败：tests/GenCollector.Tests/GenCollector.Tests.csproj
```
判定：拦截生效
