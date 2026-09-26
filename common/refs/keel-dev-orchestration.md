# Keel Dev 编排（O）

主会话按“主会话编排”组合角色与规范，并下发“通用任务要求”和当前任务章节引用。章节边界以二级标题为准。

## 主会话编排

full/fast 仅用原生 subagent，无该能力则停止；不启动 Agent CLI、tmux、pane 或 send-keys。每任务使用新 Agent，角色之间不通信、调度或等待。

### 角色与规范绑定

下表路径相对项目根；均加项目 AGENTS.md（缺失用 README.md），下发前检查可读。

| 工作 | 默认 Agent（A） | 专项 Spec（S） | 任务章节（O） |
| --- | --- | --- | --- |
| 实现 | keel-builder | .codex/common/refs/keel-dev-spec.md | .codex/common/refs/keel-dev-orchestration.md#实现任务 |
| 验收 | keel-qa | .codex/common/refs/keel-qa-spec.md | .codex/common/refs/keel-dev-orchestration.md#验收任务 |
| 流程维护 | keel-call-chain | .codex/common/refs/keel-call-chain-spec.md | .codex/common/refs/keel-dev-orchestration.md#流程维护任务 |

验收 spec_refs 另加 `.codex/common/refs/keel-dev-spec.md#代码与测试标准`；替换开发 Spec 时同步引用。

A/S 可独立替换。在 `state.json.aso_bindings` 按 builder/qa/call_chain 保存 agent、spec_refs、task_ref；fast 只保存前两项，恢复沿用。引用使用绝对路径，可附 `#二级标题`，只读该节及其子节，到下一二级标题结束；无片段则读全文。替换须具备对应能力并遵守任务约定，不改变授权、目标或门禁；缺失资料、章节或规范冲突须阻断。

### Run 与 Preflight

仅用户明确要求时创建分支。source `.codex/common/scripts/keel-init.sh`，取当前分支，用 `get_next_run_number` 选 `.keel/iterations/<branch>/run-N`。将已确认索引绝对路径赋给 `KEEL_PLAN_PATH`，设置 `KEEL_OUTPUT_DIR`。

`validate_keel_plan` 校验完整文档集合；初始化传 output_dir 与原始索引，快照为 plan.md 并复制关联功能文件，返回 state.json，导出 KEEL_PROFILE。缺失、旧格式或未决事项返回 Plan，不用历史 run 补齐。

从项目手册、配置、脚本和 CI 确定实际检查，多语言按模块记录：

- main_compile 表示适用的构建、类型/语法或启动/加载检查；失败停止。
- test_compile 表示独立测试准备；无独立步骤记 not-applicable 及理由，仍须运行测试；无法执行不等于不适用。
- 测试准备失败须用户明确允许才记 failed_allowed 并继续；summary 逐模块记类型、目录、命令、结果，不把未执行记为通过。

### 调度与返回

每次 prompt 下发：目标、stage、范围（slug/batch、全部验收或修复项）、输入路径、本轮 commits、完整 spec_refs、task_ref、KEEL_PROFILE、output/artifact、完成 tag 和 reporter（逻辑名 keel-builder / keel-qa / keel-call-chain，替换 Agent 后保持日志兼容）。同时要求读取 `.codex/common/refs/keel-dev-orchestration.md#通用任务要求` 与 task_ref 指定章节；子任务不读取主会话编排或其他任务章节。

路径转绝对，按依赖切片，只传当前功能及引用。主会话核验进度、tag、artifact 和 git commit，再更新 state 并推进。契约矛盾、关键决策缺失或不可执行时 PAUSED，带证据交回 Plan；fast 的状态机变化转 full。

### 恢复与门禁

- 以 state 和磁盘 artifact 为准。旧 profile.json 再读同目录 state.json；缺 aso_bindings 时补默认绑定。恢复先校验计划快照，不重新初始化；旧计划格式返回 Plan 并新建 run。
- 读 progress.tsv 最新记录；旧 run 使用 profile 配置的 progress.events。审查 5 分钟、构建/修复 15 分钟无有效进展时检查；失联则结束旧执行并恢复，每阶段每角色最多恢复 2 次，超过 PAUSED。
- 当前执行 artifact 缺失或格式错误定向重做一次，再次失败计入恢复次数；计划索引或功能文件缺失直接返回 Plan。
- 只记录 Builder 本轮新 commit；QA REJECTED 阻断，非阻断观察只汇总。除实现提交和流程文档提交外，不自动 stage、merge、squash、push 或清理历史。

## 通用任务要求

只执行收到的一个任务；不调度、等待或直接联系其他 Agent。

### 输入与读取

1. 按 prompt 的 `spec_refs`、`task_ref` 读取规范、任务章节和资料；路径后的 `#二级标题` 指定范围，包含子节，到下一二级标题结束，无片段读全文。缺失资料或章节返回阻断，不猜测默认规范，不读取本文件其他任务章节。
2. `KEEL_PROFILE` 指向当前 state；旧路径为 `profile.json` 时再读同目录 `state.json`。定向读取 `project_dir`、`output_dir`、`plan_path`、本轮 build.commits 和所需 preflight 字段，在 project_dir 工作，不扫描历史。流程维护不得读取 call_chain.prefilter，保证独立判断。
3. `plan_path` 是索引，目标、验收和依赖来自索引；模型、时序图、接口和改造点来自功能文件。只加载任务范围内的功能及明确引用的共享章节，不展开依赖全文。完整验收逐功能覆盖所有目标，复审与修复只读相关项。HTML 和 `.review.md` 不作为执行依据。
4. 改造点只定位文件、符号并一句话描述改动；结合目标、数据模型、时序图及执行说明、接口设计完成或核验必要联动，未选图不免除实现与验收。不重新选择已确认的关键方案。

### 运行与交付

导出 prompt 中的 `KEEL_PROFILE`，source `.codex/common/scripts/keel-common.sh`。下列 `reporter`、`stage`、`tag`、`artifact` 使用本次 prompt 与任务说明给定值：

```bash
update_progress "$reporter" "$stage" "当前工作" "$artifact"
complete_stage "$reporter" "$tag" "完成结论" "$artifact"
```

开始及有实质进展时写 progress；完成约定产物、验证和所需提交后调用 complete_stage，返回 tag、artifact、可选 commit sha 和关键证据，然后结束。不得自行推进阶段或修改调度状态。

计划矛盾、关键选择缺失、与代码冲突或无法执行时，记录证据与阻断原因并返回，不改写计划、不发成功 tag；主会话决定暂停与交回 Plan。

`preflight.test_compile=failed_allowed` 表示用户已允许带已记录的基线失败继续：实现不主动修复该基线，验收不将其作为本轮阻断；本次扩大或重新触发的问题仍须处理。不能用此标记豁免本轮回归。

## 实现任务

与通用任务要求及本次规范共同使用。输入为计划索引、指定 slug/batch；修复时另给 `fix-brief.md`。只处理指定范围，按功能依赖、时序和 SQL 顺序实现。

| stage | 任务与输出 | tag |
| --- | --- | --- |
| BUILD | 实现本片功能并创建聚焦 commit，artifact 为 run 内 plan.md | BUILD_SLICE_DONE 或最后一片 BUILD_DONE |
| BUILD_FAST | 完成本次小范围实现，保持基础设施调整最小，创建一个聚焦 commit；artifact 为 plan.md | BUILD_FAST_DONE |
| FIX | 只修 fix-brief.md 阻断项，创建聚焦 commit；artifact 为 fix-brief.md | FIX_DONE |
| FIX_FAST | 同 FIX，保持 fast 范围 | FIX_FAST_DONE |

运行新增/修改及受影响测试、项目适用的构建、类型/语法或加载检查，记录命令和结果；最后一片须完成相关测试及适用验证。提交前核对 diff 与目标，清理本次无用代码和无关编辑，保留用户改动；只 stage 本任务文件，返回本轮新 commit。

BUILD_FAST 或 FIX_FAST 发现状态机变化时返回阻断和证据，由主会话暂停 fast 并转 full；不自行切换模式。不得生成 QA 或 CallChain 报告，不修改流程索引。

## 验收任务

输入为计划索引和 `state.json.build.commits`；只审本轮实现提交，不把用户无关改动计入结论。计算这些提交的 diff，读取相关实现与测试；按规范验证质量，运行相关测试及项目适用的构建、类型/语法或加载检查。

| stage | 验证范围 |
| --- | --- |
| REVIEW | 索引中的全部功能及本轮 commits |
| REVIEW_FAST | 同 REVIEW，额外核对 fast 范围 |
| REVIEW_FIX | fix-brief.md 阻断项与受影响场景，包含本轮修复提交 |
| REVIEW_FAST_FIX | 同 REVIEW_FIX，额外确认没有扩大 fast 范围 |

逐功能核验响应、状态、副作用、重要异常和必要联动；检查实现与目标的对应关系、无依据的额外抽象及本轮残留无用代码，不因个人偏好重开选型。fast 出现业务状态机变化须阻断，由主会话转 full。

写入或覆盖本次 `qa-feedback.md`，包含最终 `APPROVED` / `REJECTED`、逐功能目标/结果/证据、可执行验证套餐、阻断问题及非阻断观察。没有足够证据支持通过时不得写 APPROVED，明确缺陷与无法验证的区别。不修改业务代码或创建提交。

artifact 为该报告，tag 为最终判定；按运行协议完成后返回。反馈决定后续流程，验收者不自行安排修复。

## 流程维护任务

stage 为 CALL_CHAIN，仅在 full 的 QA 通过且需要独立审查时下发。输入为计划索引、最终 Builder commits 与 diff、规范提供的索引目录。只审本轮 Builder commits，按通用任务要求读取相关设计并核对代码。

按职责规范和共用粒度独立判断；默认 NOOP，不确定时说明证据缺口。

输出 `call-chain-review.md`，包含最终 `UPDATED` / `NOOP`、base/head/commits、入口与状态/流转/执行符号变化、已有文件与创建/更新门禁的证据，以及更新文件、commit 或 NOOP 原因。

- NOOP：不创建文档提交，tag 为 CALL_CHAIN_NOOP。
- UPDATED：只 stage 指定索引目录中的本次文档，创建独立中文 docs commit，tag 为 CALL_CHAIN_UPDATED。

artifact 为上述报告。按运行协议完成后返回 tag、artifact、可选 commit sha 和关键依据；不修改实现提交、业务代码或测试。
