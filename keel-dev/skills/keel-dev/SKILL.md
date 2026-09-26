---
name: keel-dev
description: 高风险后端改动的完整 subagent 验收流程，编排实现、QA 与业务流程维护。
user-invocable: true
---

# Keel Dev

用于复杂流程、迁移、权限、事务并发、外部集成或跨模块状态流转；日常小中型改动使用 `/keel-dev-fast`。

先读 `.codex/common/refs/keel-dev-orchestration.md#主会话编排`，按其中 A/S 绑定与任务协议调度。每阶段下发规范引用、通用任务要求、当前任务章节和完整参数，不能依赖角色内置 Keel 规则。不重复 Plan 的选型与确认。

## 初始化

按共享契约设置输入并运行：

```bash
KEEL_PROFILE=$(init_keel_run "$KEEL_OUTPUT_DIR" "$KEEL_PLAN_PATH")
export KEEL_PROFILE
```

保存有效 A/S 绑定。计划完整、无未决问题且 Preflight 通过后进入 BUILD；缺失或旧格式返回 Plan。

## 状态机

### BUILD

按功能依赖、模型和时序关系切片，每片一个或少量强相关 slug，小需求一次完成。每片调度实现绑定（默认 keel-builder），下发索引路径、slug/batch，按需读取功能及引用章节。tag 为 BUILD_SLICE_DONE，最后一片为 BUILD_DONE；artifact 为 run 内 plan.md。

按实现任务说明实现、测试和提交；每片只记录新 commit，最后一片完成相关测试及适用验证。全部完成进入 REVIEW。契约矛盾、遗漏关键决策或不可执行时 PAUSED，带证据交回 Plan。

### REVIEW / FIX

调度验收绑定（默认 keel-qa），输入索引和 Builder commits，完整验收全部功能，输出 qa-feedback.md，tag 为 APPROVED 或 REJECTED。

APPROVED 进入 CALL_CHAIN_PREFILTER；REJECTED 的阻断项写 fix-brief.md，进入 FIX。每轮新实现 Agent 只修阻断、验证并提交，tag FIX_DONE；随后新验收 Agent 执行 REVIEW_FIX，覆盖 qa-feedback.md。最多 3 轮，仍阻断则 PAUSED；通过进入 CALL_CHAIN_PREFILTER。

### CALL_CHAIN_PREFILTER

主会话独立检查本轮 Builder diff：明确没有外部入口、异步推进点、业务状态节点、流转条件或状态变更符号变化时记 noop；存在任一变化或不确定时保守记 run。

```bash
record_call_chain_prefilter "<noop|run>" "<判定证据>"
```

- on-demand 的 noop：执行 record_call_chain_skip，不调度 Agent，直接 DONE。
- on-demand 的 run：进入 CALL_CHAIN。
- 恢复旧 mode=shadow：始终独立调度，不向 Agent 暴露预判；完成后使用 record_call_chain_shadow_result。

### CALL_CHAIN

仅 prefilter=run 或旧 shadow 进入此阶段。调度流程维护绑定（默认 keel-call-chain），下发规范中的索引目录、本轮最终 Builder commits 与相关计划，按任务说明输出 call-chain-review.md。

- CALL_CHAIN_NOOP：执行 `record_call_chain_result noop`。
- CALL_CHAIN_UPDATED：核对仅索引文档的独立 docs commit，再执行 `record_call_chain_result updated "<commit-sha>"`。

旧 shadow 改用 `record_call_chain_shadow_result "<noop|updated>"`，并记录对应文档结果；随后 DONE。

## 完成

报告 Builder commits、QA 验证摘要、CallChain 跳过/NOOP/UPDATED 结论和 artifact。DONE 后新反馈另开 plan/dev run，范围变化回到 `/keel-plan`。
