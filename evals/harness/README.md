# Harness 强模型回归评估

本目录用于比较 Harness 瘦身前后的需求结构化、构建、审查和恢复效果。评估基线固定为提交 `e7d6183`，目标模型只覆盖强模型。

## 运行约定

1. 对同一个 case 使用相同模型、模型配置和仓库快照。
2. baseline 与 candidate 各运行至少 3 次。
3. 自动记录 XML、构建、测试、git diff、完成 tag、Agent 调用次数和 token。
4. 按 `rubric.md` 盲评模型产物，不向评审者透露版本。
5. 任一 hard gate 退化时，candidate 不得进入下一期。

仓库不绑定具体模型 CLI。执行环境负责把 `cases.md` 中的任务映射到隔离测试仓库，并把结果写入外部 eval 报告；不要在本仓库或其他长期项目中运行 Harness 端到端任务。

## 本地静态检查

`baseline-2.1.0.tsv` 记录改造前的指令体量。改造后运行：

```bash
scripts/harness-metrics.sh
scripts/check-runtime-parity.sh
scripts/check-slimming-targets.sh
```

静态体量只衡量上下文成本，不能替代行为 eval。

## CallChain Shadow

第二期 shadow 模式会在 full run 的 `state.json.call_chain.prefilter` 中记录主会话预判和独立 CallChain Agent 结论。汇总：

```bash
scripts/summarize-call-chain-shadow.sh /path/to/.harness/iterations
scripts/summarize-call-chain-shadow.sh --check-ready /path/to/.harness/iterations
```

真实跳过 CallChain 的最低准入条件：

- 至少 10 个已完成 shadow 样本。
- 至少 5 个主会话 `noop` 样本。
- 至少 3 个 Agent `UPDATED` 正样本。
- 不得出现主会话 `noop`、Agent `UPDATED` 的漏判。

`run`/`NOOP` 属于安全的保守误报，只影响节省比例，不影响准入安全性。
