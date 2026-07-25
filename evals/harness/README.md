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
