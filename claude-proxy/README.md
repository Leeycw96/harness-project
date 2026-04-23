# claude-proxy

在同一台机器上并行运行多个 **Claude Code** 会话，每个会话可切换到不同的 coding plan（官方订阅 / Kimi / GLM / Qwen / MiniMax / …）。公共 settings 复用，plan 特有字段（如 `env`、`model`）单独维护。

## 工作原理

- 每个 plan 一个 JSON 文件放在 `plans/<name>.json`，只写该 plan 特有字段（至少是 `env`）。
- `common.json` 存放所有 plan 共享的 Claude Code settings（如 `enabledPlugins`、`statusLine`、`teammateMode` 等）。
- Launcher 深合并 `common.json` + `plans/<plan>.json`，把合并结果中的 `env.*` 注入进程环境，其余字段写入临时 `settings.json`，通过 `claude --settings <file>` 叠加生效。
- 每个 plan 生成一个 zsh 函数 `claude4<plan>`，自动附加 `--dangerously-skip-permissions`。
- 原生 `claude` 命令不被代理，保持官方订阅 + 默认权限校验。

## 前置依赖

- macOS / Linux + `zsh`
- [`claude`](https://docs.claude.com/en/docs/claude-code) CLI 已安装并在 `PATH` 中
- `jq`（`brew install jq`）

## 目录结构

```
claude-proxy/
├── common.json              # 公共 Claude Code settings
├── plans/
│   ├── minimax.json         # 各 plan 特有配置
│   ├── kimi.json
│   ├── glm.json
│   └── qwen.json
├── claude-proxy.sh          # 核心 launcher
├── install.sh               # 生成 aliases.zsh
├── aliases.zsh              # 自动生成，供 ~/.zshrc source
└── README.md
```

## 使用步骤

### 1. 填写各 plan 的 token

打开 `plans/<plan>.json`，把 `ANTHROPIC_AUTH_TOKEN` 填成你从对应厂商获取的 token：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-xxxxxxxxxxxxxxxx",
    "ANTHROPIC_BASE_URL": "https://api.moonshot.cn/anthropic",
    ...
  }
}
```

### 2. （可选）调整公共配置

编辑 `common.json` 修改所有 plan 共享的默认值，比如 `effortLevel`、`enabledPlugins`、`statusLine` 等。

### 3. 生成命令

```bash
./install.sh
```

产出 `aliases.zsh`，并打印已登记的命令列表。

### 4. 挂到 shell

在 `~/.zshrc` 中追加（仅需一次）：

```zsh
source "/absolute/path/to/claude-proxy/aliases.zsh"
```

然后重新加载：

```bash
exec zsh
```

### 5. 启动会话

```bash
claude             # 官方订阅（未被代理，默认权限校验）
claude4minimax     # MiniMax plan
claude4kimi        # Kimi plan
claude4glm         # GLM plan
claude4qwen        # Qwen plan
```

所有 `claude4*` 命令默认以 `--dangerously-skip-permissions` 启动；原生 `claude` 保持官方行为。多个命令可以在不同终端同时运行，互不干扰。

## 新增一个 plan

1. 在 `plans/` 下新建 `<name>.json`，至少包含 `env`：
   ```json
   {
     "env": {
       "ANTHROPIC_AUTH_TOKEN": "...",
       "ANTHROPIC_BASE_URL": "..."
     },
     "model": "..."
   }
   ```
2. 重新生成命令：`./install.sh`
3. `exec zsh` 重载别名即可使用 `claude4<name>`

可选字段：
- 任何 Claude Code `settings.json` 字段（plan 中的值会覆盖 `common.json` 中的同名字段）
- `_proxy.command`：自定义命令名，覆盖默认的 `claude4<name>`

## 常见问题

**Q: 临时 `settings.json` 文件放在哪？**
A: 每次启动创建在 `$TMPDIR/claude-proxy-<plan>.xxxxxx/settings.json`，会话退出（含 Ctrl-C / TERM / HUP）时自动清理。

**Q: 会不会覆盖我 `~/.claude/settings.json`？**
A: 不会。`--settings` 只是作为额外一层叠加，原有 user/project/local settings 仍然生效，plan 配置优先级更高。

**Q: 如何让 `claude` 也走某个 plan？**
A: 直接 `source` 对应 plan 产生的环境变量即可，或用 `env` 前缀临时注入；不建议把原生 `claude` 也包起来，这样会失去"官方订阅"的清晰通道。
