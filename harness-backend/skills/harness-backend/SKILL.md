---
name: harness-backend
description: 高风险后端改动的完整 subagent 验收流程，调度 Builder、QA、CodeReview 和 CallChain。
user-invocable: true
---

# Harness Backend

用于复杂流程、迁移、权限、事务并发、外部集成或跨模块状态流转。日常小中型改动使用 `/harness-backend-fast`。

开始前读取 `.codex/common/refs/harness-backend-orchestration.md`。当前环境没有 subagent 能力时停止。

## 初始化

按共享契约创建 run，将输入保存为 `plan.md`，调用：

```bash
HARNESS_PROFILE=$(init_harness_run "$HARNESS_OUTPUT_DIR" "$HARNESS_OUTPUT_DIR/plan.md")
export HARNESS_PROFILE
```

Preflight 通过后进入 `SCOPE_BUILD`。

## 状态机

### SCOPE_BUILD

调度 `harness-builder`，输入 plan、项目手册和已有 call-chain，输出 `build-scope.md`，tag `SCOPE_READY`。scope 必须把每个 feature 映射到入口、模块/文件、数据、测试、slice 和验证命令；不得复制或改写需求。

校验通过后进入 `SCOPE_REVIEW`。

### SCOPE_REVIEW

调度 `harness-qa`，输入 plan + build-scope，输出 `scope-review.md`，tag `ALIGNED` 或 `NEEDS_ADJUSTMENT`。

- `ALIGNED`：进入 `BUILD`。
- `NEEDS_ADJUSTMENT`：把最小问题清单交回新 Builder 覆盖 scope。
- 最多 3 次，仍不对齐则 `PAUSED`。

### BUILD

按 scope 将小需求一次完成，大需求按一个或少量强相关 slug 切片。每片调度新 `harness-builder`，输入 scope、最新 scope-review 和指定 slug，tag `BUILD_SLICE_DONE` 或 `BUILD_DONE`。

每片返回后只记录新增 commit。最后一片必须完成相关测试和测试编译；全部完成后进入 `PARALLEL_REVIEW`。

### PARALLEL_REVIEW

并行调度：

- `harness-qa`：按 plan/scope 验证 Builder commits，输出 `qa-feedback.md`，tag `APPROVED` 或 `REJECTED`。
- `harness-code-review`：只审 Builder commit diff，输出 `code-review.md`，tag `CODE_REVIEW_APPROVED` 或 `CODE_REVIEW_REJECTED`。

双通过进入 `CALL_CHAIN`；任一阻断则把 QA 阻断项和 CodeReview P0/P1 合并为 `fix-brief.md`，进入 `FIX`。

### FIX

最多 3 轮。调度新 Builder 只修 `fix-brief.md`，运行相关测试并提交，tag `FIX_DONE`；随后并行运行 `REVIEW_FIX` 和 `CODE_REVIEW_FIX`，覆盖评审文件。

双通过进入 `CALL_CHAIN`；3 轮后仍阻断则 `PAUSED`。

### CALL_CHAIN_PREFILTER（shadow）

主会话先独立审查 Builder diff：

- 明确没有外部入口、异步推进点或多阶段生命周期变化：记录 `noop`。
- 存在任一变化或无法确定：保守记录 `run`。

```bash
record_call_chain_prefilter "<noop|run>" "<判定证据>"
```

shadow 期间无论预判为何都继续调度 CallChain，且不把预判告诉 Agent，避免影响独立结论。

### CALL_CHAIN

调度 `harness-call-chain`，只审本轮 Builder commits 和已有 `.harness/call-chain/`，输出 `call-chain-review.md`：

- `CALL_CHAIN_NOOP`：记录 noop，并执行 `record_call_chain_shadow_result noop`。
- `CALL_CHAIN_UPDATED`：只更新 call-chain 文件并创建独立 docs commit，再执行 `record_call_chain_shadow_result updated`。

shadow 不改变交付门禁；即使预判与 Agent 不一致也完成本轮，但必须在汇总中报告并保留样本。随后置为 `DONE`。

## 完成

报告 Builder commits、QA 验证摘要、CodeReview P2、CallChain 结论、shadow 是否安全一致及 artifact 路径。DONE 后的新反馈通过新的 plan/backend run 处理；范围变化重新运行 `/harness-plan`。
