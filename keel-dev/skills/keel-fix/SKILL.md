---
name: keel-fix
description: 定位新提交的 BUG，编排局部缺陷的修复说明、用户确认、实现与验收；涉及需求或设计变化时转交 keel-plan，已有开发任务的返修沿用原流程。
user-invocable: true
---

# Keel Fix

流程：接收与定位 → 分流 → 修复说明与确认 → 修复 → QA 验收与返修 → 现场复验。
主会话负责用户沟通与推进，Builder 负责定位和修复，QA 独立验收；需要方案设计时提示用户转 `/keel-plan`，局部修复不调度 CallChain。

## 接收与定位

主会话调度 `keel-builder`，任务为只读问题调查，包含现象、预期及依据、版本、已有资料、项目手册（AGENTS.md，缺失用 README.md）、代码与日志路径。Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-investigation-spec`（`.codex/common/refs/keel-investigation-spec.md`）、`keel-bug-scope-spec`（`.codex/common/refs/keel-bug-scope-spec.md#分类结论`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）。

请 Builder 定位根因，返回结论、影响范围和仍需核实的信息；定位为只读任务，无需 Plan 或开发 run。主会话参照 `.agents/skills/keel-fix/assets/investigation-template.md` 在 `.keel/bugs/<id>/investigation.md` 保留调查进展，按 `.codex/common/refs/keel-bug-scope-spec.md#修复资格` 记录资格结论；尚未定位时补充必要资料或检查，继续分析。

## 分流

主会话依据定位结果及 `.codex/common/refs/keel-bug-scope-spec.md#分类结论` 决定去向：已定位的局部实现缺陷进入修复说明；需求或设计变化说明理由并提示用户走 `/keel-plan`；尚未定位时继续调查。需增加日志代码等诊断能力时，也先说明改造需求并转 Plan。

## 修复说明与确认

主会话加载 `.codex/common/refs/keel-fix-review-spec.md#修复说明` 和 `.codex/common/refs/keel-code-change-spec.md`，使用 `.agents/skills/keel-fix/assets/bug-template.md` 编写 `.keel/bugs/<id>/bug.md`；它是本次审阅与执行内容的来源，调查依据保留在同目录 investigation.md。

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
```

展示同名 HTML，反馈修改 MD 后重新渲染。只有已定位的局部缺陷且用户明确确认当前修复说明后，才能开始修复；确认根因或补充日志不等于批准方案。

确认后选择 `.keel/bugs/<id>/runs/run-N/` 为产物目录。执行直接读取 bug.md 和同目录 investigation.md；原方案内返修不重复确认。主会话在首次修复前记住当前 HEAD，从 Git 获取本轮修复与返修的 commits，供验收与交付使用。

## 修复

主会话调度新的 `keel-builder`，Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-implementation-spec`（`.codex/common/refs/keel-implementation-spec.md`）、`keel-code-quality-spec`（`.codex/common/refs/keel-code-quality-spec.md`）、`keel-bug-scope-spec`（`.codex/common/refs/keel-bug-scope-spec.md#分类结论`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）。任务包含 bug.md、investigation.md、必要资料和本轮范围；请其完成已确认修复、验证和聚焦提交。正常完成只需简短通知，无需汇总实际改动、验证结果、commits 或遗留项；无法完成时说明阻碍。

当前 Builder 完成后直接安排验收；返修只处理 fix-brief.md 的阻断项和受影响行为。

## 验收与返修

主会话调度新的 `keel-qa`，Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-acceptance-spec`（`.codex/common/refs/keel-acceptance-spec.md`）、`keel-code-quality-spec`（`.codex/common/refs/keel-code-quality-spec.md`）、`keel-bug-scope-spec`（`.codex/common/refs/keel-bug-scope-spec.md#分类结论`、`.codex/common/refs/keel-bug-scope-spec.md#验收记录`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）、`keel-qa-scoring-spec`（`.codex/common/refs/keel-qa-scoring-spec.md`）。任务包含 bug.md、investigation.md、本轮 Builder 标识和 commits、验收范围及产物目录，返修验收另附 fix-brief.md；请其按 Spec 验收，返回 APPROVED/REJECTED、当次评分路径和遗留项。

初验覆盖全部修复目标，复验覆盖阻断项及受影响行为。主会话按 QA 返回的 APPROVED/REJECTED 直接推进：通过后等待现场复验；未通过则依据 qa-feedback.md 整理 fix-brief.md，安排 Builder 返修和新 QA 复验。通过时验收报告可省略，评分 JSON 始终保留；评分不代替验收结论。

根因被推翻时回到定位；发现需求或设计变化时提示转 Plan。已解决问题的新反馈另开 BUG。

## 现场复验与交付

主会话报告 commits、验证结果和现场缺口。QA 通过表示代码验收完成，待测试或用户确认原场景解决后任务完成。推送、合并及回写外部缺陷单按用户另行授权执行。

## Agent 调用

使用原生 subagent；主会话选择或替换 Agent/Spec。业务输入仅两段：

- **任务**：自包含本步目标、范围与授权、必要资料引用（含项目手册）与交付要求。
- **Spec**：产物规范 name 与绝对路径列表；带 `#二级标题` 时只加载该节及子节。

调用层实际加载所选注册 Agent 的角色配置并提供项目环境，不增加第三段业务输入；尽量使用独立任务上下文，工具支持时关闭完整历史继承，不靠继承父 Skill 或对话充当角色。不下发 Skill 或历史对话。Agent 自主工作，按本步要求完成交付，不统一要求返回汇总；主会话通过原生消息跟进，完成后直接推进。
