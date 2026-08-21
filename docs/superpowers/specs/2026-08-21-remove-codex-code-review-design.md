# 移除 Codex App CodeReview 设计

## 背景与范围

Harness Backend 当前在 Codex App 的 full 和 fast 流程中调度独立 CodeReview Agent。此次只修改 Codex App runtime：完整移除 CodeReview 阶段、Agent、状态和产物，并由 QA 承担构建后的验收。`claude-code/` runtime 保持原样。

## 状态机

full 流程调整为：

```text
SCOPE_BUILD -> SCOPE_REVIEW(QA) -> BUILD -> REVIEW(QA)
  -> REJECTED: FIX -> REVIEW_FIX(QA)
  -> APPROVED: CALL_CHAIN_PREFILTER -> CALL_CHAIN/DONE
```

fast 流程调整为：

```text
BUILD_FAST -> REVIEW_FAST(QA)
  -> REJECTED: FIX_FAST -> REVIEW_FAST_FIX(QA)
  -> APPROVED: DONE
```

full 的 QA 读取 plan、build-scope 和 Builder commits；fast 的 QA 读取 plan 和 Builder commits。两者都运行相关测试、验证业务响应与副作用，并依据共享代码质量红线检查 stub、入口层业务逻辑和测试质量。QA 返回 `APPROVED` 或 `REJECTED`，阻断项写入 `fix-brief.md`。修复最多三轮，超过上限进入 `PAUSED`。

## Runtime 清理

删除 Codex 的 `harness-code-review.md` 和 `harness-code-review.toml`。从 full/fast Skill、Builder、QA、CallChain、共享编排契约、初始化状态及公共 helper 中删除 CodeReview 调度和展示逻辑。

新 run 不再包含 `code-review.md` artifact 或 `review.code_review` 状态。full 保留 `qa-feedback.md`、`fix-brief.md` 和 CallChain 产物；fast 使用 `qa-feedback.md` 与 `fix-brief.md`。部署 manifest 会在再次部署时清理已跟踪的旧 CodeReview Agent 文件。

## 旧 Run 恢复

旧 full run 恢复到 `PARALLEL_REVIEW`、`CODE_REVIEW` 或复审阶段时，忽略旧 `review.code_review` 状态并使用 `REVIEW` 或 `REVIEW_FIX` 重新执行 QA。旧 fast run 恢复到 `CODE_REVIEW_FAST` 或 `CODE_REVIEW_FAST_FIX` 时，分别映射到 `REVIEW_FAST` 或 `REVIEW_FAST_FIX`。已有 `fix-brief.md` 可以继续由 Builder 消费；旧 `code-review.md` 只作为历史文件保留，不参与新门禁。

## 文档与校验

README 和 Codex eval 描述改为 QA-only 验收，同时明确 Claude Code 仍保留原有 CodeReview 流程。指标和 slimming gate 删除已移除的 Codex CodeReview Agent 项。

原有 runtime parity 检查改为验证两类事实：仍共享的 plan 和基础文件保持一致；Codex 不再包含 CodeReview Agent，而 Claude Code 仍包含它。由于 backend 状态机已按用户要求产生 runtime 差异，不再对 full/fast 编排文件做虚假的等价比较。

验证包括：Shell 语法、slimming targets、CallChain 受控评测、Codex 临时部署 manifest、CodeReview 残留扫描，以及确认 `claude-code/` 没有本次 diff。
