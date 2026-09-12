# Keel Plan HTML 审阅界面设计

> 历史设计记录：当前仅维护 Codex App runtime，部署和验证方式以根目录 README.md 为准。


## 背景与目标

Codex App 的 Keel Plan 当前生成两份相互关联的产物：XML 需求契约和 Markdown 代码改造方案。Dev 初始化脚本解析 XML，Builder 与 QA 同时消费两份计划；用户则需要在会话中审阅两份较长的完整草稿，容易产生阅读疲劳。

本次为 Codex App Keel Plan 增加一个桌面端、自包含的 HTML 审阅界面。HTML 用两个标签页呈现现有两份计划，并成为会话中的唯一完整审阅入口。XML 和 Markdown 继续作为 Agent 与脚本的唯一事实来源，现有 Dev 契约不变。

Claude Code runtime 仍维持当前单 XML 产物流程，不在本次范围内。

## 产物契约

Keel Plan 最终生成三份文件：

1. `.keel/plans/<name>.md`：XML 需求契约，供初始化脚本解析。
2. `.keel/plans/<name>-implementation.md`：Markdown 代码改造方案，供 Builder 和 QA 消费。
3. `.keel/plans/<name>.html`：面向用户的唯一完整审阅入口。

XML 中的 `<implementation-plan>` 声明保持不变，不引用 HTML。Dev、Builder 和 QA 不读取、解析或复制 HTML。HTML 是 Keel Plan 的必需产物；缺失时 Plan 不得报告完成或提示进入 Dev。

## 架构与组件

新增两个 Codex Keel Plan 内部组件：

- `keel-plan/skills/keel-plan/assets/plan-view-template.html`：自包含的桌面端页面模板，包含样式、标签页行为和安全渲染逻辑。
- `keel-plan/skills/keel-plan/scripts/render-plan-html.sh`：确定性渲染入口，只读消费 XML 和 Markdown，生成对应 HTML。

部署后的调用形式为：

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh \
  .keel/plans/<name>.md \
  .keel/plans/<name>-implementation.md \
  .keel/plans/<name>.html
```

渲染器将两份源内容安全编码后嵌入模板。页面在本地浏览器中解析 XML，并按受支持的 Markdown 结构创建展示节点。模板不引用 CDN、远程字体、远程脚本或其他网络资源，生成文件可通过 `file://` 直接打开。

XML 和 Markdown 始终是唯一事实来源。用户反馈导致内容变化时，Keel Plan 先更新相应源文件、重新运行现有契约校验，再重新生成 HTML；禁止只修改 HTML。

## Keel Plan 流程

Keel Plan 保留现有调研、澄清、技术决策和分段确认门禁，并调整最终审阅流程：

1. 确认范围、feature、验收标准、目标流程、修改边界和关键技术决策。
2. 写入 XML 与 Markdown，并验证 XML 可解析、路径关联正确、十个 Markdown 必需章节齐全。
3. 调用渲染器生成 HTML。
4. 在会话中只报告简短变更摘要与 HTML 路径，不再铺开两份完整草稿。
5. 用户通过 HTML 审阅两个标签页；收到修改意见后更新源文件并重新生成 HTML。
6. 用户最终确认后，报告三份文件路径，并提示选择 `/keel-dev-fast` 或 `/keel-dev`。

第一次生成 HTML 前，范围、验收标准、目标流程和关键技术决策必须已经确认，保持现有“未确认关键内容前不写文件”的门禁。

## 页面信息架构

页面仅面向桌面端，建议浏览器视口宽度不小于 1024px；不实现移动端断点、折叠布局或触屏专项适配。

顶部区域展示计划名称、审阅状态和背景摘要。主体包含两个标签页：

### 需求契约

将 XML 转成面向人的结构化内容，不展示 XML 标签：

- 背景与动机；
- feature 数量、验收标准数量和依赖状态概览；
- 每个 feature 的 slug、描述和验收标准；
- Out of scope；
- 约束；
- ready 与 not-ready 依赖。

### 实施方案

按照固定章节渲染 Markdown，不显示 Markdown 标记：

- Purpose；
- Current Flow；
- Target Flow；
- Change Map；
- Interfaces and Data；
- Technical Decisions；
- Cross-cutting Constraints；
- Implementation Sequence；
- Validation；
- Risks and Recovery。

渲染器支持这些计划需要的标题、段落、有序与无序列表、行内代码、代码块和链接。HTML 不提供编辑、评论、下载、主题切换或源码视图。

标签页支持鼠标点击和键盘切换，并通过 URL hash 恢复当前标签。页面使用正确的 tab 语义、焦点状态和关联面板属性。

## 视觉设计

页面采用已确认的 `Calm Technical` 风格。技术感来自结构、排版和少量工程化细节，而不是终端皮肤或工业装饰：

- 石墨灰与冷灰用于页面背景、表面、边框和正文层级；
- 低饱和蓝色只用于当前标签、链接和焦点状态；
- 状态颜色只表达语义，并同时配合文字或形状，禁止只靠颜色传递信息；
- 中文正文使用系统无衬线字体，路径、slug 和状态使用系统等宽字体；
- 长文左对齐，使用舒适行高和约 80 字符以内的阅读行宽；
- 不使用霓虹色、渐变、发光效果、满屏卡片或装饰性动效。

普通正文与背景对比度至少达到 WCAG AA 的 4.5:1，大字号文字和必要非文本界面至少达到 3:1。

设计依据：

- [GitHub Primer Color Usage](https://primer.style/product/getting-started/foundations/color-usage/)
- [GitHub Primer Typography](https://primer.style/product/getting-started/foundations/typography/)
- [IBM Carbon Color](https://carbondesignsystem.com/elements/color/overview/)
- [IBM Carbon Productive Typography](https://v10.carbondesignsystem.com/guidelines/typography/productive/)
- [Atlassian Color](https://atlassian.design/foundations/color)
- [W3C WCAG 2.2 Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum)

## 安全与错误处理

渲染器在生成前验证参数、输入文件、XML 可解析性、implementation plan 路径关联和 Markdown 必需章节。源内容先安全编码，再嵌入模板，避免中文、引号、代码片段或结束标签破坏 HTML 结构。

页面只通过 DOM API 创建受支持的白名单元素。来自项目的 XML 与 Markdown 内容必须进入文本节点或经过明确的 URL 协议校验，禁止以任意 `innerHTML` 执行。链接只允许安全的本地相对路径、`http` 和 `https`；脚本、事件属性及其他可执行内容一律按普通文本展示。

输出采用同目录临时文件加原子替换：

1. 渲染器完整生成临时 HTML；
2. 校验必需标记、内嵌内容和输出非空；
3. 成功后替换目标 HTML；
4. 失败时删除临时文件，不覆盖已有的有效 HTML。

HTML 生成失败时保留已验证的 XML 与 Markdown。Keel Plan 针对失败原因重试一次；再次失败则报告明确错误，Plan 保持未完成，不提示进入 Dev。

## 验证

扩展 `scripts/check-planning-contract.sh`，覆盖：

- HTML 模板和渲染脚本存在；
- Keel Plan Skill 声明三份产物和 HTML 审阅流程；
- 模板包含两个可访问标签页、必需内容容器且没有远程资源；
- 示例 XML 与 Markdown 可以生成非空、自包含的 HTML；
- HTML 包含需求契约和十个实施方案章节；
- 中文、引号、HTML 标签、`<script>`、代码块、列表和链接不会破坏结构或变成可执行内容；
- 缺失输入、非法 XML、错误关联路径和缺失章节返回非零；
- 失败时不覆盖已有 HTML。

运行以下仓库级验证：

```bash
bash -n keel-plan/skills/keel-plan/scripts/render-plan-html.sh
scripts/check-planning-contract.sh
scripts/check-runtime-parity.sh
scripts/keel-metrics.sh
```

在 `mktemp -d` 创建的临时目标分别部署 Codex App 与 Claude Code runtime。Codex 目标必须包含 HTML 模板与渲染器；Claude Code 目标不得因本次变更新增三产物约束。最后使用桌面视口打开生成示例，人工检查标签切换、键盘焦点、hash 恢复、长文滚动和 Calm Technical 配色。

## 文档与兼容性

README 更新 Codex Keel Plan 为“三文件、单审阅入口”，明确用户审阅 HTML，Dev 仍只消费 XML 与 Markdown。部署目录示例同步加入新增模板和脚本。

现有双产物计划仍可直接交给 Dev，不要求补生成 HTML。只有运行新版 Keel Plan 的新计划必须包含 HTML。Claude Code runtime、旧计划和现有 Dev run 不迁移。

## Out of Scope

- 用 HTML 替代 XML 或 Markdown；
- 修改 Dev、Builder 或 QA 的输入契约；
- 修改 Claude Code Keel Plan；
- 移动端适配；
- HTML 内编辑、评论、下载、打印优化、主题切换或源码视图；
- 引入前端框架、包管理器、CDN 或远程服务；
- 将 HTML 审阅器扩展为独立 Web 应用。
