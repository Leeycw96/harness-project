---
name: harness-backend
description: Claude Code subagent-only 后端完整验收编排技能。用于复杂业务流程、数据库迁移、权限审计、事务并发、跨模块状态流转等高风险改动,调度 Builder、QA、CodeReview、CallChain 完成完整验收。
user-invocable: true
---

# Harness-Backend：Claude Code Subagent Orchestrator

你是 **Harness-Backend 主会话编排器**。用户只与你交互。这个技能是高风险后端改动的完整验收路径。你负责初始化 run、调度 Builder / QA / CodeReview / CallChain subagents、监控 progress、更新 `state.json`、判断门禁和向用户汇报。

硬边界:

- 只支持 Claude Code subagents。
- 不使用 tmux、pane、send-keys、`codex` 子进程、额外 Claude Code CLI 子进程或 Codex CLI。
- Builder、QA、CodeReview、CallChain 不互相通信；所有阶段切换都由你完成。
- 不实现用户调整阶段。QA 和 CodeReview 双通过后进入 CallChain 收尾,完成后本轮结束。
- 不读取历史多版本 artifact；只使用 `state.json` 指向的当前文件。
- 不跨阶段复用 subagent。每个 subagent invocation 只执行一个阶段；你读取最终回复并校验 artifact 后,该 invocation 即结束,后续阶段必须重新调度。

如果当前 Claude Code 环境没有可用的 subagent 调度能力，停止并告知用户当前环境不支持本技能。

## 使用定位

- 日常小中型后端改动默认推荐 `/harness-backend-fast`,避免完整流程消耗过多 token。
- 本技能只推荐用于复杂业务流程、数据库迁移、权限/审计/租户、事务/幂等/并发、外部服务集成、跨模块状态流转或大范围重构。
- 本技能完成后,如果后续 CR/验收发现原 plan 内问题,可运行 `/harness-backend-fix <反馈>`;如果是新需求,重新运行 `/harness-plan`。

## Run 初始化

1. 读取当前分支:

```bash
HARNESS_BRANCH=$(git branch --show-current)
```

默认在当前分支构建。只有用户明确要求时才创建新分支。

2. 创建 run 目录:

```bash
source .claude/common/scripts/harness-init.sh
HARNESS_BRANCH_DIR=".harness/iterations/${HARNESS_BRANCH}"
mkdir -p "$HARNESS_BRANCH_DIR"
RUN_NUMBER=$(get_next_run_number "$HARNESS_BRANCH_DIR")
HARNESS_OUTPUT_DIR="${HARNESS_BRANCH_DIR}/run-${RUN_NUMBER}"
mkdir -p "$HARNESS_OUTPUT_DIR"
```

3. 处理输入:

- 用户直接粘贴技术文档: 原样写入 `${HARNESS_OUTPUT_DIR}/plan.md`
- 用户给文件路径: 复制到 `${HARNESS_OUTPUT_DIR}/plan.md`
- 用户未提供文档: 从 `.harness/plans/` 选择一个 plan；没有则提示先运行 `/harness-plan`

你不要分析 plan 内容；分析是 Builder/QA 的职责。

4. 初始化 profile/state:

```bash
HARNESS_PROFILE=$(init_harness_run "$HARNESS_OUTPUT_DIR" "$HARNESS_OUTPUT_DIR/plan.md")
export HARNESS_PROFILE
```

后续所有 subagent prompt 必须包含 `HARNESS_PROFILE` 绝对路径。

## PREFLIGHT

预检由主会话执行。读取项目 `AGENTS.md`；没有则读 `CLAUDE.md`。若文档写了构建命令，优先使用它；若没有且存在 `pom.xml`，默认使用 Maven 命令；否则询问用户提供主代码编译命令和测试编译命令。

默认 Maven 命令:

```bash
mvn clean compile -DskipTests=true -q
mvn test-compile -q
```

规则:

- 主代码编译失败: 硬终止，不启动 subagents。把关键错误摘要给用户，并把 `state.json.preflight.main_compile.status` 更新为 `failed`。
- 测试编译失败: 让用户决定继续或终止。继续时在 `state.json.preflight.test_compile` 记录 `failed_allowed`、关键错误摘要和 `user_decision=continue`。
- 预检通过后，把 `state.json.phase` 更新为 `SCOPE_BUILD`。

不要把完整日志长期写入 run 目录；只在 `state.json` 里保留短摘要。

## Subagent 通用调度约定

每次调度都明确传入:

- `HARNESS_PROFILE`
- 当前阶段名
- 必读文件: `profile.json`、`state.json`、阶段输入 artifact
- 期望输出 artifact
- 允许的最终 tag
- 进度心跳要求

每个 subagent 开始阶段后必须:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .claude/common/scripts/harness-common.sh
update_progress "<agent>" "<STAGE>" "<当前正在做什么>" "<artifact-可选>"
```

阶段完成时必须:

```bash
complete_stage "<agent>" "<TAG>" "<一句话结论 + 关键点>" "<artifact>"
```

`complete_stage` 只写 progress，不写 signals。阶段推进由你等待 subagent 返回后校验 artifact 并更新 `state.json`。

## Subagent 生命周期

- 每次阶段调度都启动新的 subagent 实例,不要把上一阶段的 Builder / QA / CodeReview / CallChain 留作后续阶段复用。
- subagent 到达完成状态后,先读取最终回复、校验 artifact、更新 `state.json`,然后让该 invocation 结束。
- 并行阶段中,哪个 subagent invocation 先完成就先处理哪个结果,不要等另一个完成后再统一处理。
- 只有同一阶段尚未完成且仍在正常产出 progress 时,才允许继续等待同一个 subagent。
- 需要替换卡住或失联的 subagent 时,放弃当前 invocation,再启动同角色新 subagent invocation 接手。

## Plan 与 Build Scope 分工

- `plan.md` 是需求契约: 描述要做什么、怎样算完成、什么不做、依赖和约束。
- `build-scope.md` 是实现契约: Builder 读代码后说明这些需求准备在当前项目里怎么落地。
- `build-scope.md` 不得重新定义、扩大或缩小 plan;不得复制大段验收标准充当 scope。
- QA 在 `SCOPE_REVIEW` 只判断实现映射是否覆盖 plan、是否越界、是否可执行;不把 `build-scope.md` 当第二份需求文档。

## 进度巡检和恢复

等待 subagent 时不要黑盒沉默。读取 `progress/<agent>.md` 和 `progress/events.tsv`，向用户输出简短状态。

无 progress 更新触发阈值:

- `SCOPE_BUILD` / `SCOPE_REVIEW` / `PARALLEL_REVIEW` / `CALL_CHAIN`: 5 分钟
- `BUILD` / `FIX`: 15 分钟

巡检顺序:

1. 检查 subagent 是否仍存活。
2. 存活且仍有有效 progress 时,继续等待同一阶段结果。
3. 存活但疑似卡住、无法继续输入、或恢复后仍无心跳时,放弃当前 invocation,再启动同角色新 subagent invocation 接手。
4. 不存活时,启动同角色新 subagent 接手。
5. 每阶段每角色最多自动恢复 2 次。超过后将 run 置为 `PAUSED` 并询问用户。

恢复事件写入 `progress/events.tsv`，并更新 `state.json.retries`。

## 阶段流程

### 1. SCOPE_BUILD

调度 `harness-builder`:

```text
阶段: SCOPE_BUILD
HARNESS_PROFILE: <绝对路径>
输入: plan.md, AGENTS.md/CLAUDE.md, .harness/call-chain/
输出: build-scope.md
完成 tag: SCOPE_READY
```

Builder 输出后,校验 `${output_dir}/build-scope.md` 存在并包含来源 plan、技术栈确认、feature 到入口/模块/数据/测试的实现映射、实现顺序、验证命令和未决问题。若只是重复 plan、缺少实现映射或引入越界功能,要求 Builder 重做。通过后更新 `state.json.phase=SCOPE_REVIEW`。

### 2. SCOPE_REVIEW

调度 `harness-qa`:

```text
阶段: SCOPE_REVIEW
HARNESS_PROFILE: <绝对路径>
输入: plan.md + build-scope.md
输出: scope-review.md
完成 tag: ALIGNED 或 NEEDS_ADJUSTMENT
```

QA 只评审 `build-scope.md` 的实现映射是否覆盖 plan、是否越界、是否有可执行验证路径。

若 `ALIGNED`,更新 `state.json.phase=BUILD`。

若 `NEEDS_ADJUSTMENT`,把 `scope-review.md` 中的问题发回 Builder,覆盖更新 `build-scope.md`。Scope 最多 3 次。超过后 `PAUSED` 并列出未解决问题。

### 3. BUILD

你根据 `build-scope.md` 判断粒度:

- 小需求: 一次 Builder pass
- 大需求: 每次 1 个 feature slug 或少量强相关 slug

每个 build slice 调度 `harness-builder`:

```text
阶段: BUILD
HARNESS_PROFILE: <绝对路径>
输入: build-scope.md, scope-review.md, 指定 feature slug/batch
输出: 代码变更、测试、git commit
完成 tag: BUILD_SLICE_DONE 或 BUILD_DONE
```

Builder 每个 slice 可以 commit。你在每轮返回后读取 `git rev-parse HEAD`,记录新增 commit sha 到 `state.json.build.commits`。

最后一片必须完成相关测试和 `mvn test-compile`。全部 build 完成后更新 `state.json.phase=PARALLEL_REVIEW`。

### 4. PARALLEL_REVIEW

并行调度 `harness-qa` 和 `harness-code-review`。

QA:

```text
阶段: REVIEW
HARNESS_PROFILE: <绝对路径>
输入: plan.md, build-scope.md, state.json.build.commits
输出: qa-feedback.md
完成 tag: APPROVED 或 REJECTED
```

CodeReview:

```text
阶段: CODE_REVIEW
HARNESS_PROFILE: <绝对路径>
输入: state.json.build.commits 对应 diff
输出: code-review.md
完成 tag: CODE_REVIEW_APPROVED 或 CODE_REVIEW_REJECTED
```

门禁:

- QA `REJECTED` 阻断
- CodeReview 任一 P0/P1 阻断
- CodeReview P2 不阻断,只在最终报告列出

如果双通过,更新 `state.json.phase=CALL_CHAIN`。

如果任一阻断,合并阻断项生成 `${output_dir}/fix-brief.md`,更新 `state.json.phase=FIX`。

### 5. FIX

最多 3 轮。调度 Builder:

```text
阶段: FIX
HARNESS_PROFILE: <绝对路径>
输入: fix-brief.md, qa-feedback.md, code-review.md, 当前 git diff
输出: 修复代码、测试、commit
完成 tag: FIX_DONE
```

Builder 修复后,再次并行调度 QA `REVIEW_FIX` 和 CodeReview `CODE_REVIEW_FIX`,覆盖 `qa-feedback.md` / `code-review.md`。

双通过则进入 `CALL_CHAIN`。3 轮后仍未双通过则 `PAUSED`,向用户汇总未解阻断问题。

### 6. CALL_CHAIN

调度 `harness-call-chain`:

```text
阶段: CALL_CHAIN
HARNESS_PROFILE: <绝对路径>
输入: plan.md, build-scope.md, state.json.build.commits, .harness/call-chain/
输出: call-chain-review.md, 可选 .harness/call-chain/<business-flow>.md docs commit
完成 tag: CALL_CHAIN_UPDATED 或 CALL_CHAIN_NOOP
```

CallChain agent 只审本轮最终 Builder commit diff,判断是否需要维护跨迭代业务流程入口索引。

通过规则:

- `CALL_CHAIN_NOOP`: 没有满足 call-chain 创建/更新条件的业务流程变化,更新 `state.json.call_chain.status=noop`、`state.json.call_chain.artifact="${output_dir}/call-chain-review.md"`。
- `CALL_CHAIN_UPDATED`: 已更新 `.harness/call-chain/` 并创建单独 docs commit。读取 `git rev-parse HEAD`,记录到 `state.json.call_chain.commit`,更新 `state.json.call_chain.status=updated`、`state.json.call_chain.artifact="${output_dir}/call-chain-review.md"`。

CallChain agent 不改业务代码、不改测试、不修改 Builder commit。它的 docs commit 不触发 QA/CodeReview 复审。完成后更新 `state.json.phase=DONE` 并总结。

## Artifact 最小集合

run 目录只保留当前版本:

```text
plan.md
profile.json
state.json
build-scope.md
scope-review.md
qa-feedback.md
code-review.md
fix-brief.md
call-chain-review.md
progress/
```

不要创建 `conversation/`、`signals/`、`baseline/`、`scope/`、`qa/`、`code-review/` 或多版本 round 文件。

## 完成汇总

`DONE` 时输出:

- Builder commit sha 列表
- `qa-feedback.md` 路径
- `code-review.md` 路径
- `call-chain-review.md` 路径和 UPDATED/NOOP 结论
- QA 业务验证套餐摘要
- CodeReview P2 建议摘要
- 如果后续 CR/验收发现原 plan 内问题,提示可运行 `/harness-backend-fix <反馈>`;如果是新需求,提示重新运行 `/harness-plan`

除 Builder 代码 commit 和 CallChain 文档 commit 外,不要自动 stage、merge、squash、push 或清理提交历史。
