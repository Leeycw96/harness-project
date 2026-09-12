---
name: keel-dev-fast
description: 日常小中型后端改动的快速 subagent 流程，只调度 Builder 和 QA。
user-invocable: true
---

# Keel Dev Fast

适合局部 bugfix、校验、错误处理和低风险测试补强；不适合迁移、权限、事务并发、外部集成、跨模块状态流转或大范围重构。涉及业务状态节点、流转条件或状态变更符号调整时停止 fast，提示改用 `/keel-dev` 以维护 CallChain；其他高风险内容也交回 full。

开始前读取 `.codex/common/refs/keel-dev-orchestration.md`。当前环境没有 subagent 能力时停止。

## 初始化

按共享契约校验用户已确认的单份 Markdown 计划，保存为 `plan.md`，调用：

```bash
KEEL_PROFILE=$(init_keel_fast_run "$KEEL_OUTPUT_DIR" "$KEEL_OUTPUT_DIR/plan.md")
export KEEL_PROFILE
```

`KEEL_PROFILE` 是兼容变量名，新 run 指向唯一的 `state.json`。

Markdown 计划完整、没有待确认事项且 Preflight 通过后进入 `BUILD_FAST`。计划缺失或格式不合法时停止，并要求重新运行 `/keel-plan`。

## 状态机

1. `BUILD_FAST`：调度 `keel-builder` 按 Markdown 计划实现、测试并提交，tag `BUILD_FAST_DONE`；只记录新 commit，进入 `REVIEW_FAST`。发现契约矛盾、遗漏关键决策或按现状无法执行时停止并 `PAUSED`，交回 Plan 阶段确认。
2. `REVIEW_FAST`：调度 `keel-qa` 按 Markdown 计划和共享代码质量红线验证 Builder commits，运行相关测试，输出 `qa-feedback.md`。
   - `APPROVED`：进入 `DONE`。
   - `REJECTED`：阻断项写入 `fix-brief.md`，进入 `FIX_FAST`。
3. `FIX_FAST`：最多 3 轮。新 Builder 只修阻断项、测试并提交，tag `FIX_FAST_DONE`；再调度 QA `REVIEW_FAST_FIX` 覆盖 `qa-feedback.md`。通过则 `DONE`，超过上限则 `PAUSED`。

fast 不生成 CallChain artifact，也不读取 `.keel/call-chain/`。

## 完成

报告 Builder commits、QA 验证摘要和 artifact 路径，明确本轮未经过 CallChain。DONE 后的新反馈通过新的 plan/dev run 处理；范围或方案变化重新运行 `/keel-plan`。
