# CallChain 按需调度受控评测

日期：2026-07-25

## 方法

- 使用 `evals/harness/fixtures/call-chain-shadow/cases.md` 的 10 个 Builder diff。
- 3 个独立 prefilter Agent 各评审一轮，只输出 `noop/run`。
- 3 个独立 CallChain Agent 各评审一轮，只输出 `NOOP/UPDATED`。
- 两类 Agent 互不可见对方结果；同轮同 case 配成一组，共 30 组。
- `noop/UPDATED` 视为 unsafe 漏判；`run/NOOP` 是安全的保守误报。

## 结果

| 指标 | 结果 |
|---|---:|
| 配对样本 | 30 |
| prefilter `noop` | 14 |
| CallChain `UPDATED` | 12 |
| 完全一致 | 26 |
| unsafe 漏判 | 0 |
| prefilter 跨轮次波动 case | 1 |
| CallChain 跨轮次波动 case | 0 |

CASE-05 的参数校验变更在第三轮被保守判为 `run`，另外两轮为 `noop`；CallChain 三轮均为 `NOOP`。CASE-06 的单步同步 CRUD 三轮均为 `run/NOOP`。两者只降低跳过比例，不会漏掉应更新的调用链。

CASE-07 至 CASE-10 覆盖 MQ、Scheduler、callback 和多阶段状态流转，12 组均为 `run/UPDATED`。

## 结论

评测超过 10 个完整样本、5 个 prefilter `noop` 和 3 个 Agent `UPDATED` 的最低要求，且 unsafe 为 0，允许启用 CallChain 按需调度。

受控 fixtures 不替代生产观察。启用后继续保留判定原因；遇到任一入口、异步或生命周期变化以及不确定情况时仍保守调度 CallChain Agent。

复核命令：

```bash
scripts/check-call-chain-controlled-eval.sh
```
