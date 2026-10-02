---
name: keel-dev
description: 执行已确认计划，编排实现、QA 验收与返修，并按实际改动维护业务流程索引。
user-invocable: true
---

# Keel Dev

流程：初始化与前置检查 → 实现 → QA 验收（必要时返修）→ 判断并维护流程索引 → 交付。
主会话负责调度与阶段推进；各 Agent 依据任务和 Spec 自主完成本职工作。

## 角色与规范

下表为默认绑定，均附项目 AGENTS.md（缺失用 README.md）。A/S 可替换；主会话核对能力与引用，并在 `state.json.aso_bindings` 按 builder/qa/call_chain 记录 agent、spec_refs、task_ref。

| 工作 | 默认 Agent | Spec | 任务步骤 |
| --- | --- | --- | --- |
| 实现 | keel-builder | .codex/common/refs/keel-dev-spec.md | .agents/skills/keel-dev/SKILL.md#实现 |
| 验收 | keel-qa | .codex/common/refs/keel-qa-spec.md | .agents/skills/keel-dev/SKILL.md#验收 |
| 流程维护 | keel-call-chain | .codex/common/refs/keel-call-chain-spec.md | .agents/skills/keel-dev/SKILL.md#流程维护 |

QA 另给 `.codex/common/refs/keel-dev-spec.md#代码与测试标准`；CallChain 另给 `.codex/common/refs/keel-business-flow-spec.md`。替换 Spec 时同步这些引用。

## 初始化

主会话接收已确认的计划索引。新任务在项目根 source `.codex/common/scripts/keel-init.sh`，将索引绝对路径设为 KEEL_PLAN_PATH，用当前分支和 get_next_run_number 选择 `.keel/iterations/<branch>/run-N`，设为 KEEL_OUTPUT_DIR；仅用户要求时创建分支。

```bash
KEEL_PROFILE=$(init_keel_run "$KEEL_OUTPUT_DIR" "$KEEL_PLAN_PATH")
export KEEL_PROFILE
```

初始化校验并快照索引与功能文档。缺失、旧格式或关键设计未决时交回 Plan；已有 run 按下文恢复。

主会话按项目配置完成前置检查并记录工作目录、命令与结果：main_compile 为适用的构建、类型/语法或启动检查，失败暂停；test_compile 为测试准备，无独立准备记 not-applicable，无法执行不等于不适用。既有准备失败须用户明确允许才记 failed_allowed，仍须验证本次改动。准备完成进入 BUILD。

## 实现

主会话按实现绑定调度 `keel-builder`，给开发 Spec、run 内计划、当前功能范围；请其完成实现、相关验证和聚焦提交，返回新 commits 与证据。小任务一次完成，确有依赖或隔离需要时按功能分片。

| 阶段 | 本步任务 | 完成标记与产物 |
| --- | --- | --- |
| BUILD | 实现当前功能，最后一片完成整体相关验证 | BUILD_SLICE_DONE；最后一片 BUILD_DONE；产物 plan.md |
| FIX | 按 QA 的 fix-brief.md 修复阻断项及受影响行为 | FIX_DONE；产物 fix-brief.md |

主会话核对结果并记录本轮新 commits。全部实现完成进入 REVIEW，返修完成进入 REVIEW_FIX；发现计划矛盾或需要改变已确认设计时暂停并交回 Plan。

## 验收

主会话按验收绑定调度新的 `keel-qa`，给 QA Spec、开发质量标准、计划及本轮 Builder commits。请其独立验证功能与实现，按 Spec 写 qa-feedback.md，返回 APPROVED 或 REJECTED。

REVIEW 覆盖全部功能；REVIEW_FIX 覆盖阻断项与受影响场景。通过后进入流程维护判定；未通过则由主会话将阻断项整理为 fix-brief.md，返回实现步骤的 FIX，再安排新 QA 复验。最多三轮返修，仍阻断则 PAUSED。

## 流程维护

QA 通过后，主会话检查最终 Builder diff，按 CallChain Spec 判断是否需要调度：明确无外部入口、异步推进点、业务状态节点、流转条件或状态变更符号变化时为 noop，有变化或不确定为 run。

调用 `record_call_chain_prefilter "<noop|run>" "<判定证据>"`。on-demand 的 noop 调用 record_call_chain_skip 后直接交付；run 调度 `keel-call-chain`，给 CallChain Spec、共用业务流程 Spec、索引目录、最终 commits 和相关计划，请其核实并维护受影响流程，返回 call-chain-review.md。

- CALL_CHAIN_NOOP：主会话调用 `record_call_chain_result noop`。
- CALL_CHAIN_UPDATED：核对独立的流程文档 commit，调用 `record_call_chain_result updated "<commit-sha>"`。

恢复旧 shadow 模式时始终调度 CallChain，Agent 独立判断且不读取预判结果；主会话改用 `record_call_chain_shadow_result "<noop|updated>"` 并记录对应文档结果。

## 交付

主会话报告实现 commits、QA 验证摘要、流程维护结论及产物。DONE 后的新反馈另开任务，范围或设计变化交回 `/keel-plan`。

## 运行衔接

每次使用原生 subagent；默认角色与 Spec 来自本 Skill 的绑定，具体方法由 Agent 自主选择。主会话下发任务、Spec、项目与产物路径、功能范围和所需 commits，以及 KEEL_PROFILE、stage、artifact、tag、reporter；同时给本步 task_ref 与 `.agents/skills/keel-dev/SKILL.md#运行衔接`。引用转绝对路径，带 `#二级标题` 时只读取该节及子节。

执行依据为快照索引和当前功能及其明确引用章节。Agent 导出 KEEL_PROFILE，source `.codex/common/scripts/keel-common.sh`，用 `update_progress "<reporter>" "<stage>" "<摘要>" "<artifact>"` 报告进展，用 `complete_stage "<reporter>" "<tag>" "<摘要>" "<artifact>"` 报告完成。reporter 沿用 keel-builder / keel-qa / keel-call-chain；Agent 返回结果，主会话核对产物、tag 与 commit 后推进 state。

恢复时先结束旧执行，运行 `resume_keel_run "$KEEL_PROFILE"` 并采用返回路径（兼容旧 profile）；保留提交、进度与返修计数。旧默认 task_ref 重绑到本 Skill 对应步骤，自定义 A/S 沿用。审查五分钟、实现或返修十五分钟无进展时检查，每阶段每角色最多恢复两次；产物错误定向补做一次，再失败计入恢复次数。已完成 run 不重开，超限或关键资料缺失则暂停并报告。
