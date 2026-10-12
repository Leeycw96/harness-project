---
name: keel-dev
description: 执行已确认计划，编排实现、QA 验收与返修，并按实际改动维护业务流程索引。
user-invocable: true
---

# Keel Dev

流程：初始化与前置检查 → 实现 → QA 验收（必要时返修）→ 判断并维护流程索引 → 交付。
主会话负责调度与阶段推进；各 Agent 依据任务和 Spec 自主完成本职工作。

## 角色与规范

下表为默认绑定。主会话选择或替换 Agent/Spec、核对能力与引用，在 `state.json.aso_bindings` 按 builder/qa/call_chain 记录 agent、spec_refs；旧 task_ref 忽略，不让 Agent 读取 Skill。

| 工作 | 默认 Agent | Spec |
| --- | --- | --- |
| 实现 | keel-builder | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-implementation-spec`：`.codex/common/refs/keel-implementation-spec.md`；`keel-code-quality-spec`：`.codex/common/refs/keel-code-quality-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md` |
| 验收 | keel-qa | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-acceptance-spec`：`.codex/common/refs/keel-acceptance-spec.md`；`keel-code-quality-spec`：`.codex/common/refs/keel-code-quality-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md`；`keel-qa-scoring-spec`：`.codex/common/refs/keel-qa-scoring-spec.md` |
| 流程维护 | keel-call-chain | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-flow-index-spec`：`.codex/common/refs/keel-flow-index-spec.md`；`keel-business-flow-spec`：`.codex/common/refs/keel-business-flow-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md` |

## 初始化

主会话接收已确认的计划索引。新任务在项目根 source `.codex/common/scripts/keel-init.sh`，将索引绝对路径设为 KEEL_PLAN_PATH，用当前分支和 get_next_run_number 选择 `.keel/iterations/<branch>/run-N`，设为 KEEL_OUTPUT_DIR；仅用户要求时创建分支。

```bash
KEEL_PROFILE=$(init_keel_run "$KEEL_OUTPUT_DIR" "$KEEL_PLAN_PATH")
export KEEL_PROFILE
```

初始化校验并快照索引与功能文档。缺失、旧格式或关键设计未决时交回 Plan；已有 run 按下文恢复。

主会话按项目配置完成前置检查并简述结果：main_compile 为适用的构建、类型/语法或启动检查，失败暂停；test_compile 为测试准备，无独立准备记 not-applicable，无法执行不等于不适用。既有准备失败须用户明确允许才记 failed_allowed，仍须验证本次改动。准备完成进入 BUILD。

## 实现

主会话按实现绑定调度 `keel-builder`，任务包含 run 内快照计划、当前功能范围及交付要求：在业务代码与测试范围内完成实现、相关验证和聚焦提交，返回新 commits、产物、验证结果和遗留项。小任务一次完成，确有依赖或隔离需要时按功能分片。

以下阶段、完成标记与产物登记仅由主会话内部使用：

| 阶段 | 本步任务 | 主会话完成标记与产物 |
| --- | --- | --- |
| BUILD | 实现当前功能，最后一片完成整体相关验证 | BUILD_SLICE_DONE；最后一片 BUILD_DONE；产物 plan.md |
| FIX | 按 QA 的 fix-brief.md 修复阻断项及受影响行为 | FIX_DONE；产物 fix-brief.md |

主会话核对结果并记录本轮新 commits。全部实现完成进入 REVIEW，返修完成进入 REVIEW_FIX；发现计划矛盾或需要改变已确认设计时暂停并交回 Plan。

## 验收

主会话按验收绑定调度新的 `keel-qa`，任务包含快照计划、本轮 Builder 标识和 commits、验收范围及报告目录；返修验收另附 fix-brief.md。请其按 Spec 核验本次交付并生成验收产物，返回业务结论 APPROVED 或 REJECTED、验证结果和遗留项。

REVIEW 覆盖全部功能；REVIEW_FIX 覆盖阻断项与受影响场景。通过后进入流程维护判定；未通过则由主会话将阻断项整理为 fix-brief.md，返回实现步骤的 FIX，再安排新 QA 复验。最多三轮返修，仍阻断则 PAUSED。

## 流程维护

QA 通过后，主会话检查最终 Builder diff，按流程索引 Spec 判断是否需要调度：明确无外部入口、异步推进点、业务状态节点、流转条件或状态变更符号变化时为 noop，有变化或不确定为 run。

主会话调用 `record_call_chain_prefilter "<noop|run>" "<判定说明>"`。on-demand 的 noop 调用 record_call_chain_skip 后直接交付；run 按流程维护绑定调度 `keel-call-chain`，任务包含索引目录、最终 commits 和相关计划，请其核实并维护受影响流程，返回 call-chain-review.md、业务结论 NOOP 或 UPDATED、更新文件与未确认事项。

收到报告后，主会话先核对产物与结果，以对应内部标记调用 complete_stage；成功后才记录以下结果并推进 state：

- NOOP：主会话映射内部标记 CALL_CHAIN_NOOP，调用 `record_call_chain_result noop`。
- UPDATED：主会话核对更新文档与报告，映射内部标记 CALL_CHAIN_UPDATED，调用 `record_call_chain_result updated`。本步不要求 Git 提交；任务另外要求提交时，可用第二参数记录返回的 commit SHA。

恢复旧 shadow 模式时始终调度 CallChain，Agent 独立判断且不读取预判结果；主会话完成上述产物校验与记录后，改用 `record_call_chain_shadow_result "<noop|updated>"` 并记录对应文档结果。

## 交付

主会话报告实现 commits、QA 验证摘要、流程维护结论及产物。DONE 后的新反馈另开任务，范围或设计变化交回 `/keel-plan`。

## 运行衔接

每次使用原生 subagent，业务输入仅两段：

- **任务**：自包含本步目标、范围与授权、必要资料引用（含项目 AGENTS.md，缺失用 README.md）与交付要求；执行资料为快照索引、当前功能及明确引用章节。
- **Spec**：产物规范 name 与绝对路径列表；带 `#二级标题` 时只加载该节及子节。

调用层实际加载所选注册 Agent 的角色配置并提供项目环境，不增加第三段业务输入；尽量使用独立任务上下文，工具支持时关闭完整历史继承，不靠继承父 Skill 或对话充当角色。不下发 KEEL_PROFILE、stage、artifact、tag、reporter、task_ref 或 Skill，不把运行字段和历史对话夹入任务。Agent 自主选择方法，仅返回业务结论、产物、commits、验证结果与遗留项。

主会话记录当前原生执行标识，通过原生消息跟进并手动调用脚本，没有自动进度采集器；仅接受当前执行的进展与结果，拒绝晚到的旧消息。进展通过原生消息跟进，不另存进度文件。主会话 source `.codex/common/scripts/keel-common.sh`，核对产物、结果及任务要求的提交后调用 `complete_stage "<reporter>" "<tag>" "<摘要>" "<artifact>"`，再推进 state。reporter 沿用对应默认角色；阶段、登记产物和完成标记仅为主会话内部字段，实现结果映射上表，QA 结论映射 APPROVED/REJECTED，流程维护结论按上节映射。Agent 不调用运行助手或修改运行状态。

恢复时主会话先结束旧执行，运行 `resume_keel_run "$KEEL_PROFILE"` 并采用返回路径（兼容旧 profile），再创建新任务并记录新执行标识；保留提交、进度与返修计数，自定义 A/S 沿用，忽略旧 task_ref。审查五分钟、实现或返修十五分钟无进展时检查，并非自动判失败；轮询、重复摘要和仅 running 不算新进展，不重置计时。每阶段每角色最多恢复两次；产物错误定向补做一次，再失败计入恢复次数。已完成 run 不重开，超限或关键资料缺失则暂停并报告。
