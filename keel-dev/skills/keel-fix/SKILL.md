---
name: keel-fix
description: 定位新提交的 BUG，编排局部缺陷的修复说明、用户确认、实现与验收；涉及需求或设计变化时转交 keel-plan，已有开发 run 的返修沿用原流程。
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

展示同名 HTML，反馈修改 MD 后重新渲染。用户明确确认当前修复说明后才运行：

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py approve .keel/bugs/<id>/bug.md --decision '<用户确认原文>'
```

首次审批检查局部修复资格并记录用户确认，只保存独立 fix state.json；执行直接读取 bug.md 和同目录 investigation.md，不复制批准快照。采用返回路径作为 KEEL_PROFILE；同一 BUG 重复确认恢复既有任务，阶段和计数保留。确认后不再校验文档变化或要求重新确认。确认根因或补充日志不等于批准修复方案。

主会话按项目配置完成适用的构建、类型/语法或启动检查，失败暂停；测试无独立准备记 not-applicable，无法运行不算不适用。既有准备失败经用户明确允许才记 failed_allowed，简述失败情况并继续验证本次改动。

## 修复

主会话调度新的 `keel-builder`，Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-implementation-spec`（`.codex/common/refs/keel-implementation-spec.md`）、`keel-code-quality-spec`（`.codex/common/refs/keel-code-quality-spec.md`）、`keel-bug-scope-spec`（`.codex/common/refs/keel-bug-scope-spec.md#分类结论`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）。任务包含 bug.md、investigation.md、必要资料和本轮范围（旧任务沿用已有资料）；请其完成已确认修复、验证和聚焦提交，返回业务结论、commits、产物、验证结果与遗留项。

主会话内部阶段 BUG_BUILD 对应全部已确认修复，完成后以 bug.md 登记 BUG_BUILD_DONE；BUG_FIX 对应 fix-brief.md 的阻断项和受影响行为，完成后以该文件登记 BUG_FIX_DONE。主会话依据当前 Builder 的业务结论更新 build.commits，分别进入 BUG_REVIEW 或 BUG_REVIEW_FIX；阶段与标记不下发给 Agent。

## 验收与返修

主会话调度新的 `keel-qa`，Spec 为 `keel-delivery-spec`（`.codex/common/refs/keel-delivery-spec.md`）、`keel-acceptance-spec`（`.codex/common/refs/keel-acceptance-spec.md`）、`keel-code-quality-spec`（`.codex/common/refs/keel-code-quality-spec.md`）、`keel-bug-scope-spec`（`.codex/common/refs/keel-bug-scope-spec.md#分类结论`、`.codex/common/refs/keel-bug-scope-spec.md#验收记录`）、`keel-document-writing-spec`（`.codex/common/refs/keel-document-writing-spec.md`）、`keel-qa-scoring-spec`（`.codex/common/refs/keel-qa-scoring-spec.md`）。任务包含 bug.md、investigation.md、本轮 Builder 标识和 commits、验收范围及产物目录（旧任务沿用已有资料），返修验收另附 fix-brief.md；请其按 Spec 验收，返回 APPROVED/REJECTED、当次评分路径和遗留项。

BUG_REVIEW 覆盖全部修复目标，BUG_REVIEW_FIX 覆盖阻断项及受影响行为。通过后进入 WAITING_RETEST；未通过则由主会话整理 fix-brief.md，进入 BUG_FIX 并安排新 QA 复验。原方案内返修最多三轮且不重复确认，仍阻断则 PAUSED。

根因被推翻时回到定位；发现需求或设计变化时记 NEEDS_PLAN 并提示转 Plan。已结束任务的新反馈另开 BUG，不通过重复确认重置阶段或返修次数。

## 现场复验与交付

主会话报告 commits、验证结果和现场缺口。QA 通过表示代码验收完成，待测试或用户确认原场景解决后记 DONE。推送、合并及回写外部缺陷单按用户另行授权执行。

## 运行衔接

使用原生 subagent；主会话选择或替换 Agent/Spec，在执行阶段的 state.json.aso_bindings 按 builder/qa 记录 agent、spec_refs，忽略旧 task_ref。业务输入仅两段：

- **任务**：自包含本步目标、范围与授权、必要资料引用（含项目手册）与交付要求。
- **Spec**：产物规范 name 与绝对路径列表；带 `#二级标题` 时只加载该节及子节。

调用层实际加载所选注册 Agent 的角色配置并提供项目环境，不增加第三段业务输入；尽量使用独立任务上下文，工具支持时关闭完整历史继承，不靠继承父 Skill 或对话充当角色。不下发 KEEL_PROFILE、stage、artifact、tag、reporter、task_ref 或 Skill，不把运行字段和历史对话夹入任务。Agent 自主工作，仅返回业务结论、产物、commits、验证结果与遗留项。

修复与验收派发时，主会话提供批准资料与本轮范围。主会话记录当前原生执行标识，通过原生消息跟进并手动调用脚本，没有自动进度采集器；仅接受当前执行的进展与结果，拒绝晚到的旧消息。进展通过原生消息跟进，不另存进度文件。主会话 source `.codex/common/scripts/keel-common.sh`，按当前执行返回的业务结论登记 commits 与产物，调用 `complete_stage "<reporter>" "<tag>" "<摘要>" "<artifact>"`，成功后推进 state。reporter 沿用 keel-builder/keel-qa；修复结果映射本 Skill 的内部标记，QA 按返回结论映射完成标记，artifact 用当次报告；通过且无报告时用当次评分 JSON。审批、阶段与计数均由主会话管理；Agent 不调用运行助手或修改运行状态。定位阶段仅通过原生消息跟进。

恢复以 state、进度和产物为准；读取原文资料并沿用绑定，忽略旧 task_ref。审查五分钟、构建或返修十五分钟无进展时检查，并非自动判失败；轮询、重复摘要和仅 running 不算新进展，不重置计时。恢复时先结束旧执行，再创建新任务并记录新执行标识；每阶段每角色最多两次，产物错误补做一次，再失败计入恢复次数，超限暂停。
