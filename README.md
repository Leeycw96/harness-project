# Harness

Harness 是一组面向 Codex App 和 Claude Code 的 skills + agent 手册,用于通过主会话编排 Builder、QA、CodeReview、CallChain 等 subagents 完成长任务后端构建。

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

`harness backend` 会同时部署 `/harness-plan`、`/harness-backend-fast`、`/harness-backend` 和 `/harness-backend-fix`。

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
    ├── harness-backend-fast/
    └── harness-backend-fix/
.codex/
├── common/
│   ├── refs/
│   └── scripts/
├── agents/
│   ├── harness-builder.md
│   ├── harness-builder-AGENTS.md
│   ├── harness-builder.toml
│   ├── harness-qa.md
│   ├── harness-qa-AGENTS.md
│   ├── harness-qa.toml
│   ├── harness-code-review.md
│   ├── harness-code-review-AGENTS.md
│   ├── harness-code-review.toml
│   ├── harness-call-chain.md
│   ├── harness-call-chain-AGENTS.md
│   ├── harness-call-chain.toml
│   ├── harness-feedback-triage.md
│   ├── harness-feedback-triage-AGENTS.md
│   └── harness-feedback-triage.toml
└── .harness/
    └── installed-manifest
```

## Claude Code 部署结果

```text
.claude/
├── skills/
│   ├── harness-plan/
│   ├── harness-backend/
│   ├── harness-backend-fast/
│   └── harness-backend-fix/
├── common/
│   ├── refs/
│   └── scripts/
├── agents/
│   ├── harness-builder.md
│   ├── harness-qa.md
│   ├── harness-code-review.md
│   ├── harness-call-chain.md
│   └── harness-feedback-triage.md
└── .harness/
    └── installed-manifest
```

## 使用

1. 运行 `/harness-plan` 通过对话生成 `.harness/plans/<name>.md` XML plan。
2. 日常小中型改动优先运行 `/harness-backend-fast <plan-path>`。
3. 高风险改动再运行 `/harness-backend <plan-path>` 走完整验收。

```text
/harness-backend-fast <plan-path>
```

fast run 只调度 Builder 和 CodeReview,不运行 QA、Scope Review 或 CallChain,是默认推荐路径,适合小范围 bugfix、局部逻辑调整、简单校验或错误处理。

```text
/harness-backend <plan-path>
```

backend run 会调度 Builder 生成 scope,调度 QA 审 scope,调度 Builder 构建,再并行调度 QA 和 CodeReview 验收,最后维护 CallChain。复杂业务流程、数据库迁移、权限审计、事务/并发、跨模块状态流转等高风险改动使用它。

```text
/harness-backend-fix <反馈>
```

`/harness-backend-fix <反馈>` 只用于 `/harness-backend` 完成后处理人工 CR/验收反馈: 它会判断反馈是否属于原 plan 内问题,成立则修复并复审,新需求则提示重新走 `/harness-plan`。fast run 暂不支持 fix。

run 目录最小结构:

```text
.harness/iterations/<branch>/run-N/
  plan.md
  profile.json
  state.json
  build-scope.md
  scope-review.md
  qa-feedback.md
  code-review.md
  fix-brief.md
  progress/
```

fast run 最小结构:

```text
.harness/iterations/<branch>/run-N/
  plan.md
  profile.json
  state.json
  code-review.md
  fix-brief.md
  progress/
```

## 开发与验证

常用验证命令:

```bash
bash -n bin/harness
find common claude-code/common -type f -name '*.sh' -exec bash -n {} \;
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
