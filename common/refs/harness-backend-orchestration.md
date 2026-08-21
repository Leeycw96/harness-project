# Harness Backend 编排契约

full 与 fast 主会话都必须遵守本契约。

只使用当前 runtime 的原生 subagent；不启动 tmux、pane、send-keys、`codex`、Claude Code 或其他 Agent CLI 子进程。Agent 之间不直接通信。

## Run

1. 仅在用户明确要求时创建分支，然后初始化目录：

```bash
source .codex/common/scripts/harness-init.sh
HARNESS_BRANCH=$(git branch --show-current)
HARNESS_BRANCH_DIR=".harness/iterations/${HARNESS_BRANCH}"
RUN_NUMBER=$(get_next_run_number "$HARNESS_BRANCH_DIR")
HARNESS_OUTPUT_DIR="${HARNESS_BRANCH_DIR}/run-${RUN_NUMBER}"
mkdir -p "$HARNESS_OUTPUT_DIR"
```

2. 从用户输入、路径或 `.harness/plans/` 取得需求计划；调用 `resolve_implementation_plan_path "<需求计划路径>"` 读取其中唯一的 `<implementation-plan path="..." />`，取得代码改造计划。声明缺失、格式不合法或任一文件不存在时停止，并要求重新运行 `/harness-plan`。
3. 确认两份计划没有 `TBD`、未决问题或交给 Builder 的关键选择，再分别复制到 `${HARNESS_OUTPUT_DIR}/plan.md` 和 `${HARNESS_OUTPUT_DIR}/implementation-plan.md`。不得用已有 run 的旧 artifact 补齐缺失计划。
4. 调用当前模式的初始化函数，传入 run 内两份计划，返回唯一 `state.json` 路径并导出兼容变量 `HARNESS_PROFILE`。
5. 读取项目根 `AGENTS.md`，不存在时读 `CLAUDE.md`。

## Preflight

优先执行项目手册指定的主代码和测试编译命令；未指定且有 `pom.xml` 时使用：

```bash
mvn clean compile -DskipTests=true -q
mvn test-compile -q
```

主编译失败时记录短摘要并停止。测试编译失败时由用户决定是否继续；继续则记录 `failed_allowed`，后续 Agent 不得把该基线问题算作本轮回归。

## 调度

每个 Agent prompt 只需给出：`HARNESS_PROFILE` 绝对路径、阶段、输入、输出、完成 tag。Agent 从该 `state.json` 读取 `plan_path` 与 `implementation_plan_path`，写 progress，完成一个阶段后返回，不与其他 Agent 通信。

主会话收到结果后依次校验完成 tag、artifact 和 git commit，再更新 `state.json`。每个阶段使用新 Agent 执行；完成后结束当前执行。

## 进度与恢复

读取追加式 `progress.tsv` 的最新记录向用户报告状态；旧 run 读取 state/profile 中配置的 `progress.events`。审查类阶段 5 分钟、构建/修复阶段 15 分钟无有效进度时检查 Agent；卡住或失联则结束旧执行并从磁盘状态启动新执行。每阶段每角色最多恢复 2 次，超过后置为 `PAUSED`。

## 门禁

- 只消费当前 artifact，不扫描历史版本。
- 运行中的执行 artifact 缺失或格式错误时定向重做一次；再次失败计入恢复次数。`plan.md` 或 `implementation-plan.md` 缺失不重做，直接停止并返回 Plan 阶段。
- 只记录 Builder 本轮新 commit，不审查或提交用户无关改动。
- QA `REJECTED` 阻断；非阻断观察只汇总。
- 除 Builder 代码 commit 和 CallChain 文档 commit 外，不自动 stage、merge、squash、push 或清理历史。
