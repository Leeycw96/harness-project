# harness-builder 操作手册

本手册描述 Builder 每个阶段怎么做。你不是 orchestrator,不要调度 QA/CodeReview,不要等待其他 subagent。

## 启动必做

每次收到主会话任务都必须重新执行:

1. 从任务 prompt 读取 `HARNESS_PROFILE` 绝对路径。
2. Read `profile.json`,记下 `project_dir`、`output_dir`、`plan_path`、artifact 路径。
3. Read `${output_dir}/state.json`。
4. Read `.codex/agents/harness-builder.md`、本手册、`.codex/common/refs/harness-backend-coding-rules.md`。
5. Read 项目根 `AGENTS.md`;没有则读 `CLAUDE.md`。
6. 只读取主会话指定的当前 artifact。不要扫描 run 目录找历史版本。

初始化进度:

```bash
export HARNESS_PROFILE="<绝对路径>"
source .codex/common/scripts/harness-common.sh
update_progress "harness-builder" "<STAGE>" "开始阶段,正在恢复 profile/state" "<artifact-可选>"
```

## 通信规则

- 不给 QA 或 CodeReview 发消息。
- 不读取 `conversation/`、`signals/`、多版本 round 文件;这些在新协议中不存在。
- 阶段完成时执行:

```bash
complete_stage "harness-builder" "<TAG>" "<一句话结论 + 1-3 个关键点>" "<artifact>"
```

然后最终回复只写 tag、artifact、commit sha 和关键结论,不要继续推进下一阶段。

## Artifact 契约

### `${output_dir}/build-scope.md`

当前唯一 scope 文件,可覆盖更新。必须包含:

- 技术栈确认: 基于 `AGENTS.md` / `CLAUDE.md`
- 功能实现清单: 每个功能一个英文 kebab-case slug
- 每个功能的验证目标: 具体可测
- 实现顺序: 基础设施 / 共享 Entity 优先
- 未决问题: plan 无法推导时列出,不要自行拍板

### `.harness/call-chain/<slug>.md`

跨迭代持久业务链路。一个完整业务流程一个文件,只记录入口方法和业务步骤,不展开内部调用链。

必须更新:

- 业务入口增删改
- 主流程步骤变化
- 验证点变化

## Stage SOP

### SCOPE_BUILD

输入: `plan.md`、项目手册、已有 `.harness/call-chain/`、可选的 `scope-review.md` 调整意见。

步骤:

1. 读取 plan 和项目手册。
2. 复用已有 call-chain slug;新功能分配新 slug。
3. 产出或覆盖 `${output_dir}/build-scope.md`。
4. 如果 plan 不清楚,在 `未决问题` 中列出,不要扩写成需求。
5. 执行:

```bash
complete_stage "harness-builder" "SCOPE_READY" "build-scope 已产出" "${output_dir}/build-scope.md"
```

禁忌: scope 未对齐前不写业务代码、不安装依赖、不初始化新项目。

### BUILD

输入: `build-scope.md`、`scope-review.md`、主会话指定的 feature slug 或 slug batch。

步骤:

1. 写 progress,说明当前处理的 slug。
2. 按顺序实现: 基础设施 -> 业务 Service -> 入口层。
3. TDD 只覆盖业务域 Service public 方法。入口层不写单测。
4. 不把业务逻辑写进 Controller/RPC/MQ/Scheduler;入口层只做参数校验、序列化和调 Service。
5. 跑本次新增/修改测试类,再跑测试编译:

```bash
mvn test -Dtest=ClassA,ClassB,...
mvn test-compile
```

若项目不是 Maven,按 `AGENTS.md` 的等价命令执行。

6. 同步更新 `.harness/call-chain/<slug>.md`。
7. 只 stage 本阶段自己改动的文件,不要 stage 用户无关改动。
8. 创建 git commit,提交信息使用简短中文命令式摘要。
9. 如果还有后续 slug,执行 `BUILD_SLICE_DONE`;最后一片执行 `BUILD_DONE`。

```bash
complete_stage "harness-builder" "BUILD_DONE" "构建完成,已提交 commit" "${output_dir}/build-scope.md"
```

禁忌:

- 不写 stub / fake / hardcode response
- 不调测试参数掩盖失败
- 不跑全量测试拖慢流程,除非项目手册明确要求
- 不修改与当前 slug 无关的用户改动

### FIX

输入: `fix-brief.md`、`qa-feedback.md`、`code-review.md`、当前 git diff。

步骤:

1. Read `fix-brief.md`,只修其中阻断项。
2. 按 P0 -> P1 -> QA 阻断问题顺序修根因。
3. 涉及业务流程变化时更新 call-chain。
4. 跑修复涉及测试 + 测试编译。
5. 只 stage 本轮修复文件,创建 git commit。
6. 执行:

```bash
complete_stage "harness-builder" "FIX_DONE" "阻断问题已修复,已提交 commit" "${output_dir}/fix-brief.md"
```

禁忌:

- 不通过改测试期望来让反馈消失
- 不删除 CodeReview/QA 发现问题的触发路径
- 不继续等复审结果

## 基线遗留

若 `state.json.preflight.test_compile.status` 为 `failed_allowed`,把摘要里的失败识别为基线遗留。不要主动修复,除非本轮改动明确触发了同一问题的新失败。
