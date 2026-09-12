# Keel Plan Draft-first 审阅流程设计

> 历史设计记录：当前仅维护 Codex App runtime，部署和验证方式以根目录 README.md 为准。


## 背景与目标

Codex App Keel Plan 已增加 XML、Markdown 和 HTML 三产物，但现有 Skill 仍要求用户逐步确认范围、feature、验收标准、Current Flow、Target Flow、Out of Scope 和 Change Map。HTML 只替代了最后一次长草稿展示，没有消除过程中的重复确认。

本次将 Keel Plan 改为 Draft-first 工作流：Keel 只询问必须由用户决定、且无法从项目上下文确定的事项；决策完成后自动推导完整计划并直接生成 HTML。HTML 成为唯一整体确认门禁，用户通过指出章节或内容发起修订。

本设计替代 `2026-08-24-keel-plan-html-review-design.md` 中“分段确认范围、流程和修改边界后再生成 HTML”的交互要求。三产物、渲染器、安全规则和 Dev 输入契约保持不变。

## 决策门禁

Keel 必须先读取项目规则、相关 CallChain、代码、数据模型、配置和测试，并优先沿用已有业务事实与工程惯例。

只有同时满足以下条件时才询问用户：

1. 该事项属于用户拥有决策权的业务、范围、交互或关键技术选择；
2. 用户输入、代码、CallChain 和项目惯例无法给出唯一答案；
3. 不同答案会产生实质不同的计划内容。

典型用户决策包括：

- 本轮是否包含某项业务能力；
- 两种业务结果都合理时选择哪一种；
- 未就绪外部依赖应阻塞、降级还是移出范围；
- 项目没有既定惯例，且技术选择会改变接口、数据、安全或长期维护方式。

以下内容由 Keel 根据调研结果和已完成决策自行确定，不得逐项询问用户确认：

- Current Flow；
- Target Flow；
- feature slug；
- acceptance criteria；
- Out of Scope；
- Change Map；
- Interfaces and Data；
- Cross-cutting Constraints；
- Implementation Sequence；
- Validation；
- Risks and Recovery；
- 沿用项目现有框架、公共接口和工程惯例的技术方案。

每次只询问一个真实用户决策。用户回答后，该答案立即成为确定输入；Keel 负责同步推导所有受影响章节，不得再以“请确认 Current Flow、Target Flow 或 feature 清单”等形式重复确认。

## Draft-first 工作流

Keel Plan 按以下顺序执行：

1. 读取用户需求和项目上下文，完成 Current Flow 与实现边界调研。
2. 识别是否存在真实用户决策。
3. 存在决策时一次询问一个，直至所有必要决策完成；不存在时不发起澄清轮次。
4. 自动起草范围、feature、验收标准、Current Flow、Target Flow、Out of Scope、Change Map、技术决策、实施顺序、验证与恢复方案。
5. 写入并校验 XML 与 Markdown，生成首版 HTML。
6. 在会话中只返回简短范围摘要、HTML 路径和审阅提示。
7. 用户通过 HTML 集中检查完整计划，并用自然语言指出需要调整的标签页、章节或内容。
8. Keel 更新机器源文件、同步修正受影响章节、重新校验并覆盖生成同一路径 HTML。
9. 用户明确确认最终 HTML 后，Keel Plan 才报告完成并提示选择 Dev。

第一次写入文件的门禁从“所有章节均已逐项确认”改为“所有真实用户决策均已完成”。不要求用户在生成首版 HTML 前确认 Keel 根据事实和决策推导出的章节。

## HTML 修订循环

首版与每次修订后的 HTML 均使用现有 `.keel/plans/<name>.html` 路径和 `READY FOR REVIEW` 状态。XML 与 Markdown 继续作为唯一事实来源；禁止直接修改 HTML。

收到用户反馈后，Keel 必须：

1. 将反馈映射到 XML 或 Markdown 的源章节；
2. 识别该修改对其他章节的连锁影响；
3. 同步更新受影响内容；
4. 重新运行 XML、路径、必需章节和 HTML 生成检查；
5. 覆盖生成同一路径 HTML，并提示用户刷新审阅。

例如，Target Flow 变化时必须同时检查 feature、acceptance criteria、Change Map、Implementation Sequence 和 Validation。Out of Scope 变化时必须检查 XML feature、依赖和实施范围是否仍一致。

如果反馈本身已经表达明确决策，Keel 直接执行修订。如果反馈产生新的真实决策分支，则回到决策门禁，一次询问一个；完成后继续生成 HTML，不恢复逐段确认。

## 错误与完成语义

现有三产物安全和失败规则保持不变：

- HTML 由确定性渲染器从 XML 与 Markdown 生成；
- 生成失败时保留有效机器产物，不覆盖已有 HTML；
- 针对失败原因重试一次，再次失败时 Plan 保持未完成；
- 源文件缺失、路径不一致、必需章节缺失或包含未决项时不得报告完成。

`READY FOR REVIEW` 只表示首版或修订版可供用户审阅，不表示 Keel Plan 已完成。只有用户明确接受最终 HTML，才提示 `/keel-dev-fast` 或 `/keel-dev`。

## 实现范围

本次只修改 Codex App runtime：

- 重写 `keel-plan/skills/keel-plan/SKILL.md` 的门禁、技术决策和流程；
- 更新 `README.md` 的 Codex Plan 使用说明；
- 扩展 `scripts/check-planning-contract.sh`，验证 Draft-first 契约并阻止旧逐段确认措辞回归。

HTML 模板、渲染器、XML 与 Markdown 模板、Dev、Builder、QA 和 Claude Code runtime 不修改。

## 验证

静态契约检查必须确认：

- Skill 明确区分“用户决策”和“由决策推导的计划章节”；
- 真实用户决策完成后直接生成三产物；
- Current Flow、Target Flow、Out of Scope、feature 和 Change Map 不再要求逐项确认；
- HTML 是唯一整体确认门禁；
- 用户反馈会更新机器源文件、同步关联章节并重新生成 HTML；
- 未经用户最终确认不得提示进入 Dev；
- Claude Code runtime 不包含 Draft-first 三产物契约。

运行：

```bash
scripts/check-planning-contract.sh
scripts/check-runtime-parity.sh
scripts/keel-metrics.sh
scripts/check-slimming-targets.sh
```

最后在 `mktemp -d` 目标分别部署 Codex App 与 Claude Code runtime，确认 Codex Skill 包含新流程，Claude Code Skill 保持原样。

## Out of Scope

- 修改 HTML 的视觉、标签页或渲染行为；
- 在 HTML 中增加编辑或评论能力；
- 用 HTML 替代 XML 或 Markdown；
- 修改 Dev、Builder 或 QA 输入契约；
- 修改 Claude Code Keel Plan；
- 完全禁止 Keel 提出必要用户决策；
- 省略用户对最终 HTML 的明确确认。
