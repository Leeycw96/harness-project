# Harness

Harness 是一组面向 Codex App 和 Claude Code 的 skills + agent 手册,用于通过主会话编排 Builder、QA、CallChain 等 subagents 完成长任务后端构建。Claude Code runtime 仍保留独立 CodeReview。

当前维护两套 runtime:

- Codex App: 根级 `common/`、`harness-plan/`、`harness-backend/`
- Claude Code: `claude-code/common/`、`claude-code/harness-plan/`、`claude-code/harness-backend/`

两套 runtime 源码、部署目录和 manifest 相互隔离。

## 目录结构

```text
harness-project/
├── bin/harness                         # 部署 CLI
├── install.sh                          # 把 bin/ 写入 PATH
├── common/                             # Codex App common,部署到 .codex/common/
├── harness-plan/                       # Codex App /harness-plan skill
├── harness-backend/                    # Codex App backend skills + agents
└── claude-code/                        # Claude Code runtime
    ├── common/                         # 部署到 .claude/common/
    ├── harness-plan/                   # Claude Code /harness-plan skill
    └── harness-backend/                # Claude Code backend skills + agents
```

Codex App 模式保留现有布局:

```text
harness-<mode>/
├── skills/harness-<mode>/              # skill
└── agents/                             # Codex custom agents、TOML 和角色/SOP 文档
```

Claude Code 模式使用 Claude 原生布局:

```text
claude-code/harness-<mode>/
├── skills/harness-<mode>/              # .claude/skills/<name>/SKILL.md
└── agents/                             # .claude/agents/<agent>.md
```

## 安装 CLI

```bash
git clone <this-repo>
cd harness-project
./install.sh
source ~/.zshrc      # 或新开一个终端
```

`install.sh` 只把 `bin/` 加入 PATH,不会部署任何 skill。

## 部署

必须显式选择 runtime。默认部署到当前目录:

```bash
cd /path/to/your/project
harness backend --codex
harness backend --claude-code
```

也可以指定目标目录:

```bash
harness backend --codex /path/to/your/project
harness backend --claude-code /path/to/your/project
```

`harness backend` 会同时部署 `/harness-plan`、`/harness-backend-fast` 和 `/harness-backend`。

旧格式不再支持:

- `harness backend`
- `harness backend /path/to/project`
- `harness --codex backend`
- `harness --claude-code backend`
- `harness --runtime ...`
- `harness ... --codex-cli`

## Codex App 部署结果

```text
.agents/
└── skills/
    ├── harness-plan/
    ├── harness-backend/
    └── harness-backend-fast/
.codex/
├── common/
│   ├── refs/
│   └── scripts/
├── agents/
│   ├── harness-builder.md
│   ├── harness-builder.toml
│   ├── harness-qa.md
│   ├── harness-qa.toml
│   ├── harness-call-chain.md
│   └── harness-call-chain.toml
└── .harness/
    └── installed-manifest
```

## Claude Code 部署结果

```text
.claude/
├── skills/
│   ├── harness-plan/
│   ├── harness-backend/
│   └── harness-backend-fast/
├── common/
│   ├── refs/
│   └── scripts/
├── agents/
│   ├── harness-builder.md
│   ├── harness-qa.md
│   ├── harness-code-review.md
│   └── harness-call-chain.md
└── .harness/
    └── installed-manifest
```

## 使用

1. 在 Codex App 运行 `/harness-plan`，通过对话生成相互关联的 `.harness/plans/<name>.md` XML 需求计划和 `.harness/plans/<name>-implementation.md` Markdown 代码改造计划。
2. 日常小中型改动优先运行 `/harness-backend-fast <plan-path>`。
3. 高风险改动再运行 `/harness-backend <plan-path>` 走完整验收。

```text
/harness-backend-fast <plan-path>
```

Codex App 的 Plan 阶段会先读取相关 CallChain 和实际代码，确认当前流程、目标流程、修改地图与关键技术决策。项目内部调研始终执行；只有在缺少既定方案且技术选型会显著影响实现时，才先征得用户同意后进行外部调研。选型未确认时暂停，不把决策留给 Builder。

Codex App 的 fast run 只调度 Builder 和 QA，不运行 CallChain，是默认推荐路径，适合小范围 bugfix、局部逻辑调整、简单校验或错误处理。Builder 与 QA 均消费两份已确认计划，QA 同时验证目标业务流程、修改边界和共享代码质量红线。

```text
/harness-backend <plan-path>
```

Codex App 的 backend run 在 Preflight 后直接由 Builder 按代码改造计划构建，再由 QA 验收，最后按需维护 CallChain。复杂业务流程、数据库迁移、权限审计、事务/并发、跨模块状态流转等高风险改动使用它。Codex App 不再生成或审查 build-scope；方案和边界必须在 Plan 阶段完成确认。

Claude Code runtime 保持原流程：fast 使用 Builder + CodeReview，full 使用 QA + CodeReview 双门禁。

CallChain 已启用按需调度：主会话明确判断没有外部入口、异步推进点或多阶段生命周期变化时记录 `noop` 并跳过 Agent；存在变化或不确定时记录 `run` 并保持独立 CallChain 评审。受控评测结果使用 `scripts/check-call-chain-controlled-eval.sh` 复核。

full 和 fast 都会在本轮评审发现阻断问题时自动进入内部修复循环。run 完成后的新反馈使用新的 plan/backend run；范围变化重新运行 `/harness-plan`。

run 目录最小结构:

```text
.harness/iterations/<branch>/run-N/
  plan.md
  implementation-plan.md
  state.json
  qa-feedback.md
  fix-brief.md
  call-chain-review.md
  progress.tsv
```

fast run 最小结构:

```text
.harness/iterations/<branch>/run-N/
  plan.md
  implementation-plan.md
  state.json
  qa-feedback.md
  fix-brief.md
  progress.tsv
```

新 run 的静态契约和运行状态统一保存在 `state.json`，其中同时记录 `plan_path` 和 `implementation_plan_path`；所有 Agent 心跳追加到 `progress.tsv`。缺少代码改造计划的旧 run 不兼容本流程，需要重新运行 `/harness-plan`。

## 开发与验证

常用验证命令:

```bash
bash -n bin/harness
find common claude-code/common -type f -name '*.sh' -exec bash -n {} \;
scripts/check-runtime-parity.sh
scripts/check-planning-contract.sh
scripts/harness-metrics.sh
scripts/check-slimming-targets.sh
scripts/check-call-chain-controlled-eval.sh
scripts/summarize-call-chain-shadow.sh --help
tmp=$(mktemp -d)
bin/harness backend --codex "$tmp"
bin/harness backend --claude-code "$tmp"
find "$tmp/.agents/skills" "$tmp/.codex" "$tmp/.claude" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

对 `bin/harness` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。

## 部署行为

- Codex skills 部署到 `.agents/skills/`
- Codex agents 部署到 `.codex/agents/`
- Codex common 部署到 `.codex/common/`
- Codex manifest 写入 `.codex/.harness/installed-manifest`
- Claude Code skills 部署到 `.claude/skills/`
- Claude Code agents 部署到 `.claude/agents/`
- Claude Code common 部署到 `.claude/common/`
- Claude Code manifest 写入 `.claude/.harness/installed-manifest`
- 同名文件直接覆盖
- 只删除当前 runtime 上次由 manifest 记录、但本次源里已不存在的旧文件

## 安全

- Harness 不会自动 merge、squash、push 或清理 Builder commits。
- Deployment 会覆盖目标项目中的同名 Harness 文件。
