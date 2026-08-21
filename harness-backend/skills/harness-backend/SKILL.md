---
name: harness-backend
description: 高风险后端改动的完整 subagent 验收流程，调度 Builder、QA 和 CallChain。
user-invocable: true
---

# Harness Backend

用于复杂流程、迁移、权限、事务并发、外部集成或跨模块状态流转。日常小中型改动使用 `/harness-backend-fast`。

开始前读取 `.codex/common/refs/harness-backend-orchestration.md`。当前环境没有 subagent 能力时停止。

## 初始化

按共享契约读取需求计划中声明的代码改造计划，将两份输入分别保存为 `plan.md` 和 `implementation-plan.md`，调用：

```bash
HARNESS_PROFILE=$(init_harness_run "$HARNESS_OUTPUT_DIR" "$HARNESS_OUTPUT_DIR/plan.md" "$HARNESS_OUTPUT_DIR/implementation-plan.md")
export HARNESS_PROFILE
```

`HARNESS_PROFILE` 是兼容变量名，新 run 指向唯一的 `state.json`。

两份计划均存在、没有待确认事项且 Preflight 通过后，直接进入 `BUILD`。缺少代码改造计划时停止，并要求重新运行 `/harness-plan`。

## 状态机

### BUILD

按已确认的代码改造计划，将小需求一次完成，大需求依据 `Implementation Sequence` 按一个或少量强相关 slug 切片。每片调度新 `harness-builder`，输入需求计划、代码改造计划和指定 slug，tag `BUILD_SLICE_DONE` 或 `BUILD_DONE`。Builder 不得重新选择技术方案或改变目标业务流程；发现契约矛盾、遗漏关键决策或按现状无法执行时，停止并将 run 置为 `PAUSED`，交回 Plan 阶段确认。

每片返回后只记录新增 commit。最后一片必须完成相关测试和测试编译；全部完成后进入 `REVIEW`。

### REVIEW

调度 `harness-qa`，按需求计划、代码改造计划和共享代码质量红线验证 Builder commits，运行相关测试，输出 `qa-feedback.md`，tag `APPROVED` 或 `REJECTED`。

通过则进入 `CALL_CHAIN_PREFILTER`；阻断项写入 `fix-brief.md`，进入 `FIX`。

### FIX

最多 3 轮。调度新 Builder 只修 `fix-brief.md`，运行相关测试并提交，tag `FIX_DONE`；随后运行 QA `REVIEW_FIX`，覆盖 `qa-feedback.md`。

通过则进入 `CALL_CHAIN_PREFILTER`；3 轮后仍阻断则 `PAUSED`。

### CALL_CHAIN_PREFILTER

主会话先独立审查 Builder diff：

- 明确没有外部入口、异步推进点或多阶段生命周期变化：记录 `noop`。
- 存在任一变化或无法确定：保守记录 `run`。

```bash
record_call_chain_prefilter "<noop|run>" "<判定证据>"
```

- `noop`：执行 `record_call_chain_skip`，不调度 Agent，直接进入 `DONE`。
- `run`：进入 `CALL_CHAIN`。

恢复旧 `mode=shadow` run 时仍始终调度 Agent，且不把预判告诉 Agent；完成后使用 `record_call_chain_shadow_result`。

### CALL_CHAIN

仅在 prefilter 为 `run` 或恢复旧 shadow run 时调度 `harness-call-chain`。Agent 依据代码改造计划，只审本轮 Builder commits 和已有 `.harness/call-chain/`，输出 `call-chain-review.md`：

- `CALL_CHAIN_NOOP`：执行 `record_call_chain_result noop`。
- `CALL_CHAIN_UPDATED`：只更新 call-chain 文件并创建独立 docs commit，再执行 `record_call_chain_result updated "<commit-sha>"`。

旧 shadow run 使用对应 shadow helper。随后置为 `DONE`。

## 完成

报告 Builder commits、QA 验证摘要、CallChain 跳过/NOOP/UPDATED 结论及 artifact 路径。DONE 后的新反馈通过新的 plan/backend run 处理；范围变化重新运行 `/harness-plan`。
