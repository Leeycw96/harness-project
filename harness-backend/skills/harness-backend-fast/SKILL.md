---
name: harness-backend-fast
description: 日常小中型后端改动的快速 subagent 流程，只调度 Builder 和 QA。
user-invocable: true
---

# Harness Backend Fast

适合局部 bugfix、校验、错误处理和低风险测试补强；不适合迁移、权限、事务并发、外部集成、跨模块状态流转或大范围重构。发现高风险内容时询问用户是否改用 `/harness-backend`。

开始前读取 `.codex/common/refs/harness-backend-orchestration.md`。当前环境没有 subagent 能力时停止。

## 初始化

按共享契约读取需求计划中声明的代码改造计划，将两份输入分别保存为 `plan.md` 和 `implementation-plan.md`，调用：

```bash
HARNESS_PROFILE=$(init_harness_fast_run "$HARNESS_OUTPUT_DIR" "$HARNESS_OUTPUT_DIR/plan.md" "$HARNESS_OUTPUT_DIR/implementation-plan.md")
export HARNESS_PROFILE
```

`HARNESS_PROFILE` 是兼容变量名，新 run 指向唯一的 `state.json`。

两份计划均存在、没有待确认事项且 Preflight 通过后进入 `BUILD_FAST`。缺少代码改造计划时停止，并要求重新运行 `/harness-plan`。

## 状态机

1. `BUILD_FAST`：调度 `harness-builder` 按需求计划和代码改造计划实现、测试并提交，tag `BUILD_FAST_DONE`；只记录新 commit，进入 `REVIEW_FAST`。发现契约矛盾、遗漏关键决策或按现状无法执行时停止并 `PAUSED`，交回 Plan 阶段确认。
2. `REVIEW_FAST`：调度 `harness-qa` 按两份计划和共享代码质量红线验证 Builder commits，运行相关测试，输出 `qa-feedback.md`。
   - `APPROVED`：进入 `DONE`。
   - `REJECTED`：阻断项写入 `fix-brief.md`，进入 `FIX_FAST`。
3. `FIX_FAST`：最多 3 轮。新 Builder 只修阻断项、测试并提交，tag `FIX_FAST_DONE`；再调度 QA `REVIEW_FAST_FIX` 覆盖 `qa-feedback.md`。通过则 `DONE`，超过上限则 `PAUSED`。

fast 不生成 CallChain artifact，也不读取 `.harness/call-chain/`。

## 完成

报告 Builder commits、QA 验证摘要和 artifact 路径，明确本轮未经过 CallChain。DONE 后的新反馈通过新的 plan/backend run 处理；范围或方案变化重新运行 `/harness-plan`。
