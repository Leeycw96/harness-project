# 库存预占流程索引维护

**UPDATED**。新增 [库存预占生命周期](../../../../call-chain/inventory-reservation.md)，记录创建、确认、取消入口和当前状态机。

## 检查范围与判断

- 角色：已加载 `.codex/agents/keel-call-chain.toml` 指向的 `keel-call-chain.md`，遵循项目 `AGENTS.md` 及本任务四份 Spec。
- 实现范围：`fbad27c..54433356b72081445ef6b0d82804d37a38ae1ffe`。核对 `inventory/` 实际代码、迁移，参照本目录 [plan.md](plan.md) 与 [qa-feedback.md](qa-feedback.md)。
- 原有索引：`.keel/call-chain/` 不存在。新增条件成立：同一预占由三个外部 HTTP 入口推进，并从 `RESERVED` 到达两个互斥终态。
- 粒度：创建、确认、取消共同完成按订单预留库存的目标，合为一个流程；库存查询仅观察结果，无独立状态机，不另建流程文档。

## 入口与状态证据

| 事实 | 代码证据 |
| --- | --- |
| 新增三个写入口：创建、确认、取消 | `inventory/http.py:24`、`:34`、`:45`；`Handler.do_POST` 分派到三个真实业务函数 |
| 创建有效预占；同订单相同请求返回任何已有状态，终态不重开 | `inventory/service.py:65`、`:71`、`:88`；`reserve_stock` 插入 `RESERVED` |
| 确认扣减库存并写 `CONFIRMED`；重复确认不扣减，取消终态拒绝确认 | `inventory/service.py:96`、`:103`、`:109` |
| 取消写 `CANCELLED`，释放有效预占；重复取消不再释放，确认终态拒绝取消 | `inventory/service.py:119`、`:126`；查询仅汇总 `RESERVED`（`:14`） |
| 写事务串行推进，失败回滚；503 由调用方重试，500 无额外状态 | `inventory/service.py:32`、`:40`；数据库状态值约束 `inventory/migrations/002_reservations.sql:5` |
| 无异步入口、自动过期或后台补偿 | 已完整核对 `inventory/http.py`、`inventory/service.py`、`inventory/db.py` 和两份迁移，推进操作均在同步 HTTP 请求内完成 |

## 更新与提交

- 更新文件：`.keel/call-chain/inventory-reservation.md`，包含业务步骤、入口目录、状态表、自包含 PlantUML 图、流转条件、实际状态写入符号、失败和重试说明。
- 独立文档提交：`6027483bda0877fab1c479fbdf3bca2083a41623`（`库存预占: 新增生命周期流程索引`），仅新增上述流程文档。
- `.keel/` 被项目忽略规则覆盖；只对流程文档显式加入版本控制。本报告沿用迭代资料约定保存，不混入文档提交；未修改忽略规则或运行状态。

## 验证与遗留

- `git diff --cached --check`：提交前退出码 0；暂存范围仅一份流程文档。
- 文档静态核对：21 处完整文件行号均有效，图中的三个状态与迁移约束一致，三个 HTTP 写入口齐全；手动核对图、表、文字及实际状态写入位置一致。
- `git show --stat HEAD`：仅流程文档，78 行新增；`git status --short --untracked-files=all`：空输出。
- 业务测试未重跑；本次只维护文档，业务验收证据引用独立 QA 报告，不将其表述为本角色执行结果。
- 流程索引没有未解决项或代码证据缺口。真实用户对 Plan HTML 的审阅仍待确认，沿用 QA 标记；本次文档维护不改变该确认状态。
