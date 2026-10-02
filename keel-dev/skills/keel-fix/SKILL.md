---
name: keel-fix
description: 定位新提交的 BUG，编排局部缺陷的修复说明、用户确认、实现与验收；涉及需求或设计变化时转交 keel-plan，已有开发 run 的返修沿用原流程。
---

# Keel Fix

流程：接收与定位 → 分流 → 修复说明与确认 → 修复 → QA 验收与返修 → 现场复验。
主会话负责用户沟通与推进，Builder 负责定位和修复，QA 独立验收；需要方案设计时提示用户转 `/keel-plan`，局部修复不调度 CallChain。

## 接收与定位

主会话整理现象、预期及依据、版本和已有证据，将项目手册（AGENTS.md，缺失用 README.md）、代码与日志路径交给 `keel-builder`。Spec 为 `.codex/common/refs/keel-dev-spec.md#操作约束`、`.codex/common/refs/keel-dev-spec.md#问题定位`。

请 Builder 定位根因，返回结论、证据、影响范围和仍需核实的信息；定位为只读任务，无需 Plan 或开发 run。主会话在 `.keel/bugs/<id>/investigation.md` 保留调查进展；尚未定位时安排有针对性的取证，收到新证据后继续分析。

## 分流

主会话依据定位证据及 `.codex/common/refs/keel-fix-spec.md#适用范围` 决定去向：已定位的局部实现缺陷进入修复说明；需求或设计变化说明理由并提示用户走 `/keel-plan`；证据不足继续定位。需增加日志代码等诊断能力时，也先说明改造需求并转 Plan。

## 修复说明与确认

主会话按 `.codex/common/refs/keel-fix-spec.md#修复说明`，使用 `.agents/skills/keel-fix/assets/bug-template.md` 编写 `.keel/bugs/<id>/bug.md`；它是本次审阅与执行内容的来源。

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
```

展示同名 HTML，反馈修改 MD 后重新渲染。用户明确确认当前修复说明后才运行：

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py approve .keel/bugs/<id>/bug.md --decision '<用户确认原文>'
```

脚本核对源文档与 HTML，保存 approved.md 和独立 fix state.json。采用返回路径作为 KEEL_PROFILE；重复确认同一版本恢复既有任务，计数保留。确认根因或补充日志不等于批准修复方案。

主会话按项目配置完成适用的构建、类型/语法或启动检查，失败暂停；测试无独立准备记 not-applicable，无法运行不算不适用。既有准备失败经用户明确允许才记 failed_allowed，记录证据并继续验证本次改动。

## 修复

主会话调度新的 `keel-builder`，Spec 为 `.codex/common/refs/keel-dev-spec.md` 与 `.codex/common/refs/keel-fix-spec.md`，给 approved.md 及必要证据。请其完成已确认修复、验证和聚焦提交，返回 commits 与结果。

BUG_BUILD 实现全部已确认修复，以 approved.md 为 artifact，返回 BUG_BUILD_DONE；BUG_FIX 处理 fix-brief.md 阻断项和受影响行为，以该文件为 artifact，返回 BUG_FIX_DONE。主会话核对结果并更新 build.commits，分别进入 BUG_REVIEW 或 BUG_REVIEW_FIX。

## 验收与返修

主会话调度新的 `keel-qa`，Spec 为 `.codex/common/refs/keel-qa-spec.md`、`.codex/common/refs/keel-dev-spec.md#代码与测试标准` 和 `.codex/common/refs/keel-fix-spec.md`，给 approved.md 与本轮 commits。请其独立核验目标、修复行为和实际影响，按 Spec 写 qa-feedback.md，返回 APPROVED 或 REJECTED。

BUG_REVIEW 覆盖全部修复目标，BUG_REVIEW_FIX 覆盖阻断项及受影响行为。通过后进入 WAITING_RETEST；未通过则由主会话整理 fix-brief.md，进入 BUG_FIX 并安排新 QA 复验。原方案内返修最多三轮且不重复确认，仍阻断则 PAUSED。

根因被推翻时回到定位；发现需求或设计变化时记 NEEDS_PLAN 并提示转 Plan；局部方案实质变化时结束当前执行，更新 MD/HTML 并重新确认形成新快照。

## 现场复验与交付

主会话报告 commits、验证证据和现场缺口。QA 通过表示代码验收完成，待测试或用户确认原场景解决后记 DONE。推送、合并及回写外部缺陷单按用户另行授权执行。

## 运行衔接

使用原生 subagent，均附项目手册；主会话可替换 A/S 并在执行阶段的 state.json.aso_bindings 保存 builder/qa 绑定。定位任务引用 `.agents/skills/keel-fix/SKILL.md#接收与定位`；执行阶段 task_ref 为 `.agents/skills/keel-fix/SKILL.md#修复` 或 `.agents/skills/keel-fix/SKILL.md#验收与返修`，另下发 `.agents/skills/keel-fix/SKILL.md#运行衔接`。路径转绝对，章节引用仅加载对应二级标题及子节。

修复与验收的每次派发前，主会话运行 `python3 .agents/skills/keel-fix/scripts/keel-fix.py check "$KEEL_PROFILE"` 核对确认版本，并给 Agent 快照、当前范围、commits、stage、artifact 与完成 tag。Agent 依据 Spec 自主工作，导出 KEEL_PROFILE 并 source `.codex/common/scripts/keel-common.sh`，使用 update_progress 和 complete_stage 报告进展与结果，reporter 为 keel-builder 或 keel-qa；状态与审批由主会话处理。定位阶段不使用执行进度协议。

恢复以 state、进度和产物为准；沿用已确认快照与绑定，将旧默认任务引用映射到当前步骤。审查五分钟、构建或返修十五分钟无进展时检查，结束失联执行后恢复，每阶段每角色最多两次；产物错误补做一次，再失败计入恢复次数，超限暂停。确认版本不一致时先处理审阅，不能用新方案继续旧执行。
