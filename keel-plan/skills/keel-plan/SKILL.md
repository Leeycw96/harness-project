---
name: keel-plan
description: 编排需求调研、方案起草与用户审阅，生成按功能拆分的执行文档和同源 HTML。
user-invocable: true
---

# Keel Plan

流程：调研 → 用户决策 → 起草 → 检查与渲染 → 用户审阅 → 修订或交付。
主会话负责沟通、调度和交付，Planner 负责调研与方案设计。

## 调研

主会话将需求、项目目录与手册（AGENTS.md，缺失用 README.md）、相关代码和流程资料、已有方案与决定交给 `keel-planner`。Spec 为 `.codex/common/refs/keel-plan-spec.md` 和 `.codex/common/refs/keel-business-flow-spec.md`。

请 Planner 核实现状、本期变化、影响范围及 Spec 的适用条件，提出功能目标、验收结果、必要取舍和待决问题，并返回证据。此步为只读调研；资料不足时由主会话补充资料或安排继续调研。

## 用户决策

主会话根据调研结果确认需要用户决定的范围、业务规则和关键技术选择，并确认哪些重点功能生成时序图（部分、全部或不生成）。沿用已有明确决定；可从项目核实的问题交回调研。资料充分且关键选择明确后起草。

## 起草与修订

主会话调度 `keel-planner`，沿用调研步骤的两项 Spec，提供调研证据、已确认目标与选择、计划名称和源文件范围。请其生成 `.keel/plans/<name>.md`、对应功能文档和同名 `.review.md`，按 Spec 落实适用的必需内容。

可按需参考 `.agents/skills/keel-plan/assets/plan-template.md`、`.agents/skills/keel-plan/assets/plan-review-template.md` 及关联功能示例；局部调整和合约设计分别参考 `.agents/skills/keel-plan/assets/incremental-example.md`、`.agents/skills/keel-plan/assets/contract-example.md`。示例事实替换为本项目事实。

修订时仍由 Planner 使用相同 Spec，接收本次反馈与受影响源文件，返回修改结果及未决问题。

## 检查与渲染

主会话按本次目标与 Spec 检查源文档，内容缺口交回 Planner 修订；通过后在项目根运行：

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh ".keel/plans/<name>.md" ".keel/plans/<name>.html"
```

脚本组合并校验文档，需要 Python 3；含图时需要本地 PlantUML，或 KEEL_PLANTUML_JAR 与 Java。依赖或图语法有误时修正后重试一次；仍失败则保留源文件并报告未完成。

## 用户审阅与交付

主会话展示摘要和 HTML。收到反馈后返回“起草与修订”，修改源文档并重渲染同一路径；用户明确确认最终 HTML 后，交付 HTML、索引及功能目录，供 `/keel-dev` 执行。

## 调度与恢复

使用原生 subagent，默认 `keel-planner`；A/S 可按本次任务替换，缺少所需能力或资料时报告。每次给 Agent 当前任务、Spec、必要资料和允许写入范围，路径转绝对；任务引用为 `.agents/skills/keel-plan/SKILL.md#调研` 或 `.agents/skills/keel-plan/SKILL.md#起草与修订`。Agent 完成当前任务并返回，主会话处理决策和流程衔接。

恢复时沿用已有证据、源文档和仍适用的用户决定，从未完成步骤继续；最终审阅未确认或渲染未成功时保留在 Plan。
