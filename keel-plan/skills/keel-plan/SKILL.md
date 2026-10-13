---
name: keel-plan
description: 编排需求调研、方案起草与用户审阅，生成按功能拆分的执行文档和同源 HTML。
user-invocable: true
---

# Keel Plan

流程：调研 → 用户决策 → 起草 → 渲染 → 用户审阅 → 修订或交付。
主会话负责沟通、调度和交付，Planner 负责调研与方案设计。

## 调研

主会话调度 `keel-planner`，任务为只读调研，包含需求、项目目录与手册（AGENTS.md，缺失用 README.md）、相关代码和流程资料、已有方案与决定。Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-proposal-spec`（`.codex/common/refs/keel-proposal-spec.md#调研结果`）、`keel-business-flow-spec`（`.codex/common/refs/keel-business-flow-spec.md`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）。

请 Planner 核实现状、本期变化、影响范围及 Spec 的适用条件，提出功能目标、验收结果、必要取舍和待决问题，并简述现状。此步为只读调研；资料不足时由主会话补充资料或安排继续调研。

## 用户决策

主会话根据调研结果确认需要用户决定的范围、业务规则和关键技术选择，并确认哪些重点功能生成时序图（部分、全部或不生成）。沿用已有明确决定；可从项目核实的问题交回调研。资料充分且关键选择明确后起草。

## 起草与修订

主会话调度 `keel-planner`，沿用调研步骤的通用交付、业务流程和文档表达 Spec，方案规范改用 `keel-proposal-spec` 全文（`.codex/common/refs/keel-proposal-spec.md`），另给 `keel-code-change-spec`（`.codex/common/refs/keel-code-change-spec.md`）。任务包含调研结果、已确认目标与选择、计划名称和源文件范围；请其生成 `.keel/plans/<name>.md`、对应功能文档和同名 `.review.md`，按 Spec 落实适用的必需内容。

可按需提供 `.agents/skills/keel-plan/assets/plan-template.md`、`.agents/skills/keel-plan/assets/plan-review-template.md` 及关联功能示例；局部调整、JSON 结构和合约设计示例分别为 `.agents/skills/keel-plan/assets/incremental-example.md`、`.agents/skills/keel-plan/assets/json-example.md`、`.agents/skills/keel-plan/assets/contract-example.md`。示例事实替换为本项目事实。

修订时仍由 Planner 使用相同 Spec，接收本次反馈与受影响源文件，返回修改结果及未决问题。

## 渲染

收到当前 Planner 返回的源文档后，主会话直接在项目根运行：

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh ".keel/plans/<name>.md" ".keel/plans/<name>.html"
```

脚本组合并校验文档，需要 Python 3；含图时需要本地 PlantUML，或 KEEL_PLANTUML_JAR 与 Java。校验或渲染失败时，按错误安排 Planner 修订或补齐依赖；无法完成时保留源文件并说明阻碍。

## 用户审阅与交付

主会话展示摘要和 HTML。收到反馈后返回“起草与修订”，修改源文档并重渲染同一路径；用户明确确认最终 HTML 后，交付 HTML、索引及功能目录，供 `/keel-dev` 执行。

## 调度

使用原生 subagent，默认 `keel-planner`；主会话选择或替换 Agent/Spec，核对能力与引用。业务输入仅两段：

- **任务**：自包含本步目标、范围与授权、必要资料引用（含项目手册）与交付要求。
- **Spec**：产物规范 name 与绝对路径列表；带 `#二级标题` 时只加载该节及子节。

调用层实际加载所选注册 Agent 的角色配置并提供项目环境，不增加第三段业务输入；尽量使用独立任务上下文，工具支持时关闭完整历史继承。不附 Skill、task_ref 或历史对话。Agent 自主工作，仅返回业务结论、产物和遗留项；主会话通过原生消息跟进，收到源文档后渲染并交付。缺少所需能力或资料时说明阻碍。
