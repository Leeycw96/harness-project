# Keel Eval Rubric

## Hard Gates

任一项失败即判 candidate 退化：

- Plan XML 全部可解析。
- Plan XML 必须且仅能关联一份存在的 Markdown 代码改造计划。
- 未确认内容不进入本次 feature。
- 两份计划不得包含 `TBD`、未决关键选型或交给 Builder 的关键决策。
- 代码改造计划必须描述 Current Flow、Target Flow、路径级 Change Map、接口与数据、技术决策、适用的横切约束、实施顺序、验证和恢复。
- 涉及外部技术调研时必须先获得用户同意；拒绝调研且未选择或授权代选时暂停。
- Codex Dev 不得生成或消费 build-scope artifact，Preflight 后直接构建。
- Builder 结果可编译，相关测试通过，不存在 stub/fake。
- 预埋 P0/P1 的召回率不低于 baseline。
- QA 只审 Builder commit diff。
- CallChain 正负样本判定不低于 baseline。
- CallChain shadow/受控评测不得出现 `prefilter=noop`、Agent `UPDATED` 的漏判。
- 中断后可恢复，超过重试上限可暂停并报告原因。

## 评分项

每项 0–2 分：

| 维度 | 0 | 1 | 2 |
|------|---|---|---|
| 边界 | 越界或漏掉核心范围 | 有轻微歧义 | 范围、依赖、out-of-scope 清晰 |
| 验收 | 模糊且不可执行 | 部分可执行 | 动作、响应、副作用和异常完整 |
| 计划 | 目标流程或修改边界缺失 | 仅有高层方向 | 现状、目标流程、路径级改造契约和关键决策完整 |
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
