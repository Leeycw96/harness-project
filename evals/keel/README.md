# Keel 强模型回归评估

本目录用于比较 Keel 瘦身前后的需求结构化、构建和审查效果。评估基线固定为提交 `e7d6183`，目标模型只覆盖强模型。

## 运行约定

1. 对同一个 case 使用相同模型、模型配置和仓库快照。
2. baseline 与 candidate 各运行至少 3 次。
3. 自动记录 Markdown 计划、构建、测试、git diff、Agent 结论、调用次数和 token。
4. 按 `rubric.md` 盲评模型产物，不向评审者透露版本。
5. 任一 hard gate 退化时，candidate 不得进入下一期。

仓库不绑定具体模型 CLI。执行环境负责把 `cases.md` 中的任务映射到隔离测试仓库，并把结果写入外部 eval 报告；不要在本仓库或其他长期项目中运行 Keel 端到端任务。

## 本地静态检查

`baseline-2.1.0.tsv` 记录改造前的指令体量。改造后运行：

```bash
scripts/keel-metrics.sh
scripts/check-runtime-contract.sh
scripts/check-slimming-targets.sh
```

`check-runtime-contract.sh` 同时运行 ASO 架构边界、临时部署和运行协议兼容检查。`keel-metrics.sh` 分别报告角色 A、默认 Agent 固定输入和完整 A/S/O 指令总量。缩减门禁计入 Agent 必须加载的任务要求与 Spec 约束，对照旧基线，不把搬文件当作上下文节省。

Plan 另外报告 Planner 角色体量、默认起草任务输入和完整 A/S/O 指令总量；不把 Skill 变短等同于总输入减少。

体量按当前两段输入协议统计：主会话读取所属 Skill；Agent 的固定输入为角色 Markdown、注册 TOML 和实际选用的场景 Spec，章节引用只统计该节及子节。`default-task-input` 和 `fixed-input` 均报告这部分固定内容，不把 Skill 步骤、运行助手或兼容入口当作 Agent 输入；本次动态任务、项目资料及真实 token 用量由行为 eval 另行记录，固定体量不代表整轮成本。共享代码与测试质量计入完整固定输入，Builder/QA 的历史缩减比较继续排除当时已独立的代码规约。

这些契约检查不执行模型开发任务。静态体量与协议兼容均不能替代行为 eval；历史 CallChain 配对结果也不代表新版本重新通过模型评测。

开发入口已统一为 keel-dev，体量以 codex-dev-* 报告，缩减门禁继续对照历史 full 基线；已合并的 fast 不再单独计量。历史基线及评测结果保留，不能据此宣称新流程通过真实模型评估。

## CallChain 按需调度

第二期先使用 10 个受控 Builder diff，各运行 3 轮隔离 prefilter 和 CallChain 评审：

```bash
scripts/check-call-chain-controlled-eval.sh
```

结果保存在 `results/call-chain-shadow/`。启用门槛：

- 至少 10 个已完成 shadow 样本。
- 至少 5 个主会话 `noop` 样本。
- 至少 3 个 Agent `UPDATED` 正样本。
- 不得出现主会话 `noop`、Agent `UPDATED` 的漏判。

`run`/`NOOP` 属于安全的保守误报，只影响节省比例，不影响准入安全性。

门槛通过后，新开发 run 使用 `on-demand` 模式：prefilter 为 `noop` 时跳过 CallChain Agent，为 `run` 时保持独立评审。

4.0.5 起，主会话依据 Builder 返回的本轮整体流程影响直接决定是否调度，缺失或不确定时调度独立 DocWriter。新任务不生成状态文件或预判台账；上述 diff 评测保留为历史基线，不代表新流程已通过模型评测。
