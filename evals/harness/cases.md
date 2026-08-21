# Eval Cases

每个 case 在隔离仓库快照中运行，baseline 与 candidate 使用相同输入。

| ID | 入口 | 场景 | 必须满足 |
|----|------|------|----------|
| PLAN-01 | harness-plan | 明确的小型变更 | XML 可解析且关联 Markdown；范围、验收标准和代码改造计划完整 |
| PLAN-02 | harness-plan | 需求同时包含本次范围、交互依赖和未来能力 | 只把确认项写入 feature；其余进入依赖或 out-of-scope |
| PLAN-03 | harness-plan | 缺少会改变方案的关键条件 | 一次只问一个关键问题，不自行补全 |
| PLAN-04 | harness-plan | 事务、幂等、权限和未就绪外部依赖 | 约束与依赖状态准确进入 plan |
| PLAN-05 | harness-plan | 现有复杂流程已有 CallChain | 先用 CallChain 定位入口和生命周期，再以代码和测试校正 Current Flow |
| PLAN-06 | harness-plan | 登录能力未指定 token 或 session，项目也无既定方案 | 先询问是否外部调研；同意后比较 2–3 个方案并等待用户选择；拒绝且未授权代选时暂停 |
| PLAN-07 | harness-plan | 跨模块业务流程改造 | Markdown 包含 Current/Target Flow、路径级 Change Map、接口与数据、技术决策、横切约束、实施顺序、验证和恢复 |
| PLAN-08 | harness-plan | 用户最终确认前仍有关键选型或 TBD | 不写文件，不把决策交给 Builder |
| FAST-01 | harness-backend-fast | 局部校验 bugfix | Builder 和 QA 消费两份计划；只改相关代码；相关测试通过；QA 覆盖本轮 commit |
| FULL-01 | harness-backend | 跨模块多阶段状态流转 | Preflight 后直接 BUILD；不存在 build-scope 阶段；QA 门禁通过；CallChain 为 UPDATED |
| REVIEW-01 | harness-backend | 预埋 stub、遗漏副作用、入口层业务逻辑和缺失测试 | P0/P1 召回不低于 baseline |
| REVIEW-02 | harness-backend | 工作区包含用户无关改动 | Builder 不提交、QA 不阻断无关改动 |
| CHAIN-01 | harness-backend | 简单查询或同步 CRUD | CallChain 为 NOOP |
| CHAIN-02 | harness-backend | shadow 主会话预判 NOOP、独立 Agent 判 UPDATED | 记录 `safe=false`，禁止启用真实跳过 |
| CHAIN-03 | harness-backend | shadow 主会话保守预判 RUN、独立 Agent 判 NOOP | 记录安全误报，不阻断准入 |
| RECOVERY-01 | harness-backend | Agent 中断或 artifact 缺失 | 从磁盘状态恢复；超过限制进入 PAUSED |
| PREFLIGHT-01 | harness-backend | 主编译失败 | 不启动 Agent，run 记录失败摘要 |
| PREFLIGHT-02 | harness-backend | 测试编译存在基线失败 | 询问用户；允许继续时 QA 不误判为本轮回归 |

## Seeded QA Defects

`REVIEW-01` 至少放入以下四类缺陷：

- 返回硬编码成功结果但没有真实持久化。
- 成功响应后缺少 plan 要求的状态或事件副作用。
- Controller、RPC、MQ 或 Scheduler 入口包含业务分支。
- Service public 契约缺少关键正常或异常测试。

评估报告必须逐项记录发现证据，不能只记录最终 APPROVED/REJECTED。
