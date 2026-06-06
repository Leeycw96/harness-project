# Harness

Harness 是一组面向 AI Coding CLI 的 skills + agent/role 手册,用于 Builder + QA 多 pane 编排。

v1.2.0 开始仓库同时维护两套运行时:

- `claude-code/`:Claude Code 版,部署到目标项目 `.claude/`
- `codex/`:Codex 版,部署到目标项目 `.codex/`

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
└── codex/                              # Codex runtime
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

Claude Code 版保持旧命令兼容:

```bash
cd /path/to/your/project
harness backend
# 等价于:
harness claude-code backend
```

Codex 版显式指定 runtime:

```bash
cd /path/to/your/project
harness codex backend
# 或:
harness --runtime codex backend /path/to/your/project
```

部署后:

```
.claude/ 或 .codex/
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

## Runtime 差异

Claude Code 版使用 `.claude/agents/*.md` frontmatter 和 `claude --agent ...` 启动 Builder/QA,并安装 PostCompact hook 提醒 agent 回查手册。

Codex 版使用普通 `codex` CLI pane。`harness-backend` skill 启动两个 Codex 会话后,通过初始 prompt 注入 `harness-builder` / `harness-qa` 角色,让它们读取 `.codex/agents/*` 手册并通过 `.harness/iterations/<branch>/run-N/conversation/` 落盘通信。

## 部署行为

- `harness <mode> [target-dir]` 默认部署 Claude Code 版到 `.claude/`
- `harness codex <mode> [target-dir]` 部署 Codex 版到 `.codex/`
- 同名文件直接覆盖
- 通过 `<app-dir>/.harness/installed-manifest` 清理上次由 harness 部署、但本次源里已不存在的旧文件
- 始终包含 `common/` 与 `harness-plan/`

## 开发与验证

常用验证命令:

```bash
bash -n bin/harness
find claude-code/common codex/common common claude-proxy -type f -name '*.sh' -exec bash -n {} \;
tmp=$(mktemp -d)
bin/harness backend "$tmp"
bin/harness codex backend "$tmp"
rm -rf "$tmp"
```

对 `bin/harness` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。
