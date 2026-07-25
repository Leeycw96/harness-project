# CallChain Shadow Fixtures

本目录用于第二期 CallChain 按需调度的受控评测。

- `cases.md` 只提供 Builder diff 和必要的基线上下文，不包含期望结论。
- Prefilter 评审只输出 `noop` 或 `run`。
- CallChain 评审只输出 `NOOP` 或 `UPDATED`。
- 两类评审相互隔离，每个 case 重复 3 次。
- 汇总时按同一轮次配对；`noop`/`UPDATED` 是 unsafe 漏判。

这些 fixtures 衡量判定边界，不替代后续生产 run 观察。
