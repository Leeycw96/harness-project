# 库存预占初验

**APPROVED**。隔离评估中的三个功能全部完成，无阻断项。

## 范围与依据

Builder：`keel-builder`（`/root/inventory_builder`）。提交：`54433356b72081445ef6b0d82804d37a38ae1ffe`；基线：`fbad27c`。

依据 [plan.md](plan.md)、三个功能文档及当前 delivery、acceptance、code-quality、document-writing、qa-scoring Spec，检查库存实现、测试、迁移和 README。QA 补测与报告保存在本目录，未改业务、方案或部署文件，未提交代码。

## 功能完成情况

三个目标的全部验收条件通过。详细条目见 [qa-score.json](qa-score.json) 的 `goal_results`，执行证据见 [qa-suite.log](qa-suite.log) 和 [qa-probes.log](qa-probes.log)。

| 目标 | 已完成行为 | 证据位置 |
| --- | --- | --- |
| reserve-stock | 库存足够时创建，包含恰好用尽；重试不多占、并发不超卖，错误不写入；查询与重启数据正确 | suite:69–70、75、77–83、85；probes:1、5 |
| confirm-reservation | 确认只扣一次，可用量不变；与取消竞争只进入一种终态，冲突或更新失败不改库存 | suite:68、71–73、76、84；probes:4 |
| cancel-reservation | 取消只释放一次、不改账面库存；终态订单不重新预占，冲突或更新失败不改记录 | suite:37–43、56、67–68、72、84；probes:2–3 |

## 代码、测试与关联影响

代码与测试质量通过。HTTP 负责解析和响应，业务模块用真实 SQLite 事务处理库存；测试断言响应、库存和状态。迁移保留旧商品，已有查询与健康检查正常。职责、约束、错误响应和回滚的逐项证据见评分记录的 `checks`。

## 实际验证

以下是既有初验结果，本次仅精简报告，未重跑业务检查。工作目录：`/private/var/folders/4y/0v4n5r7d5pz0xlp9s1kt81j40000gn/T/keel-backend-e2e-1xrmqpy4/project`。

- 语法与入口：`python3 -m compileall -q inventory tests`、`python3 -m py_compile .keel/iterations/codex/inventory-e2e/run-1/qa-probes.py`、`python3 -m inventory.http --help` 均退出 0。项目无独立构建或类型检查步骤。
- 完整测试：`python3 -m unittest discover -s tests -v`，30 项通过、15.374 秒（suite:89–91）。
- QA 补测：`python3 .keel/iterations/codex/inventory-e2e/run-1/qa-probes.py`，5 项通过、0.251 秒（probes:8–10），包含并发重复确认/取消、跨商品隔离、取消失败回滚和真实进程重启。
- 交付检查：`git diff --check fbad27c..54433356b72081445ef6b0d82804d37a38ae1ffe` 通过；同范围的 `git diff --name-status` 仅涉及库存代码、测试及 README 共 7 个文件；`git status --short --untracked-files=all` 空输出。报告目录按项目约定忽略。

## 阻断、观察与待确认事项

- 无阻断项或本次实现必需的验证缺口。
- 默认沙箱曾限制本地端口，获准重跑后全部通过，属于已解除的环境限制。
- 外部改坏库存时，确认保护返回 409 并保持原数据；该非阻断观察已有测试证据。
- 真实用户对 Plan HTML 的审阅仍待确认，本结论仅评价隔离实现，不表示用户批准。

## 评分记录

初验 [qa-score.json](qa-score.json) 保持原样：目标 3/3，五个规范检查组均通过，读取校验无错误（[校验记录](qa-score-validation.log)）。补充测试见 [qa-probes.py](qa-probes.py)。
