---
name: harness-backend
description: 协调 Backend Planner、Builder、QA 三个 Agent 完成已有后端项目的开发任务
invocation: /harness-backend
---

# Harness Backend 编排 Skill

**触发方式**: `/harness-backend <后端需求>`

## 定位

针对**已有后端项目**的开发场景，轻量、实用、不过度设计。

## tmux 布局

在同一 window 中创建最多 3 个 pane（根据场景按需启动）：

```
┌─────────┬─────────┬─────────┐
│ Planner │ Builder │   QA    │
│  pane   │  pane   │  pane   │
└─────────┴─────────┴─────────┘
```

## 场景模式

| 模式 | 启动 Agent | 适用场景 |
|------|-----------|----------|
| 完整模式 | Planner + Builder + QA | 新功能、重构 |
| 轻量模式 | Builder + QA | Bug 修复、小改动 |
| 极简模式 | Builder | 简单改动，单次交互 |

## Agent 生命周期管理

**主会话职责**：仅管理 agent 的启动和停止，不监控 agent 内部状态或交互。

### 启动
1. 根据场景模式，执行对应脚本启动所需 agent pane
2. 将需求发送给 Planner（或直接发给 Builder）

### 停止
**任务完成后**，必须执行清理：
1. 执行 `scripts/stop-agents.sh` 终止所有 agent pane
2. 主会话返回交互状态，**不等待 agent 后续消息**

## Agent 间自行交互

Agent 之上的通信由各 agent **自行负责**，主会话不参与：
- Planner → Builder: Planner 产出 `backend-tasks.md` 后自行通知 Builder
- Builder ↔ QA: 两者自行迭代

**主会话在启动 agents 后即可返回**，后续由 agents 自行完成剩余工作。

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `start-all.sh` | 启动 Planner + Builder + QA 三个 agent |
| `start-builder-qa.sh` | 启动 Builder + QA（轻量模式） |
| `start-builder.sh` | 只启动 Builder（极简模式） |
| `stop-agents.sh` | 终止所有 agent pane，清理 tmux 会话 |

## 与 harness (新项目模式) 的区别

| 方面 | harness | harness-backend |
|------|---------|-----------------|
| 目标场景 | 新项目从零开发 | 已有项目迭代开发 |
| Planner | 产出完整产品规划 | 只需拆解任务 |
| 方案设计 | 必须 build-scope.md | 小改动跳过 |
| Git 工作流 | 无 | 有（分支、commit） |
| Agent 数量 | 固定 3 个 | 按需启动 |

## 验收留痕

所有验收材料放在 `acceptance/{功能模块}/` 目录下，包含：
- `README.md` - 验收报告
- `test-results.txt` - 测试执行结果
- `scripts/test.sh` - 一键执行测试脚本
