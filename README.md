# Harness

Harness 是一组面向 AI Coding CLI/App 的 skills + agent/role 手册,用于 Builder + QA 多阶段编排。

v1.2.0 开始仓库同时维护多套运行时:

- `claude-code/`:Claude Code 版,部署到目标项目 `.claude/`
- `codex/`:Codex App 原生 subagent 版,skills 部署到目标项目 `.agents/skills/`,custom agents 部署到 `.codex/agents/`
- `codex-cli/`:Codex CLI tmux pane 版,skills 部署到 `.agents/skills/`,role/SOP 文档部署到 `.codex/agents/`

根目录下保留 v1.1.x 的 `common/`、`harness-plan/`、`harness-backend/` 等目录,用于兼容既有引用；新开发应优先改对应 runtime 目录。

## 目录结构

```
harness-project/
├── bin/harness                         # 部署 CLI
├── install.sh                          # 把 bin/ 写入 PATH
├── claude-code/                        # Claude Code runtime
│   ├── common/
│   ├── harness-plan/
│   ├── harness-backend/
│   └── harness-solidity/
├── codex/                              # Codex App runtime
│   ├── common/
│   ├── harness-plan/
│   └── harness-backend/
└── codex-cli/                          # Codex CLI tmux runtime
    ├── common/
    ├── harness-plan/
    └── harness-backend/
```

每个模式遵循统一布局:

```
harness-<mode>/
├── skills/harness-<mode>/              # skill
└── agents/                             # Claude agents 或 Codex role/SOP 文档
```

## 安装 CLI

```bash
git clone <this-repo>
cd harness-project
./install.sh
source ~/.zshrc      # 或新开一个终端
```

`install.sh` 只把 `bin/` 加入 PATH,不会部署任何 skill。

## 使用

Claude Code 版:

```bash
cd /path/to/your/project
harness --claude-code backend
# 或:
harness backend --claude-code
```

Codex 版:

```bash
cd /path/to/your/project
harness --codex backend
# 或:
harness backend --codex /path/to/your/project
```

Codex CLI tmux 版:

```bash
cd /path/to/your/project
harness --codex-cli backend
# 或:
harness backend --codex-cli /path/to/your/project
```

Claude Code 部署后:

```
.claude/
├── common/scripts/
├── skills/
│   ├── harness-plan/
│   └── harness-backend/
└── agents/
    ├── harness-builder.md
    ├── harness-builder-AGENTS.md
    ├── harness-qa.md
    └── harness-qa-AGENTS.md
```

Codex App / Codex CLI 部署后:

```
.agents/
└── skills/
    ├── harness-plan/
    └── harness-backend/
.codex/
├── common/scripts/
├── agents/
│   ├── harness-builder.md
│   ├── harness-builder-AGENTS.md
│   ├── harness-builder.toml      # Codex App runtime only
│   ├── harness-qa.md
│   ├── harness-qa-AGENTS.md
│   └── harness-qa.toml           # Codex App runtime only
└── .harness/
    └── installed-manifest
```

## Runtime 差异

Claude Code 版使用 `.claude/agents/*.md` frontmatter 和 `claude --agent ...` 启动 Builder/QA,并安装 PostCompact hook 提醒 agent 回查手册。

Codex App 版使用 Codex 原生 skills 与 custom subagents。skills 按官方目录放在 `.agents/skills/`;`harness-backend` skill 作为 orchestrator,按阶段 spawn `.codex/agents/harness-builder.toml` 与 `.codex/agents/harness-qa.toml`,让它们读取对应手册并通过 `.harness/iterations/<branch>/run-N/{signals,conversation}/` 落盘通信。Builder/QA 不要求常驻,每轮从磁盘工件恢复上下文。

Codex CLI tmux 版使用两个普通 `codex` TUI pane 长驻协作。Codex CLI 官方没有 `codex --agent` 启动参数,所以 harness 通过初始 prompt 注入 `harness-builder` / `harness-qa` 角色,并用 `.codex/common/scripts/harness-common.sh` 进行 tmux send-keys 与 conversation 落盘通信。这个版本适合需要实时观察 Builder/QA 工作内容的场景。默认启动命令是 `codex --dangerously-bypass-approvals-and-sandbox`,体验接近 Claude Code 的 `bypassPermissions`;如需保守权限,启动时选择 workspace-write 模式或自定义 `HARNESS_CLI`。

## 部署行为

- `harness --claude-code <mode> [target-dir]` 部署 Claude Code 版到 `.claude/`
- `harness --codex <mode> [target-dir]` 部署 Codex App 版:skills 到 `.agents/skills/`,agents/common/manifest 到 `.codex/`
- `harness --codex-cli <mode> [target-dir]` 部署 Codex CLI tmux 版:skills 到 `.agents/skills/`,agents/common/manifest 到 `.codex/`
- 未指定 `--claude-code`、`--codex` 或 `--codex-cli` 时直接报错,避免误装 runtime
- 同名文件直接覆盖
- 通过 `<runtime-state-dir>/.harness/installed-manifest` 清理上次由 harness 部署、但本次源里已不存在的旧文件；Codex 的 manifest 位于 `.codex/.harness/installed-manifest`
- 始终包含 `common/` 与 `harness-plan/`

## 开发与验证

常用验证命令:

```bash
bash -n bin/harness
find claude-code/common codex/common codex-cli/common common claude-proxy -type f -name '*.sh' -exec bash -n {} \;
tmp=$(mktemp -d)
bin/harness --claude-code backend "$tmp"
bin/harness --codex backend "$tmp"
bin/harness --codex-cli backend "$tmp"
rm -rf "$tmp"
```

对 `bin/harness` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。
