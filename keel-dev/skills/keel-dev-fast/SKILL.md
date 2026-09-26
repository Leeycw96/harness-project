---
name: keel-dev-fast
description: 日常小中型后端改动的快速 subagent 流程，只编排实现与 QA。
user-invocable: true
---

# Keel Dev Fast

适合局部 bugfix、校验、错误处理和低风险测试补强。迁移、权限、事务并发、外部集成、跨模块状态流转或大重构交回 full；业务状态节点、流转条件或状态变更符号调整也停止 fast，改用 `/keel-dev`。

先读 `.codex/common/refs/keel-dev-orchestration.md#主会话编排`，按绑定注入规范、通用任务要求和当前任务章节。

## 初始化

校验并快照计划：

```bash
KEEL_PROFILE=$(init_keel_fast_run "$KEEL_OUTPUT_DIR" "$KEEL_PLAN_PATH")
export KEEL_PROFILE
```

保存绑定；输入不合法返回 Plan，计划无未决问题且 Preflight 通过后 BUILD_FAST。

## 状态机

1. BUILD_FAST：调度实现绑定，下发范围与索引，按任务说明实现、验证和提交；tag BUILD_FAST_DONE，artifact 为 plan.md。记录新 commit 后 REVIEW_FAST。
2. REVIEW_FAST：调度验收绑定，验证所有目标与 Builder commits，写 qa-feedback.md。APPROVED → DONE；REJECTED 阻断项写 fix-brief.md → FIX_FAST。
3. FIX_FAST：每轮实现 Agent 修阻断、验证并提交，tag FIX_FAST_DONE；验收 Agent 以 REVIEW_FAST_FIX 覆盖反馈。最多 3 轮，通过 DONE，否则 PAUSED。

契约矛盾、关键遗漏或不可执行时 PAUSED，交回 Plan；状态机变化阻断并转 full。fast 不调度流程维护，不生成 CallChain artifact，也不读取 `.keel/call-chain/`。

## 完成

报告 commits、QA 摘要和 artifact，注明未经过 CallChain；DONE 后用新 run，范围变化回到 Plan。
