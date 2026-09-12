# Keel Markdown 业务计划设计

> 历史设计记录：当前仅维护 Codex App runtime，部署和验证方式以根目录 README.md 为准。


## 已确认目标

Codex Plan 只生成一份 Markdown 开发契约和由它派生的 HTML 审阅文件，移除 XML 和独立 implementation 计划。HTML 按现有业务状态、功能目标、选定的 PlantUML 时序图、状态机差异、接口、类/方法改造点组织。功能保留可验证验收标准，未选时序图不影响开发范围。风险恢复仅在数据迁移、新状态、不可逆副作用或上线切换时展开。

默认范围为 Codex 的 Plan/Dev/full/fast 输入迁移，两套 runtime 的 CallChain 维护约定同步。Claude Code 保持原有 XML Plan 与执行流程。

## 工作流与契约

先核对代码与 CallChain，再列出稳定 feature slug 和功能目标。用户选择哪些功能生成时序图，可选全部、部分或不生成；已有明确选择或代选授权时不重复询问。其余可推导内容直接起草，不恢复逐章确认。最终 HTML 整体确认后进入 Dev。

Markdown 的固定章节为背景与范围、现有业务流程与状态机、本次功能目标、功能时序图、状态机调整、接口设计、代码改造点、技术决策与约束、实施顺序、验证方案。风险与恢复为条件章节。每个 feature 有目标、文字目标流程、验收标准和时序图选择，接口与改造点均关联 feature。状态机不适用时明确说明，不虚构状态。

状态图使用 PlantUML，当前图描述现状；调整章节区分目标图和本期差异图。新增绿色、修改黄色、删除红色，节点同时标注新增/修改/删除，删除节点仅存在于当前或差异视图。状态流转表记录触发、条件、入口和执行变更的方法，不能只标注节点而遗漏边的变化。

HTML 为单页带章节导航的离线审阅文档，展示表格和实际图像，图下可展开源码。本地 PlantUML 以 pipe 方式生成 SVG，通过 image data URL 嵌入，不向远程服务发送计划。渲染需要 Python 3；含图时需要本地 plantuml 或 KEEL_PLANTUML_JAR + Java。依赖缺失或图语法失败不覆盖旧 HTML，不能把源码当成功图表。

Dev/full/fast 初始化只接收 plan.md，state 仅记录 plan_path。Builder 和 QA 以该文件为唯一计划依据。旧 XML 输入明确拒绝，要求重新生成；不自动拼接旧 run。fast 不维护 CallChain，涉及业务状态机变化须切换 full。

CallChain 在原业务流程文件维护当前状态机和流转表，以已验收代码为准。流转记录源/目标状态、事件/条件、业务入口类/方法、实际变更类/方法及证据路径；内部方法只记录状态变化执行点，不扩展成完整调用栈。状态、流转条件和执行入口变化均触发 full prefilter；删除状态/边应清理当前文档，历史留给 git。

## 实施与验证

1. 替换 Plan 模板与 Skill，新增共享 Markdown 验证和离线图表渲染，更新 HTML。
2. 迁移初始化、编排、Builder/QA/full/fast，同步 CallChain 与 prefilter。
3. 更新文档、规划契约测试与 runtime 分叉检查。
4. 验证 Markdown 拒绝不完整/旧 XML，表格和图表正确渲染，无图计划不需 PlantUML，错误输入和图失败不覆盖旧输出。运行实际状态图/时序图浏览器检查。
5. 运行现有门禁；在 mktemp 目标测试两套部署与旧模板清理，最后检查 git status。

图表实现依据：[PlantUML CLI](https://plantuml.com/command-line)、[安全配置](https://plantuml.com/security)。

## 后续确认：语言无关

两套 runtime 的业务开发规则遵循项目语言、架构与工具链。计划和 CallChain 使用仓库路径及实际模块/函数/类型/类/方法定位；测试面向对外业务契约，文件命名与发现方式采用项目约定。保留明确标注的 Java、Go、Python 示例，不从示例推导强制分层或选型。

Preflight 沿用 state 字段以兼容旧调用：main_compile 表示主验证，test_compile 表示测试准备。无独立编译阶段时执行项目适用的类型/语法、加载、测试发现等检查；无独立准备步骤明确记录 not-applicable 与理由，不等于测试通过。多语言仓库按受影响模块记录验证证据。HTML 渲染自身的 Python/PlantUML 工具依赖不限制业务语言。
