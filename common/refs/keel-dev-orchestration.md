# Keel Dev 编排契约

full 与 fast 主会话都必须遵守本契约。

只使用当前 runtime 的原生 subagent；不启动 tmux、pane、send-keys、`codex` 或其他 Agent CLI 子进程。Agent 之间不直接通信。

## Run

1. 仅在用户明确要求时创建分支，然后初始化目录：

```bash
source .codex/common/scripts/keel-init.sh
KEEL_BRANCH=$(git branch --show-current)
KEEL_BRANCH_DIR=".keel/iterations/${KEEL_BRANCH}"
RUN_NUMBER=$(get_next_run_number "$KEEL_BRANCH_DIR")
KEEL_OUTPUT_DIR="${KEEL_BRANCH_DIR}/run-${RUN_NUMBER}"
mkdir -p "$KEEL_OUTPUT_DIR"
```

2. 从用户输入、路径或 `.keel/plans/` 取得用户已确认的 Markdown 计划，调用 `validate_keel_plan "<计划路径>"`。缺失、旧格式或契约不完整时停止并返回 `/keel-plan`；HTML 仅供用户审阅，不作为执行输入。
3. 确认计划没有未决问题或交给 Builder 的关键选择，再复制到 `${KEEL_OUTPUT_DIR}/plan.md`。不得用已有 run 的旧 artifact 补齐计划。
4. 初始化函数只传入 output_dir 和 run 内 plan.md，返回唯一 `state.json` 路径并导出 `KEEL_PROFILE`。
5. 读取项目根 `AGENTS.md`，不存在时读 `README.md`。

## Preflight

从项目手册、配置、脚本和 CI 确定语言、目录与验证命令；多语言按受影响模块记录，信息不足时调研工具链。

- `main_compile` 保留兼容字段名，表示适用的构建、类型/语法或启动/加载检查；失败则停止。
- `test_compile` 表示独立测试编译、发现/收集或等价测试准备。无独立步骤记 `not-applicable` 及理由，后续仍须运行测试；无法执行不等于不适用。
- 测试准备失败由用户决定是否继续；允许则记 `failed_allowed`，后续区分基线失败与本轮回归。
- summary 逐模块记录检查类型、目录、命令和结果；未执行不标通过，任一适用检查失败不能整体标通过。

## 调度

每个 Agent prompt 只需给出：`KEEL_PROFILE` 绝对路径、阶段、输入、输出、完成 tag。Agent 从该 `state.json` 读取 `plan_path`，写 progress，完成一个阶段后返回，不与其他 Agent 通信。

主会话收到结果后依次校验完成 tag、artifact 和 git commit，再更新 `state.json`。每个阶段使用新 Agent 执行；完成后结束当前执行。

## 进度与恢复

读取追加式 `progress.tsv` 的最新记录向用户报告状态；旧 run 读取 state/profile 中配置的 `progress.events`。审查类阶段 5 分钟、构建/修复阶段 15 分钟无有效进度时检查 Agent；卡住或失联则结束旧执行并从磁盘状态启动新执行。每阶段每角色最多恢复 2 次，超过后置为 `PAUSED`。

## 门禁

- 只消费当前 artifact，不扫描历史版本。恢复旧 run 时先校验其 plan.md；旧格式须重新生成计划并新建 run，不自动拼接或迁移历史输入。
- 运行中的执行 artifact 缺失或格式错误时定向重做一次；再次失败计入恢复次数。`plan.md` 缺失不重做，直接停止并返回 Plan 阶段。
- 只记录 Builder 本轮新 commit，不审查或提交用户无关改动。
- QA `REJECTED` 阻断；非阻断观察只汇总。
- 除 Builder 代码 commit 和 CallChain 文档 commit 外，不自动 stage、merge、squash、push 或清理历史。
