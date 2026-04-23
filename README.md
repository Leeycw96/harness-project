# Harness CLI

Harness 是一个 Claude Code 的多 Agent 编排工具，支持 Fullstack 和 Backend 两种模式。

## 目录结构

```
harness/
├── bin/
│   └── harness          # CLI 命令
├── fullstack/           # 新项目全栈开发
│   ├── agents/
│   │   ├── planner.md   # 产品规划 Agent
│   │   ├── builder.md   # 全栈构建 Agent
│   │   └── qa.md        # 验收测试 Agent
│   └── skill/
│       └── SKILL.md     # /harness 指令
└── backend/             # 已有后端项目开发
    ├── agents/
    │   ├── backend-planner.md  # 后端任务拆解 Agent
    │   ├── backend-builder.md  # 后端构建 Agent
    │   └── backend-qa.md       # 后端验收 Agent
    └── skill/
        └── SKILL.md            # /harness-backend 指令
```

## 安装

### 方法 1: 直接添加到 PATH

```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
export PATH="/Users/yangchengwu/developer/harness/harness-project/bin:$PATH"
```

### 方法 2: 使用 install 脚本

```bash
cd /Users/yangchengwu/developer/harness/harness-project
./install.sh
```

## 使用

### 在新项目中部署 Harness

```bash
# 进入你的项目目录
cd /path/to/your/project

# 部署 backend harness（适用于已有后端项目）
harness backend

# 部署 fullstack harness（适用于新项目）
harness fullstack
```

### 更新 Harness

```bash
# 直接运行原命令即可更新
harness backend      # 更新 backend harness
harness fullstack    # 更新 fullstack harness

# 强制更新，不提示确认
harness backend -f
harness fullstack -f
```

### 检查状态

```bash
harness status
```

### 查看帮助

```bash
harness --help
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `harness backend` | 部署或更新 Backend Harness |
| `harness fullstack` | 部署或更新 Fullstack Harness |
| `harness status` | 检查当前项目的 Harness 状态 |
| `harness -h` | 显示帮助信息 |
| `-f, --force` | 强制覆盖，不提示确认 |

## 使用流程

### Backend 模式（已有后端项目）

1. 进入后端项目目录
2. 运行 `harness backend`
3. 在 Claude Code 中使用 `/harness-backend <需求>`

### Fullstack 模式（新项目）

1. 进入项目目录
2. 运行 `harness fullstack`
3. 在 Claude Code 中使用 `/harness <需求>`

## Agent 说明

### Fullstack Agents

- **Planner**: 将需求展开为详尽的产品规格，定义用户故事和验收标准
- **Builder**: 执行代码构建，实现功能
- **QA**: 验收测试，确保质量

### Backend Agents

- **Backend Planner**: 理解已有项目代码结构，将需求拆解为可执行的后端任务
- **Backend Builder**: 在已有项目中执行后端开发任务
- **Backend QA**: 后端代码验收测试
