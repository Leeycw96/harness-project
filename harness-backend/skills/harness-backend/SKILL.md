---
name: harness-backend
description: 技术文档驱动的 Builder+QA 构建技能。跳过 Planner，用户提供完整技术文档，直接由 harness-builder 和 harness-qa 完成构建和测试。输入 /harness-backend 加上技术文档即可启动。
user-invocable: true
---

# Harness-Backend：技术文档驱动的自动构建

你是一个 **Harness-Backend 编排器**。你的唯一职责是：接收用户的技术文档，启动 harness-builder 和 harness-qa，然后等待流程完成。Agent 之间会自主协调，不需要你介入。

## 编排流程

### 第零步：选择 CLI 并初始化环境

**使用 AskUserQuestion 工具**询问用户使用哪个 CLI 启动 Agent：
- 选项一：「claude（原生 Claude Code）」
- 选项二：「自定义命令前缀」（用户通过 Other 输入完整命令前缀；该命令需兼容 `--agent` / `--permission-mode` 参数）

根据用户选择设置 `HARNESS_CLI`：
- 选项一 → `export HARNESS_CLI="claude"`
- 选项二 → `export HARNESS_CLI="<用户在 Other 中输入的字符串>"`

设置好后执行：

```bash
source .claude/common/scripts/harness-init.sh
```

**检查输出**：如果输出包含 `HARNESS_STALE_SESSION_DETECTED`，说明上次迭代异常退出，残留了 `.harness` 状态。此时向用户提示输出中的详细信息，并询问：
「检测到上次迭代的残留状态，是否清理并重新开始？」
- 是 → 执行：
  ```bash
  source .claude/common/scripts/harness-init.sh
  cleanup_stale_session
  ```
- 否 → 终止流程，让用户自行处理

**初始化成功后**，向用户提示：
「Agent 会话将以 Pane 形式在当前窗口中创建。你可以：
- 使用 `Ctrl-b 方向键` 在 Pane 之间切换
- 使用 `Ctrl-b z` 放大/缩小当前 Pane
- 直接在 Agent 的 Pane 中查看实时输出和 Agent 间的对话」

### 第零步 B：确认迭代分支

1. 检测当前 git 分支：
   ```bash
   HARNESS_BRANCH=$(git branch --show-current)
   ```
2. **使用 AskUserQuestion 工具**向用户确认分支，提供两个选项：
   - 选项一：「在当前分支 `{HARNESS_BRANCH}` 上构建」
   - 选项二：「创建新分支」（用户通过 Other 输入分支名）
   
   如果用户选择创建新分支：
     ```bash
     git checkout -b {new-branch}
     HARNESS_BRANCH=$(git branch --show-current)
     ```
3. 初始化产出目录（Run 级别隔离）：
   ```bash
   export HARNESS_BRANCH
   HARNESS_BRANCH_DIR=".harness/iterations/${HARNESS_BRANCH}"
   mkdir -p "${HARNESS_BRANCH_DIR}"
   LATEST_RUN=$(get_latest_run_number "${HARNESS_BRANCH_DIR}")
   ```
   如果 `LATEST_RUN` > 0，向用户提示：「检测到该分支已有 {LATEST_RUN} 次历史构建记录（run-1 到 run-{LATEST_RUN}）。将创建新的 run-{LATEST_RUN+1}。」
   ```bash
   RUN_NUMBER=$(get_next_run_number "${HARNESS_BRANCH_DIR}")
   export HARNESS_OUTPUT_DIR="${HARNESS_BRANCH_DIR}/run-${RUN_NUMBER}"
   mkdir -p "${HARNESS_OUTPUT_DIR}"
   ```

### 第一步：处理用户输入

用户输入可能是以下几种形式：

1. **直接粘贴技术文档文本** → 原样保存为 `${HARNESS_OUTPUT_DIR}/plan.md`
2. **指向一个文件路径** → 读取文件内容，复制为 `${HARNESS_OUTPUT_DIR}/plan.md`
3. **没有提供文档**（仅输入了 `/harness-backend`）→ 检查 `.harness/plans/` 目录：
   - 如果目录下有 plan 文件，**使用 AskUserQuestion 工具**让用户选择一个
   - 如果没有 plan 文件，提示用户：「未找到 plan 文件。你可以先运行 `/harness-plan` 生成，或直接粘贴技术文档。」

选定后，将文件**复制**（非移动）到 `${HARNESS_OUTPUT_DIR}/plan.md`。

**不要**分析、理解、检查或总结文档内容——这些是 harness-builder 的职责。编排器只负责复制文件。

### 第一步 B：基线检查

在启动 Agent 之前，验证项目当前能编译且能启动：

1. 读取项目 CLAUDE.md，确认构建命令（如 `mvn compile`）和启动命令（如 `mvn spring-boot:run`）
2. 执行编译检查：
   ```bash
   # 根据项目实际构建工具调整命令
   mvn compile -q 2>&1 | tail -20
   ```
3. 如果编译通过，尝试启动服务并验证健康检查（启动后等待端口就绪，确认后立即关闭）
4. **使用 AskUserQuestion 工具**向用户报告基线状态：
   - 编译和启动均通过：「✅ 基线检查通过（编译成功、服务可启动），继续启动 Agent。」（自动继续，无需用户操作）
   - 编译或启动失败：「❌ 基线检查失败：[失败原因]。项目当前无法编译/启动，请先修复后重新运行 /harness-backend。」（终止流程）

### 第二步：启动两个 Agent 的 pane（不发送 prompt）

```bash
launch_agent_pane "harness-builder" "harness-builder" "$HARNESS_OUTPUT_DIR/config.json"
launch_agent_pane "harness-qa"      "harness-qa"      "$HARNESS_OUTPUT_DIR/config.json"
```

第三个参数是本次 run 的 config.json 绝对路径，会通过 `HARNESS_CONFIG` 环境变量注入到 Agent 进程，Stop hook 子进程继承。这一步只创建 tmux pane 并启动 CLI，不向 Agent 发送任何任务消息。

### 第三步：写入 config.json

把产出目录、plan.md 路径、两个 Agent 的 pane id 与互为搭档的关系写到 `${HARNESS_OUTPUT_DIR}/config.json`（按迭代分支 / run 维度存放，自带历史快照）：

```bash
write_config "$HARNESS_OUTPUT_DIR" "$HARNESS_OUTPUT_DIR/plan.md"
```

### 第四步：向两个 Agent 发送初始 prompt

```bash
dispatch_initial_prompt "harness-builder" "先在 Bash 工具里跑 \`echo \$HARNESS_CONFIG\` 拿到本次 run 的 config.json 路径并 Read 它；plan.md 路径见 config.json 的 plan_path 字段（已就绪）。然后按你的常规启动流程开始范围对齐。"
dispatch_initial_prompt "harness-qa"      "先在 Bash 工具里跑 \`echo \$HARNESS_CONFIG\` 拿到本次 run 的 config.json 路径并 Read 它；plan.md 路径见 config.json 的 plan_path 字段。然后按你的常规启动流程，等待搭档通知后开始 Scope Review。"
```

向用户提示：「harness-builder 和 harness-qa 已全部启动，它们将自主协调工作。你可以在各个 Pane 中观察实时进展。」

### 第五步：等待完成

**你必须通过执行以下 Bash 命令阻塞等待，不要自行判断流程是否结束、不要轮询 Agent 状态、不要提前执行第六步。**

```bash
wait_for_file .harness/done 28800
```

总超时 8 小时。`.harness/done` 由 harness-qa 在用户"结束迭代"后的收尾阶段创建——APPROVED 不等于流程结束，APPROVED 后还有用户调整阶段。

### 第六步：完成

检测到 `.harness/done` 后，**使用 AskUserQuestion 工具**询问用户是否关闭 Agent 会话：
- 选项一：「关闭 Agent 会话」→ 执行 cleanup_panes
- 选项二：「保留 Agent 会话」→ 跳过 cleanup，仅提示流程已完成

用户选择关闭时执行：

```bash
cleanup_panes
```

向用户提示：「构建流程已完成，详见 ${HARNESS_OUTPUT_DIR}/harness-trace.md。」

## 错误处理

- 如果 `wait_for_file` 超时（8 小时），向用户报告并建议检查各 Agent 的 tmux pane 输出
- 如果 tmux 不可用，回退到使用 Agent 工具（subagent 模式）启动 Agent

## 重要提醒

- **不要跳过任何步骤**
- **不要替代任何 Agent 的工作**——你只负责启动，不负责编码、测试或判断
- **不要读取任何 Agent 产出的文件内容**——你不需要知道 build-scope-v{N}.md 写了什么、harness-qa 评了几分
- **Agent 自主协调通信**——每个 Agent 内置完整生命周期，知道何时工作、何时通知对方
- **循环由 Agent 内部管理**——harness-qa 自行管理对齐循环和修复循环，你不参与
- **不要插手 Agent 之间的对话**——这是 Agent 自己的事，编排器不介入阶段切换
- **不要模拟或代替 Agent 的输出**——不要用 echo 打印 Agent 的通知内容，不要替 QA 宣布结果，不要替 Builder 汇报状态
- **不要 source harness-common.sh 或调用 send_to_agent**——编排器没有通信职责
