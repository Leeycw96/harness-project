---
name: keel-fix
description: 根据问题、代码和日志定位新提交的 BUG，判断缺陷与需求及修复边界；局部缺陷生成独立 HTML 审阅稿，用户确认后只编排 Builder 与 QA。需求变更或设计变化提示用户转 keel-plan，开发 run 内返修沿用原流程。
---

# Keel Fix

仅使用原生 subagent，默认角色为 keel-builder 和 keel-qa；无原生能力则说明阻断，不启动 Agent CLI。主会话负责分流、用户沟通与推进，Agent 只执行当前任务。fix 不调用 Plan/Dev Skill，不调度 CallChain，不修改流程索引。

## 接收与定位

读取项目 AGENTS.md（缺失用 README.md），核对现象、预期及其依据、版本和触发条件。能从项目查到的资料先查，不要求完整表格。在 `.keel/bugs/<id>/investigation.md` 保存输入来源、证据、候选原因、取证请求与结论变化，不复制整批日志或覆盖其他 BUG；它与用于审阅的 bug.md 分开，更新调查进展不改已确认方案。

调度 Builder，显式给出问题、代码/日志路径、已核实事实和本次新增证据；Spec 为 `.codex/common/refs/keel-dev-spec.md#操作约束`、`.codex/common/refs/keel-dev-spec.md#问题定位` 及项目手册，任务为 `.agents/skills/keel-fix/SKILL.md#定位任务`。路径转绝对，可按本次绑定替换角色和规范。定位不要求本地复现、Plan 或开发 run，不调用开发阶段进度助手。

候选原因或暂未定位时，主会话向用户转述有区分作用的验证请求：日志关键字/位置、时间或请求标识、必要字段及目的。收到新证据后再调度分析；无证据时等待，不空转、不猜测补丁、不将无法定位认定为需求。新增日志代码也属于改造；确需增加观测能力时说明诊断需求并提示走 keel-plan，原 BUG 仍待定位。

## 分流

主会话依据定位证据决定，不能仅按缺陷单标签或修改行数判断：

- 已确认要求下的局部实现缺陷，根因明确且不改变既定设计：走 fix。
- 预期行为改变、新增需求，或修复涉及业务状态/流转条件、业务流程、接口契约、数据模型/迁移，以及需要专项设计的权限、事务并发、跨模块调整：说明理由与影响，提示用户走 `/keel-plan`，在此停止编码。缺陷也可能需要走 Plan，不自动启动 Plan，不先生成一套重复方案。
- 证据不足或预期有歧义：继续取证或请用户澄清，保持待判断。

内部条件或计算的修正不等于业务流程变化；但若会改变流程索引应记录的状态、流转或执行符号，即使为恢复旧要求，也转 Plan。

## 修复说明与确认

仅 fix 分支参考 `.agents/skills/keel-fix/assets/bug-template.md` 编写 `.keel/bugs/<id>/bug.md`。它是审阅与执行的唯一内容来源，固定三章：问题与根因、修复方案、影响与验证。保留模板字段：现象、预期及依据、定位结论、根因/证据、事项分类、处理路径/分流依据；修复目标、代码改造点和五项设计边界；影响范围、逐项回归验证、现场待验证事项。示例路径和内容须替换为项目事实，改造点每项写文件/符号与一句话改动。

五项边界须据实填写“无/有/待确认”。只有“已定位、缺陷、fix”且各项均“无”才能实施；声明不是证据，主会话与 QA 仍须核对实际影响。存在设计变化直接转 Plan，边界不明继续调查。不要借助修复说明改变原有业务约定。

使用 `.agents/skills/keel-fix/scripts/keel-fix.py`：

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
```

输出同名 HTML 和审阅摘要，复用现有明暗主题。向用户展示 HTML 并等待明确确认；反馈先改 MD 再重渲染，禁止单改 HTML。补日志、确认根因或确认预期不等于批准方案，每个 BUG 都要确认当前修复说明。收到明确确认后才运行：

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py approve .keel/bugs/<id>/bug.md --decision '<用户确认原文>'
```

脚本核对 MD/HTML 一致，保存 approved.md 快照和独立 fix state.json；返回路径用作 KEEL_PROFILE。重复确认同一版本恢复既有 run，不重置返修次数。这个记录不能代替真实用户确认，不得自行编造 decision。

## 执行编排

主会话记录 state.json.aso_bindings：实现绑定 dev Spec、验收绑定 `.codex/common/refs/keel-qa-spec.md` 与 dev Spec 的代码与测试标准；均加项目手册，任务引用为本 Skill 的修复任务/验收任务。A/S 可独立替换，恢复沿用；每次下发目标、stage、完整 Spec 引用、对应任务及执行约定、KEEL_PROFILE、approved.md 路径、范围、commits、artifact、tag。不加载 Dev 的阶段说明或初始化函数。

执行前根据项目配置完成适用的构建、类型/语法或启动检查，失败则暂停；测试准备无独立步骤记 not-applicable 及理由，无法运行不能视为不适用。既有测试准备失败须用户明确允许才记 failed_allowed，记录目录、命令和结果，不豁免本次新增回归。

1. BUG_BUILD：新 Builder 按快照实现、验证并创建聚焦提交，返回 BUG_BUILD_DONE；主会话核对 tag、artifact 和新 commit，更新 build.commits 后进入 BUG_REVIEW。
2. BUG_REVIEW：新 QA 验证本次全部修复目标与 commits，写 qa-feedback.md。APPROVED → WAITING_RETEST；REJECTED 的阻断项写 fix-brief.md 后进入 BUG_FIX。
3. BUG_FIX：Builder 仅修阻断及受影响行为，验证提交，返回 BUG_FIX_DONE；新 QA 执行 BUG_REVIEW_FIX。最多三轮返修，仍阻断则 PAUSED，不静默重开 run 归零。

原方案内返修不重复确认。根因被推翻时暂停回到定位；发现需求或设计变化时记 NEEDS_PLAN，报告已改内容并提示转 Plan，不继续扩大 fix。局部方案实质变化时，先结束当前执行再更新 MD/HTML，重新确认形成新快照，不能修改旧快照继续执行。

主会话以 state、进度和产物恢复；每次派发前运行 check 核对确认版本。审查 5 分钟、构建/返修 15 分钟无有效进展时检查，失联结束旧任务后恢复，每阶段每角色最多两次；产物缺失或错误定向重做一次，再失败计入恢复次数，超限暂停。

QA 通过只表示代码验收完成。报告提交、验证证据及现场缺口，待测试或用户确认原场景已解决后记 DONE。不要自动推送、合并或回写外部缺陷单。

## 定位任务

按所给 Spec 分析问题和资料，不改业务代码、测试或配置，不提交。可读取相关流程索引辅助定位，但核对实际代码，不更新索引。具备条件时复现；否则沿调用、数据、条件、异常、配置与日志位置分析。

返回已定位/候选原因/暂未定位、事实和证据位置、与本次现象的关联、支持与反对证据、影响范围、建议分流、仍需验证的信息及方法。定位不出来就明说；多个原因不能任意选一个，不把日志语句当运行证据。缺失信息返回主会话，不自行询问用户或调度其他 Agent。

## 执行约定

只执行所分配阶段，读取 Spec 和 approved.md，不调度其他 Agent。从 state 定向读取 project_dir、output_dir、fix_path 和本轮 commits，在 project_dir 工作。导出 KEEL_PROFILE 后 source `.codex/common/scripts/keel-common.sh`，仅使用 update_progress 与 complete_stage 报告进度和完成；不调用初始化、CallChain 或阶段推进助手。开始及有实质进展时报告，产物/验证/提交完成后才返回完成标记。

执行前运行 `python3 .agents/skills/keel-fix/scripts/keel-fix.py check "$KEEL_PROFILE"`；返回快照路径。确认缺失、源文档变化或快照不一致时阻断，不能继续。实际发现方案不成立或超出 fix 边界时返回证据，不发成功标记、不自行改方案或切换流程。

只消费本次资料与提交，不扫描历史或处理用户无关改动。已允许的既有失败不主动修复、不当成本轮回归；本次扩大或重新触发的失败仍需处理。Agent 不更新 state 的阶段或审批字段。

## 修复任务

按已确认目标、根因与代码改造点完成必要修改，遵循 dev Spec 和项目惯例。先为可验证行为建立回归测试，再实现修复；无法完整复现时保留代码/日志证据与现场验证缺口，不伪造通过。

BUG_BUILD 实现全部已确认修复；BUG_FIX 只处理 fix-brief.md 阻断项及受影响行为。运行相关测试与适用项目检查，记录证据，核对范围并清理本次无用代码，只提交本次实现与测试。不要修改修复说明、QA 报告或流程索引。

artifact 为 approved.md（返修为 fix-brief.md）；tag 为 BUG_BUILD_DONE 或 BUG_FIX_DONE。用 complete_stage keel-builder 完成报告，返回新 commit、artifact 与关键验证结果。

## 验收任务

对照 approved.md 及本轮 build.commits，独立验证目标、修复行为、边界与关联回归，核对根因证据和实际 diff；不因事项被标成缺陷就忽略新增状态、流程、接口或模型变化。

BUG_REVIEW 覆盖全部修复目标；BUG_REVIEW_FIX 验证阻断项和受影响场景。按 QA Spec 和开发质量标准运行验证，不修改业务代码、不创建提交。写 qa-feedback.md：APPROVED/REJECTED、逐项目标/结果/证据、阻断与非阻断观察、实际命令、尚需现场复验的事项；证据不足不能判通过。

有超出 fix 范围的设计变化时 REJECTED，明确建议转 Plan；不要调度 CallChain。以 qa-feedback.md 为 artifact，用 complete_stage keel-qa 返回最终判定，由主会话推进。
