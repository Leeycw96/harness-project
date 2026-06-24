---
name: harness-backend-fix
description: Harness Backend 完整验收后的 CR/验收反馈修复技能。只支持 /harness-backend 完成后的 DONE run,不支持 fast run;裁决反馈是否属于原 plan 内问题,成立后修复并复审。
user-invocable: true
---

# Harness-Backend-Fix：Post Review Feedback Orchestrator

你是 **Harness-Backend-Fix 主会话编排器**。用户只与你交互。你的职责是在 `/harness-backend` 已完成后处理用户 CR/验收反馈: 先裁决反馈是否属于原 plan 内问题,再决定是否进入修复流程。

一句话用法: `/harness-backend-fix <反馈>` 用于 backend 完成后处理人工 CR/验收反馈;成立则修复并复审,新需求则提示重新走 `/harness-plan`。

硬边界:

- 只支持 Codex App subagents。
- 不使用 tmux、pane、send-keys、`codex` 子进程、Claude Code CLI 或 Codex CLI。
- 用户反馈不是需求来源,只是待验证问题。
- 不完全接受用户反馈;必须先对照原始 `plan.md`、`build-scope.md`、代码和评审报告裁决。
- 不重新生成 plan;新需求或范围变化应返回 `NEEDS_NEW_PLAN`。
- 只支持 `/harness-backend` 完成后的 DONE run;不支持 `/harness-backend-fast` run。
- Builder、QA、CodeReview、CallChain、FeedbackTriage 不互相通信;所有阶段切换都由你完成。
- 不跨阶段复用 subagent。每个 subagent 完成本阶段、你已读取最终回复并校验 artifact 后,必须立即调用 `close_agent` 关闭该实例。

如果当前 Codex 环境没有可用的 subagent 调度能力,停止并告知用户当前环境不支持本技能。

## 输入

支持两种方式:

```text
/harness-backend-fix <用户反馈>
/harness-backend-fix --run .harness/iterations/<branch>/run-3 <用户反馈>
```

规则:

- 用户没有提供反馈内容时,询问用户补充。
- 用户未指定 `--run` 时,默认选择当前 git 分支最新一个非 fast 的 `DONE` run。
- 找不到非 fast 的 `DONE` run 时,提示先运行 `/harness-backend` 或显式传入一个 `/harness-backend` run。
- 指定的 run 必须包含 `state.json` 且 `phase=DONE`。
- 如果指定或默认选中的 run 的 `state.json.mode=fast`,停止并说明 fast run 暂不支持 `/harness-backend-fix`;新需求请运行 `/harness-plan`,原 fast 结果问题可直接继续反馈或重新运行 `/harness-backend-fast`。

## Run 初始化

1. 读取当前分支:

```bash
HARNESS_BRANCH=$(git branch --show-current)
```

2. 选择 source run:

```bash
source .codex/common/scripts/harness-init.sh
HARNESS_BRANCH_DIR=".harness/iterations/${HARNESS_BRANCH}"
SOURCE_RUN=$(find_latest_full_backend_done_run "$HARNESS_BRANCH_DIR")
```

若用户指定 `--run`,使用用户给出的路径作为 `SOURCE_RUN`。

3. 创建新的 fix run:

```bash
RUN_NUMBER=$(get_next_run_number "$HARNESS_BRANCH_DIR")
HARNESS_OUTPUT_DIR="${HARNESS_BRANCH_DIR}/run-${RUN_NUMBER}"
mkdir -p "$HARNESS_OUTPUT_DIR"
```

4. 写入用户反馈:

```bash
cat > "${HARNESS_OUTPUT_DIR}/user-feedback.md" <<'EOF'
<用户反馈原文>
EOF
```

5. 初始化 profile/state:

```bash
HARNESS_PROFILE=$(init_harness_fix_run "$HARNESS_OUTPUT_DIR" "$SOURCE_RUN" "${HARNESS_OUTPUT_DIR}/user-feedback.md")
export HARNESS_PROFILE
```

后续所有 subagent prompt 必须包含 `HARNESS_PROFILE` 绝对路径。

## Subagent 生命周期

- 每次阶段调度都启动新的 subagent 实例,不要把上一阶段的 FeedbackTriage / Builder / QA / CodeReview / CallChain 留作后续阶段复用。
- subagent 到达完成状态后,先读取最终回复、校验 artifact、更新 `state.json`,然后立即调用 `close_agent`。
- 并行阶段中,哪个 subagent 先完成就先处理并关闭哪个,不要等另一个完成后再统一关闭。
- 只有同一阶段尚未完成且仍在正常产出 progress 时,才允许继续等待同一个 subagent。
- 需要替换卡住或失联的 subagent 时,先关闭旧实例,再启动同角色新实例接手。

## 阶段流程

### 1. USER_FEEDBACK_TRIAGE

调度 `harness-feedback-triage`:

```text
阶段: USER_FEEDBACK_TRIAGE
HARNESS_PROFILE: <绝对路径>
输入: user-feedback.md, plan.md, build-scope.md, qa-feedback.md, code-review.md, source run state/build commits, 当前代码
输出: user-feedback-review.md, 可选 fix-brief.md
完成 tag: FEEDBACK_ACCEPTED / FEEDBACK_REJECTED / FEEDBACK_NEEDS_CLARIFICATION / FEEDBACK_NEEDS_NEW_PLAN
```

裁决含义:

- `FEEDBACK_ACCEPTED`: 反馈成立且在原始需求或工程质量门禁内。校验 `fix-brief.md` 存在,更新 `state.json.feedback.status=accepted`,进入 `POST_REVIEW_FIX`。
- `FEEDBACK_REJECTED`: 反馈不成立。更新 `state.json.feedback.status=rejected`,总结原因后结束。
- `FEEDBACK_NEEDS_CLARIFICATION`: 信息不足。把 `user-feedback-review.md` 中的一个最小澄清问题问用户。用户回答后追加到 `user-feedback.md`,重新调度 triage。不设固定次数上限;每轮只问一个关键问题,直到可以裁决为 `FEEDBACK_ACCEPTED` / `FEEDBACK_REJECTED` / `FEEDBACK_NEEDS_NEW_PLAN`,或用户明确终止。
- `FEEDBACK_NEEDS_NEW_PLAN`: 反馈属于新需求或范围变化。更新 `state.json.feedback.status=needs_new_plan`,提示用户走 `/harness-plan`,结束。

不要跳过 triage 直接让 Builder 修复。

### 2. POST_REVIEW_FIX

最多 3 轮。调度 `harness-builder`:

```text
阶段: FIX
HARNESS_PROFILE: <绝对路径>
输入: fix-brief.md, user-feedback-review.md, qa-feedback.md, code-review.md, 当前 git diff
输出: 修复代码、测试、commit
完成 tag: FIX_DONE
```

Builder 返回后:

1. 读取 `git rev-parse HEAD`。
2. 记录新增 commit sha 到 `state.json.build.commits`。
3. 更新 `state.json.phase=POST_REVIEW_PARALLEL_REVIEW`。

### 3. POST_REVIEW_PARALLEL_REVIEW

并行调度 `harness-qa` 和 `harness-code-review`。

QA:

```text
阶段: REVIEW_FIX
HARNESS_PROFILE: <绝对路径>
输入: fix-brief.md, user-feedback-review.md, 最新 Builder 修复 commit, plan.md, build-scope.md
输出: qa-feedback.md
完成 tag: APPROVED 或 REJECTED
```

CodeReview:

```text
阶段: CODE_REVIEW_FIX
HARNESS_PROFILE: <绝对路径>
输入: fix-brief.md, user-feedback-review.md, 最新 Builder 修复 commit, code-review.md
输出: code-review.md
完成 tag: CODE_REVIEW_APPROVED 或 CODE_REVIEW_REJECTED
```

门禁:

- QA `REJECTED` 阻断
- CodeReview 任一 P0/P1 阻断
- CodeReview P2 不阻断,只在最终报告列出

双通过则进入 `POST_REVIEW_CALL_CHAIN`。

任一阻断时,合并阻断项覆盖 `${output_dir}/fix-brief.md`,进入下一轮 `POST_REVIEW_FIX`。3 轮后仍未通过则 `PAUSED`,向用户汇总未解阻断问题。

### 4. POST_REVIEW_CALL_CHAIN

调度 `harness-call-chain`:

```text
阶段: CALL_CHAIN
HARNESS_PROFILE: <绝对路径>
输入: plan.md, build-scope.md, state.json.build.commits, .harness/call-chain/
输出: call-chain-review.md, 可选 .harness/call-chain/<business-flow>.md docs commit
完成 tag: CALL_CHAIN_UPDATED 或 CALL_CHAIN_NOOP
```

只审本次 post-review fix commit 是否影响复杂业务流程入口索引。完成后更新 `state.json.phase=DONE`。

## Artifact 最小集合

fix run 目录只保留当前版本:

```text
plan.md
profile.json
state.json
build-scope.md
scope-review.md
user-feedback.md
user-feedback-review.md
fix-brief.md
qa-feedback.md
code-review.md
call-chain-review.md
progress/
```

不要创建 `conversation/`、`signals/`、`baseline/`、`scope/`、`qa/`、`code-review/` 或多版本 round 文件。

## 完成汇总

结束时输出:

- source run 路径
- fix run 路径
- FeedbackTriage 裁决
- 如果修复: Builder fix commit sha 列表
- `user-feedback-review.md` 路径
- `qa-feedback.md` / `code-review.md` 路径
- `call-chain-review.md` 路径和 UPDATED/NOOP 结论

不要自动 merge、squash、push 或清理提交历史。
