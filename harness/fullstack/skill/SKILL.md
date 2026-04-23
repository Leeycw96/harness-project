---
name: harness
description: 协调 Planner、Builder、QA 三个 Agent 完成长时间运行应用开发
invocation: /harness
---

# Harness 编排 Skill

**触发方式**: `/harness <用户需求>`

## tmux 布局

在同一 window 中创建 3 个 pane：

```
┌─────────┬─────────┬─────────┐
│ Planner │ Builder │   QA    │
│  pane   │  pane   │  pane   │
└─────────┴─────────┴─────────┘
```

- **当前 pane**: skill 协调器
- **其他 3 个 pane**: 各运行一个 agent

## 启动流程

当 skill 被触发时：

1. **创建 Agent pane**: 执行 `scripts/start-agents.sh`
   - 创建 3 个新 pane
   - 分别启动 harness-planner、harness-builder、harness-qa

2. **发送用户需求给 Planner**:
   - 将用户需求发送给 planner pane

## Agent 生命周期管理

**主会话职责**：仅管理 agent 的启动和停止，不监控 agent 内部状态或交互。

### 启动
1. 执行 `scripts/start-agents.sh` 创建 3 个 tmux pane
2. 分别启动 harness-planner、harness-builder、harness-qa
3. 将用户需求发送给 Planner pane

### 停止
**任务完成后**，必须执行清理：
1. 执行 `scripts/stop-agents.sh` 终止所有 3 个 agent pane
2. 主会话返回交互状态，**不等待 agent 后续消息**

## Agent 间自行交互

Agent 之上的通信由各 agent **自行负责**，主会话不参与：
- Planner → Builder: Planner 产出 `plan.md` 后自行通知 Builder
- Builder ↔ QA: 两者自行迭代，最多 3 次
- 所有交互通过 tmux pane 消息完成

**主会话在启动 agents 后即可返回**，后续由 agents 自行完成剩余工作。

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `start-agents.sh` | 在当前 window 创建 3 个 agent pane |
| `stop-agents.sh` | 终止所有 agent pane，清理 tmux 会话 |
| `send-to-planner.sh <需求>` | 向 Planner 发送用户需求 |
| `send-message.sh <target> <msg>` | Agent 间发送消息 |

## 强制规则

- Builder 必须先设计方案，QA 确认后才能编码
- 最多 3 次迭代
- QA 拥有最终否决权

## 可观测性

所有交互写入文件：
- `plan.md` (Planner 产出)
- `build-scope.md` (Builder 产出)
- `{代码文件}` (Builder 产出)
- `acceptance/{功能模块}/` (QA 验收留痕，包含 scripts/ 和 screenshots/)
