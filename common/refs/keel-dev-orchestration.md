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

2. 将已确认索引的绝对路径赋给 `KEEL_PLAN_PATH`，运行 `validate_keel_plan "$KEEL_PLAN_PATH"`。索引包含目标、验收、依赖及功能链接；功能文件包含模型、时序图、接口和改造点。输入缺失、旧格式或不完整时返回 `/keel-plan`。
3. 确认无未决问题后，传 output_dir 和原始索引路径给初始化函数；它校验并快照索引为 run 内 `plan.md`，复制关联功能文件并保留相对链接。不只复制索引，不用旧 run 补齐。
4. 返回 `state.json` 路径并导出 `KEEL_PROFILE`，`plan_path` 指向 run 内索引。恢复使用快照，不重新初始化；HTML 和审阅素材不作为执行输入。
5. 读取项目根 `AGENTS.md`，不存在时读 `README.md`。

## Preflight

从项目手册、配置、脚本和 CI 确定语言、目录与验证命令；多语言按受影响模块记录，信息不足时调研工具链。

- `main_compile` 保留兼容字段名，表示适用的构建、类型/语法或启动/加载检查；失败则停止。
- `test_compile` 表示独立测试编译、发现/收集或等价测试准备。无独立步骤记 `not-applicable` 及理由，后续仍须运行测试；无法执行不等于不适用。
- 测试准备失败由用户决定是否继续；允许则记 `failed_allowed`，后续区分基线失败与本轮回归。
- summary 逐模块记录检查类型、目录、命令和结果；未执行不标通过，任一适用检查失败不能整体标通过。

## 调度

Agent prompt 给出：`KEEL_PROFILE` 绝对路径、阶段、输入、输出、完成 tag。Agent 读 `state.json.plan_path` 索引，只加载指定功能 MD 及明确引用的共享章节，不展开无关功能或依赖全文。按索引依赖安排 slice，只传 slug、路径和必要依赖，不拼接全量 MD。Agent 写 progress，完成一个阶段后返回，不互相通信。

主会话收到结果后依次校验完成 tag、artifact 和 git commit，再更新 `state.json`。每个阶段使用新 Agent 执行；完成后结束当前执行。

## 进度与恢复

读取追加式 `progress.tsv` 的最新记录向用户报告状态；旧 run 读取 state/profile 中配置的 `progress.events`。审查类阶段 5 分钟、构建/修复阶段 15 分钟无有效进度时检查 Agent；卡住或失联则结束旧执行并从磁盘状态启动新执行。每阶段每角色最多恢复 2 次，超过后置为 `PAUSED`。

## 门禁

- 只消费当前 artifact，不扫描历史版本。恢复旧 run 时先校验其 plan.md；旧格式须重新生成计划并新建 run，不自动拼接或迁移历史输入。
- 运行中的执行 artifact 缺失或格式错误时定向重做一次；再次失败计入恢复次数。索引或所引用功能文档缺失不重做，直接停止并返回 Plan 阶段。
- 只记录 Builder 本轮新 commit，不审查或提交用户无关改动。
- QA `REJECTED` 阻断；非阻断观察只汇总。
- 除 Builder 代码 commit 和 CallChain 文档 commit 外，不自动 stage、merge、squash、push 或清理历史。
