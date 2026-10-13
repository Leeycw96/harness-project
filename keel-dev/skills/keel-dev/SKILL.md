---
name: keel-dev
description: 执行已确认计划，编排实现、QA 验收与返修，并按实际改动维护业务流程索引。
user-invocable: true
---

# Keel Dev

流程：初始化与前置检查 → 实现 → QA 验收（必要时返修）→ 判断并维护流程索引 → 交付。
主会话负责调度；各 Agent 依据任务和 Spec 自主完成本职工作。

## 角色与规范

下表为默认选择，主会话可按任务替换 Agent/Spec；不让 Agent 读取 Skill。

| 工作 | 默认 Agent | Spec |
| --- | --- | --- |
| 实现 | keel-builder | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-implementation-spec`：`.codex/common/refs/keel-implementation-spec.md`；`keel-code-quality-spec`：`.codex/common/refs/keel-code-quality-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md` |
| 验收 | keel-qa | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-acceptance-spec`：`.codex/common/refs/keel-acceptance-spec.md`；`keel-code-quality-spec`：`.codex/common/refs/keel-code-quality-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md`；`keel-qa-scoring-spec`：`.codex/common/refs/keel-qa-scoring-spec.md` |
| 流程维护 | keel-doc-writer | `keel-delivery-spec`：`.codex/common/refs/keel-delivery-spec.md`；`keel-flow-index-spec`：`.codex/common/refs/keel-flow-index-spec.md`；`keel-business-flow-spec`：`.codex/common/refs/keel-business-flow-spec.md`；`keel-document-writing-spec`：`.codex/common/refs/keel-document-writing-spec.md` |

## 初始化

主会话接收已确认的计划索引。新任务在项目根 source `.codex/common/scripts/keel-init.sh`，将索引绝对路径设为 KEEL_PLAN_PATH，用当前分支和 get_next_run_number 选择 `.keel/iterations/<branch>/run-N`，设为 KEEL_OUTPUT_DIR；仅用户要求时创建分支。

```bash
KEEL_PLAN_PATH=$(init_keel_run "$KEEL_OUTPUT_DIR" "$KEEL_PLAN_PATH")
export KEEL_PLAN_PATH
```

初始化校验并快照索引与功能文档，返回 run 内 plan.md 路径；缺失、旧格式或关键设计未决时交回 Plan。

主会话按项目配置完成适用的构建、类型/语法、启动检查及测试准备，并简述结果；无法执行不等于不适用。构建等前置检查失败时报告阻碍；既有测试准备失败须用户明确允许才继续，仍须验证本次改动。

## 实现

主会话调度 `keel-builder`，任务包含 run 内快照计划、当前功能范围、本轮已有 commits 及交付要求：在业务代码与测试范围内完成实现、相关验证和聚焦提交，返回业务结论、新 commits、产物、验证结果、遗留项及覆盖本轮全部实现与返修的流程影响（外部入口、异步推进点、业务状态节点、流转条件、业务入口符号）。小任务一次完成，确有依赖或隔离需要时按功能分片。

主会话直接采用 Builder 的业务结论，全部实现或返修完成后安排 QA。Builder 报告计划矛盾或需要改变已确认设计时交回 Plan；无法完成时按实际阻碍报告。

## 验收

主会话调度新的 `keel-qa`，任务包含快照计划、本轮 Builder 标识和 commits、验收范围及产物目录；返修验收另附 fix-brief.md。请其按 Spec 验收，返回 APPROVED/REJECTED、当次评分路径和遗留项。

初次验收覆盖全部功能，返修验收覆盖阻断项与受影响场景。通过以当次明确的 APPROVED 为准，不能凭评分推断；通过且无验收报告时正常推进。未通过则将阻断项整理为 fix-brief.md，安排 Builder 返修后再由新 QA 验收；无法完成时按实际阻碍报告。

## 流程维护

QA 通过后，主会话依据 Builder 返回的本轮整体流程影响说明判断是否需要调度：明确无外部入口、异步推进点、业务状态节点、流转条件或业务入口符号变化时直接交付；有变化、未提供说明或不确定时调度独立 `keel-doc-writer`。

DocWriter 的任务包含索引目录、最终 commits 和相关计划，请其核实并维护受影响流程，返回 call-chain-review.md、业务结论 NOOP 或 UPDATED、更新文件与未确认事项。主会话直接采用 DocWriter 结论并交付。本步不要求 Git 提交，任务另有要求时沿用。

## 交付

主会话报告实现 commits、QA 验证摘要、流程维护结论及产物。交付后的新反馈另开任务，范围或设计变化交回 `/keel-plan`。

## Agent 调度

每次使用原生 subagent，业务输入仅两段：

- **任务**：自包含本步目标、范围与授权、必要资料引用（含项目 AGENTS.md，缺失用 README.md）与交付要求；执行资料为快照索引、当前功能及明确引用章节。
- **Spec**：产物规范 name 与绝对路径列表；带 `#二级标题` 时只加载该节及子节。

调用层实际加载所选注册 Agent 的角色配置并提供项目环境，不增加第三段业务输入；尽量使用独立任务上下文，工具支持时关闭完整历史继承，不靠继承父 Skill 或对话充当角色。不把 Skill 或历史对话夹入任务。Agent 自主选择方法，仅返回业务结论、产物、commits、验证结果与遗留项，主会话直接采用，不复查产出。

用户要求中止时停止后续工作，并结束进行中的 Agent。
