# Eval Cases

每个 case 在隔离仓库快照中运行，baseline 与 candidate 使用相同输入。

| ID | 入口 | 场景 | 必须满足 |
|----|------|------|----------|
| PLAN-01 | harness-plan | 明确的小型变更 | XML 可解析；范围和验收标准完整 |
| PLAN-02 | harness-plan | 需求同时包含本次范围、交互依赖和未来能力 | 只把确认项写入 feature；其余进入依赖或 out-of-scope |
| PLAN-03 | harness-plan | 缺少会改变方案的关键条件 | 一次只问一个关键问题，不自行补全 |
| PLAN-04 | harness-plan | 事务、幂等、权限和未就绪外部依赖 | 约束与依赖状态准确进入 plan |
| FAST-01 | harness-backend-fast | 局部校验 bugfix | 只改相关代码；相关测试通过；CodeReview 覆盖本轮 commit |
| FULL-01 | harness-backend | 跨模块多阶段状态流转 | scope 映射完整；QA/CodeReview 双门禁；CallChain 为 UPDATED |
| REVIEW-01 | harness-backend | 预埋 stub、遗漏副作用、入口层业务逻辑和缺失测试 | P0/P1 召回不低于 baseline |
| REVIEW-02 | harness-backend | 工作区包含用户无关改动 | Builder 不提交、Reviewer 不阻断无关改动 |
| CHAIN-01 | harness-backend | 简单查询或同步 CRUD | CallChain 为 NOOP |
| RECOVERY-01 | harness-backend | Agent 中断或 artifact 缺失 | 从磁盘状态恢复；超过限制进入 PAUSED |
| PREFLIGHT-01 | harness-backend | 主编译失败 | 不启动 Agent，run 记录失败摘要 |
| PREFLIGHT-02 | harness-backend | 测试编译存在基线失败 | 询问用户；允许继续时 Reviewer 不误判为本轮回归 |

## Seeded Review Defects

`REVIEW-01` 至少放入以下四类缺陷：

- 返回硬编码成功结果但没有真实持久化。
- 成功响应后缺少 plan 要求的状态或事件副作用。
- Controller、RPC、MQ 或 Scheduler 入口包含业务分支。
- Service public 契约缺少关键正常或异常测试。

评估报告必须逐项记录发现证据，不能只记录最终 APPROVED/REJECTED。
