---
name: harness-plan
description: 读取项目上下文，逐项澄清需求边界和验收标准，生成可供 Harness Backend 消费的 XML plan。
user-invocable: true
---

# Harness Plan

唯一产物是 `.harness/plans/<name>.md`。不要生成 spec、实现计划或额外文件。

## 门禁

- 先读项目根 `AGENTS.md`，不存在时读 `CLAUDE.md`，再检查相关代码入口、数据模型、测试和 `.harness/call-chain/`。
- 只询问会改变范围或验收标准的问题，一次一个。
- 未确认本次范围和每个 feature 的验收标准前，不写 plan。
- 不把交互依赖、未来能力或文档中顺带提及的内容写成本次开发。

## 流程

1. 用 2–4 句话说明已识别的项目背景，并提出最关键问题。
2. 将内容分为“本次开发、交互依赖、Out of scope”，让用户确认。
3. 将本次开发拆成稳定、唯一的英文 kebab-case feature slug，并确认清单。
4. 为每个 feature 确认可测试标准：触发动作、预期响应、关键副作用和重要异常分支。
5. 确认项目已有的技术、权限、事务、幂等、性能和依赖约束；不要擅自新增技术决策。
6. 读取 `.claude/skills/harness-plan/assets/plan-template.xml`，写入 `.harness/plans/<name>.md`。

## XML 契约

- 根节点为 `<plan>`。
- `<context>` 用 1–3 句话说明动机。
- 每个 `<feature>` 有唯一 `slug`、`description` 和非空 `acceptance-criteria`。
- 每个 `<criterion>` 必须能通过命令、请求、状态或副作用验证；禁止“功能正常、符合预期、保证稳定”。
- `<out-of-scope>` 同时记录明确不做项和非本轮开发的交互依赖。
- `<constraints>` 只写已确认或项目明确存在的约束。
- `<dependencies>` 使用 `ready` 或 `not-ready`。
- XML 标签外不写正文。

## 完成前检查

检查范围、slug、验收标准、依赖、约束和 XML 可解析性。需要用户决策时继续一次只问一个问题；否则展示完整 XML，请用户确认。确认后报告 plan 路径，并提示选择 `/harness-backend-fast` 或 `/harness-backend`。
