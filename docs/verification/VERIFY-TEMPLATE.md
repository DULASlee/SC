# VERIFY-TEMPLATE

> **用途**：人类架构师验收记录模板。由 `.harness/scripts/verify-all.py` 自动生成。
> **不要手写**——运行 `python .harness/scripts/verify-all.py --task-id TASK-XXX --operator your-name` 即可。

---

# VERIFY-TASK-XXX-<timestamp>

- 验收人：<architect-name>
- 时间：<ISO 8601>
- Git SHA：`<sha>`
- Git 分支：`<branch>`
- 工作区脏：<bool>

## 门禁结果

### 1. 任务卡校验

命令：`python .harness/scripts/validate-task-card.py --all`
退出码：`0`
结果：✅ 通过

### 2. 契约一致性

命令：`python scripts/check-contract-consistency.py`
退出码：`0`
结果：✅ 通过

### 3. 编译 + 警告即错误

命令：`dotnet build -c Release /p:TreatWarningsAsErrors=true --nologo -v quiet`
退出码：`0`
结果：✅ 通过

### 4. 架构测试（条件）

（脚本自动判断 ArchitectureTests 是否存在）

### 5. 可靠性工具链（条件）

（脚本自动判断 ReliabilityTests + Docker daemon 是否可用）

### 6. 全测试

命令：`dotnet test -c Release --no-build --nologo -v quiet`
退出码：`0`
结果：✅ 通过

## 验收结论

✅ **通过**。任务可标记为 done。

## 原始证据

（本节由脚本自动填充，包含所有门禁命令的原始 stdout/stderr 尾部 3000 字符）
