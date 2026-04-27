# Harness

Harness 是一组 Claude Code 的 skills + agents,用于多 Agent 编排。

## 目录结构

```
harness-project/
├── skills/
│   ├── harness-plan/                 # /harness-plan 引导式需求梳理
│   │   ├── SKILL.md
│   │   └── assets/
│   │       └── plan-template.xml     # plan 文件 XML 模板
│   └── harness-backend/              # /harness-backend 后端构建编排
│       └── SKILL.md
└── agents/
    ├── harness-builder.md            # 后端构建 Agent
    └── harness-qa.md                 # 后端验收 Agent
```

## 部署

将 skills 与 agents 放到目标项目的 `.claude/`(或全局 `~/.claude/`):

- `skills/harness-plan/` → `.claude/skills/harness-plan/`(整个目录,含 `assets/`)
- `skills/harness-backend/` → `.claude/skills/harness-backend/`
- `agents/harness-builder.md`、`agents/harness-qa.md` → `.claude/agents/`

部署可用软链或复制,按需自行选择。

## 使用流程

1. **梳理需求**:在 Claude Code 中输入 `/harness-plan`,通过对话生成 `.harness/plans/<名称>.md`(XML 格式 plan 文件)。
2. **执行构建**:输入 `/harness-backend`,选择已生成的 plan 文件,由 `harness-builder` 完成实现、`harness-qa` 完成验收。

## Skill 说明

### harness-plan

扮演产品经理,通过对话把模糊想法逐步结构化为 XML 格式的 plan 文件,作为下游 builder/qa 的直接输入。详见 `skills/harness-plan/SKILL.md`。

### harness-backend

消费 `.harness/plans/<名称>.md`,驱动 builder/qa 两个 Agent 完成构建与验收闭环。详见 `skills/harness-backend/SKILL.md`。

## Agent 说明

- **harness-builder**:在已有后端项目中执行开发任务,产出代码与 `.harness/call-chain/` 调用链文件。
- **harness-qa**:基于 plan 中的 `<acceptance-criteria>` 对实现进行验收,产出 `.harness/done` 完成标记。
