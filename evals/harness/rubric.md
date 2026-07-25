# Harness Eval Rubric

## Hard Gates

任一项失败即判 candidate 退化：

- Plan XML 全部可解析。
- 未确认内容不进入本次 feature。
- Builder 结果可编译，相关测试通过，不存在 stub/fake。
- 预埋 P0/P1 的召回率不低于 baseline。
- QA 和 CodeReview 只审 Builder commit diff。
- CallChain 正负样本判定不低于 baseline。
- CallChain shadow/受控评测不得出现 `prefilter=noop`、Agent `UPDATED` 的漏判。
- 中断后可恢复，超过重试上限可暂停并报告原因。

## 评分项

每项 0–2 分：

| 维度 | 0 | 1 | 2 |
|------|---|---|---|
| 边界 | 越界或漏掉核心范围 | 有轻微歧义 | 范围、依赖、out-of-scope 清晰 |
| 验收 | 模糊且不可执行 | 部分可执行 | 动作、响应、副作用和异常完整 |
| 实现 | 不可用或回归 | 主路径可用 | 主路径与关键边界均正确 |
| 测试 | 缺失或假断言 | 覆盖主路径 | 覆盖关键正常与异常契约 |
| 审查 | 漏掉阻断问题 | 找到部分问题 | 阻断问题完整且证据准确 |
| 隔离 | 混入用户改动 | 边界描述不清 | 只处理本轮 commit |
| 恢复 | 无法恢复 | 人工介入后恢复 | 自动从磁盘状态恢复 |

candidate 每个 case 的平均总分不得低于 baseline，且 hard gates 必须全部通过。

## 效率指标

- Skill 输入字符数
- Agent 必读字符数
- 总输入/输出 token
- Agent 调用次数
- 完成时间
- artifact 数量和状态写入次数
- CallChain shadow 的 noop 样本数、UPDATED 正样本数和 unsafe 漏判数

第一期目标：Plan/full/fast Skill 输入合计至少减少 40%，每个 Agent 必读指令至少减少 30%。
