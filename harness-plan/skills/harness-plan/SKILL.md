---
name: harness-plan
description: 深入理解现有流程，澄清需求与技术决策，生成 Harness Backend 可直接执行的需求契约和代码修改方案。
user-invocable: true
---

# Harness Plan

机器产物是 `.harness/plans/<name>.md` 和 `.harness/plans/<name>-implementation.md`，用户审阅入口是 `.harness/plans/<name>.html`。不要生成 spec、代码、原型或其他文件。

## 现状调研

- 先读项目根 `AGENTS.md`，不存在时读 `CLAUDE.md`。
- 查找与需求相关的 `.harness/call-chain/*.md`，用它定位外部入口、异步推进和生命周期状态，再核对相关代码、数据模型、配置和测试。
- CallChain 只是索引；缺失、过期或与代码冲突时以代码为准，并在 `Current Flow` 写明依据。不要修改 CallChain。

## 门禁

- 只询问会改变范围、验收标准、目标流程或实现契约的问题，一次一个。
- 未确认范围、feature、验收标准、目标流程和关键技术决策前，不写文件。
- 不把交互依赖、未来能力或顺带提及的内容写成本次开发。
- 最终产物不得包含 `TBD`、未决选型或把关键决策留给 Builder。

## 技术决策与调研

先识别项目已有框架、依赖和惯例；已有明确方案时说明并沿用，不制造选型。

项目没有既定方案，且选择会影响安全、数据、接口、事务、部署或长期维护时：

1. 说明必须决定的问题，询问用户是否进行外部调研。
2. 用户同意后只使用官方或一手来源，比较 2–3 个适合当前项目的方案；覆盖项目适配性、安全、运维、迁移和测试，给出推荐并让用户选择。
3. 用户拒绝且未指定方案时暂停，直到用户明确选择或授权 Harness 代选。
4. 获得代选授权后给出推荐与理由，仍须用户确认。

在修改方案的 `Technical Decisions` 记录候选方案、决策驱动因素、最终选择、理由、影响和来源；没有新选型时记录沿用的项目惯例。

## 流程

1. 用 2–4 句话说明现有项目和业务流程，并提出最关键问题。
2. 将内容分为“本次开发、交互依赖、Out of scope”，让用户确认。
3. 拆成稳定、唯一的英文 kebab-case feature slug，并确认清单。
4. 为每个 feature 确认触发动作、预期响应、关键副作用和重要异常分支。
5. 完成所有技术决策；确认权限、事务、幂等、并发、性能和依赖约束。
6. 起草 `Current Flow`、`Target Flow` 和 `Change Map`，让用户确认改造后的业务流程和修改边界。
7. 补齐接口与数据、实施顺序、验证、风险和恢复方案；只在会话中展示简短摘要，不铺开两个完整草稿。
8. 读取两个内容模板并写入关联的 XML 与 Markdown：
   - `.agents/skills/harness-plan/assets/plan-template.xml`
   - `.agents/skills/harness-plan/assets/implementation-plan-template.md`
9. 验证两个机器产物后，在项目根运行：
   `bash .agents/skills/harness-plan/scripts/render-plan-html.sh ".harness/plans/<name>.md" ".harness/plans/<name>-implementation.md" ".harness/plans/<name>.html"`。
10. 报告简短摘要和 HTML 路径，让用户在两个标签页中完成最终审阅。反馈只修改 XML 或 Markdown，再重新生成 HTML；禁止单独修改 HTML。

## XML 需求契约

- 根节点为 `<plan>`，并包含单行、双引号属性的 `<implementation-plan path=".harness/plans/<name>-implementation.md" />`。
- `<context>` 用 1–3 句话说明动机。
- 每个 `<feature>` 有唯一 slug、description 和非空 acceptance criteria。
- criterion 必须能通过命令、请求、状态或副作用验证；禁止“功能正常、符合预期、保证稳定”。
- out-of-scope 同时记录明确不做项和非本轮开发的交互依赖。
- constraints 只写已确认或项目明确存在的约束；dependencies 使用 `ready` 或 `not-ready`。
- XML 标签外不写正文，完成前验证 XML 可解析且引用的 Markdown 路径正确。

## 修改方案边界

Markdown 必须自包含，固定包含 Purpose、Current Flow、Target Flow、Change Map、Interfaces and Data、Technical Decisions、Cross-cutting Constraints、Implementation Sequence、Validation、Risks and Recovery。

细化到仓库相对路径、模块、已有公共类或接口及职责变化，但不规定私有辅助方法、方法体、行级修改或不改变契约的局部重构。设计模式仅在它是技术选型或会改变模块边界、扩展方式、事务语义时写入。每个实施批次必须可独立验证。

## HTML 审阅入口

- HTML 是必需的桌面端用户产物，但 Backend、Builder 和 QA 仍只消费 XML 与 Markdown。
- 第一次生成 HTML 前，必须已经确认范围、验收标准、目标流程和关键技术决策。
- HTML 必须由渲染脚本从两个机器产物生成；不得手写、局部修补或把它作为新的事实来源。
- HTML 生成失败时保留已验证的 XML 与 Markdown，针对失败原因重试一次。再次失败则报告错误并保持 Plan 未完成，不提示进入 Backend。
- 会话中不粘贴两个完整草稿；用户通过 HTML 的“需求契约”和“实施方案”标签页审阅。

## 完成

最终确认前检查三个文件存在，并检查路径关联、范围、决策、目标流程、修改地图、验收标准、依赖、约束和必需章节。报告三个路径，并提示选择 `/harness-backend-fast` 或 `/harness-backend`。
