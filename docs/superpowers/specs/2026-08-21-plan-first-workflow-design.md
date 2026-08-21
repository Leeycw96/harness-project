# Harness Plan 重计划工作流设计

## 背景与目标

当前 Codex App runtime 将需求范围和验收标准放在 Harness Plan，再由 Harness Backend 的 Builder 生成 `build-scope.md` 并由 QA 执行 `SCOPE_REVIEW`。这让“scope”同时出现在需求确认和实现准备阶段，用户无法在实现前完整确认改造后的业务流程和代码方案。

本次只修改 Codex App runtime。目标是把方案决策前移到 Harness Plan：Plan 阶段完成现状理解、必要的技术调研、目标流程、代码修改地图和用户确认；Backend 删除 build-scope 阶段，只负责 Builder 实现和 QA 验收。Claude Code runtime 保持原样，不考虑旧 Codex run 兼容。

## 设计依据

OpenAI 的 [ExecPlan 指南](https://developers.openai.com/cookbook/articles/codex_exec_plans)要求执行计划自包含，明确代码位置、接口依赖、实施步骤、验证命令和可观察结果。MADR 的[决策模板](https://github.com/adr/madr/blob/develop/template/adr-template.md)使用决策驱动因素、候选方案、选择理由、后果和确认方式记录技术选型。

Harness 不直接复制完整 ExecPlan。执行进度已由 Backend `state.json` 管理，因此新增修改方案是用户批准的稳定实现契约，不包含 `Progress`、`Surprises` 或运行日志，也不由 Backend 在实现过程中自行改写。

## Plan 产物

Harness Plan 固定产出两个关联文件：

1. `.harness/plans/<name>.md`：XML 需求契约，保留 context、features、acceptance criteria、out-of-scope、constraints 和 dependencies，并新增 `<implementation-plan path=".harness/plans/<name>-implementation.md" />`。
2. `.harness/plans/<name>-implementation.md`：面向用户、Builder 和 QA 的 Markdown 修改方案。

XML 模板不得预设 JWT、Session 或其他具体技术选择，避免示例替用户做决定。

修改方案包含以下必需章节：

- `Purpose`：改造目标和用户可见结果。
- `Current Flow`：根据相关 CallChain 和代码还原入口、状态、外部调用及副作用。
- `Target Flow`：改造后的触发、判断、状态变化、异常分支和终态。
- `Change Map`：按 feature 映射仓库相对路径、模块、已有公共类或接口及职责变化。
- `Interfaces and Data`：API、RPC、消息、表结构、状态字段和兼容或迁移要求。
- `Technical Decisions`：候选方案、决策驱动因素、选择、理由、影响和调研来源；无新选型时明确记录沿用的项目惯例。
- `Cross-cutting Constraints`：只在需求涉及时记录事务、一致性、幂等、并发、权限、安全和错误处理。
- `Implementation Sequence`：Builder 应遵循的可独立验证批次及依赖顺序。
- `Validation`：测试命令、业务场景和预期结果。
- `Risks and Recovery`：实现、迁移、重试和回滚风险。

修改方案细化到“实现契约级”：决定所有影响用户结果、跨模块协作或难以回滚的内容。私有辅助方法、方法体、行级修改、不改变契约的局部重构，以及没有实际必要的设计模式由 Builder 决定。设计模式只有在它本身是技术选型，或会改变模块边界、扩展方式或事务语义时才进入方案。

## CallChain 与现状理解

Harness Plan 必须读取与需求相关的 `.harness/call-chain/*.md`，用它定位现有外部入口、异步推进点和生命周期状态，再检查对应代码、数据模型和测试。CallChain 是流程索引而非唯一事实来源；缺失、过期或与代码不一致时，以代码为准，并在 `Current Flow` 中记录依据。Plan 阶段不修改 CallChain。

## Plan 交互与调研

流程顺序为：

1. 读取项目手册、相关代码、数据模型、测试和 CallChain。
2. 确认本次范围、交互依赖、out-of-scope 和 feature 清单。
3. 确认每个 feature 的可测试验收标准。
4. 识别会改变目标流程或实现边界的技术决策。
5. 完成所有技术选择。
6. 起草并让用户确认 Current Flow、Target Flow 和 Change Map。
7. 完成其余修改方案章节并进行最终确认。
8. 写入两个关联产物。

项目内调研始终执行，不额外询问。外部调研只在项目没有既定方案、且选择会影响安全、数据、接口、事务、部署或长期维护时提出，并必须先获得用户同意。

用户同意调研后，Harness Plan 使用官方或一手来源比较 2–3 个适合当前项目的方案，至少覆盖项目适配性、安全、运维、迁移和测试，并给出推荐供用户选择。用户拒绝调研且没有指定方案时必须暂停，直到用户明确选择或明确授权 Harness 代选。即使获得代选授权，推荐与理由仍须由用户确认。

最终产物不得包含 `TBD`、未决选型或“Builder 自行决定”的关键决策。一次只询问一个会改变方案的问题；项目已有明确惯例时说明并沿用，不制造无意义选择。

## Backend 状态机

Codex full 流程改为：

```text
Preflight -> BUILD -> REVIEW(QA)
  -> REJECTED: FIX -> REVIEW_FIX(QA)
  -> APPROVED: CALL_CHAIN_PREFILTER -> CALL_CHAIN/DONE
```

Codex fast 保持 Builder + QA 的现有结构，但同样消费两个 Plan 产物。

Backend 启动时读取 XML 中的 implementation plan 路径，确认两个文件存在且不含未决项，再分别复制为 run 内的 `plan.md` 和 `implementation-plan.md`。初始化函数记录两个路径并直接进入 `BUILD` 或 `BUILD_FAST`。

`SCOPE_BUILD`、`SCOPE_REVIEW`、`build-scope.md`、`scope-review.md`、scope attempts 及相关 Agent tag 从 Codex runtime 完整删除。缺少 implementation plan 时停止并要求重新运行 Harness Plan，不做旧 run 迁移。

## Agent 职责

Builder 同时读取需求契约和修改方案。full 按 `Implementation Sequence` 分批实现，fast 尽量单批完成。Builder 可以决定局部、可逆且不改变契约的编码细节；如果发现目标流程、接口、数据或技术决策无法执行，必须暂停，不能自行改变批准方案。

QA 同时读取两个文件，以 XML 验收标准判断需求是否满足，以 Markdown 修改方案判断 Target Flow、Change Map、接口与数据以及横切约束是否落实。QA 不再执行 Scope Review。

CallChain Agent 读取 implementation plan 和最终 Builder diff，根据实际实现维护流程索引，不再读取 build-scope。

## 状态与产物

full run 的新状态包含 `plan_path` 和 `implementation_plan_path`，artifact 保留 `qa_feedback`、`fix_brief` 和 `call_chain_review`。删除 `build_scope`、`scope_review`、`scope_attempt` 和 `limits.scope_attempts`。

fast run 同样记录两个 Plan 路径，继续使用 `qa_feedback` 和 `fix_brief`。两个模式都不生成 build-scope 相关文件。

## 文档、Eval 与校验

README 分开说明 Codex 的 plan-first 流程与保持不变的 Claude Code 流程。部署提示和 run 目录示例同步更新。

Plan eval 新增：

- 项目已有方案时沿用，不制造无意义选型。
- 用户同意外部调研时比较适用方案并记录来源。
- 用户拒绝调研且未授权代选时暂停。
- 相关 CallChain 被读取并用于 Current Flow。
- Target Flow、Change Map、接口/数据、横切约束和验证方案完整。
- 最终两个文件互相引用且没有未决项。

Backend eval 删除 scope 映射和 Scope Review 要求，改为验证 Builder 严格消费 implementation plan、QA 同时检查需求和修改方案。

Plan Skill 将因“重计划”目标增长，因此移除旧的 Plan 字符数 slimming 硬门槛，继续通过 metrics 观察规模。新增静态 planning-contract 检查，验证模板章节、XML 引用、新状态 JSON，以及 Codex 活跃 runtime 不再包含 build-scope 概念。runtime 分叉检查明确断言 Codex 已移除 build-scope，而 Claude Code 仍保留原流程。

最终验证包括 Shell 语法、XML 可解析性、Plan 合同、状态 JSON、slimming 剩余指标、CallChain 受控评测、临时部署 manifest、Codex build-scope 残留扫描，以及 `claude-code/` 无本次 diff。
