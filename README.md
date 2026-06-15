# Harness

Harness 是一组面向 Codex App 的 skills + custom agent 手册,用于通过主会话编排 Builder、QA 和 CodeReview subagents 完成长任务后端构建。

v2 开始只支持 Codex App subagent 工作流。已移除 Claude Code、Codex CLI tmux、pane/send-keys 和 runtime-specific 源目录。

## 目录结构

```text
harness-project/
├── bin/harness                         # 部署 CLI
├── install.sh                          # 把 bin/ 写入 PATH
├── common/                             # 部署到 .codex/common/
├── harness-plan/                       # /harness-plan skill
└── harness-backend/                    # /harness-backend skill + agents
```

每个模式遵循统一布局:

```text
harness-<mode>/
├── skills/harness-<mode>/              # skill
└── agents/                             # Codex custom agents 和角色/SOP 文档
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

```bash
cd /path/to/your/project
harness backend
# 或:
harness backend /path/to/your/project
```

部署后:

```text
.agents/
└── skills/
    ├── harness-plan/
    └── harness-backend/
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
│   └── harness-code-review.toml
└── .harness/
    └── installed-manifest
```

旧参数 `--claude-code`、`--codex-cli`、`--runtime` 已移除。直接使用 `harness <mode> [target-dir]`。

## 使用

1. 运行 `/harness-plan` 通过对话生成 `.harness/plans/<name>.md` XML plan。
2. 运行 `/harness-backend <plan-path>`。
3. 主会话会初始化 run,调度 Builder 生成 scope,调度 QA 审 scope,调度 Builder 构建,再并行调度 QA 和 CodeReview 验收。
4. 任一阻断问题都会由主会话合并为 `fix-brief.md` 后派 Builder 修复。最多 3 轮。
5. QA 通过且 CodeReview 无 P0/P1 后,本轮结束。

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

## 开发与验证

常用验证命令:

```bash
bash -n bin/harness
find common -type f -name '*.sh' -exec bash -n {} \;
tmp=$(mktemp -d)
bin/harness backend "$tmp"
find "$tmp/.agents/skills" "$tmp/.codex" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

对 `bin/harness` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。

## 部署行为

- skills 部署到 `.agents/skills/`
- agents 部署到 `.codex/agents/`
- common 部署到 `.codex/common/`
- manifest 写入 `.codex/.harness/installed-manifest`
- 同名文件直接覆盖
- 只删除上次由 manifest 记录、但本次源里已不存在的旧文件

## 安全

- Harness 不会自动 merge、squash、push 或清理 Builder commits。
- Deployment 会覆盖目标项目中的同名 Harness 文件。
