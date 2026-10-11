# BUG-001 实施结果

已恢复既有规则：申请数量等于可用库存时允许预占，超过时仍返回 409。依据 `bugs/BUG-001/runs/run-1/approved.md` 与 `approved-investigation.md`；仅用于隔离评估，真实用户对 Fix HTML 的审阅仍待确认。

## 改动与提交

- `inventory/service.py:86`：库存不足判断从 `>=` 改为 `>`，沿用现有事务、状态与接口。
- `tests/test_reservations.py`：新增已有 9 件预占后申请最后 1 件的回归，核对重复请求及不足时库存不变。
- `tests/test_http.py`：新增真实本地 HTTP 等量预占回归，覆盖原 `boundary-order` 申请 10 件、重复申请、不足拒绝、取消释放及确认扣减，核对库存和重复操作。
- 实现提交：`68e10818b5172db30a3bc2cd082ff8beab516436`（`inventory: 修正等量库存预占边界`）。仅包含上述源码和测试；本记录不混入提交。

## 验证

工作目录：`/private/var/folders/4y/0v4n5r7d5pz0xlp9s1kt81j40000gn/T/keel-backend-e2e-1xrmqpy4/project`。

- 修复前先补测试。`python3 -m unittest discover -s tests -p test_reservations.py -k test_reserve_last_available_unit_with_existing_reservation -v`：1 项失败，最后 1 件预占触发 `InventoryError(409, "库存不足")`。
- 修复前 `python3 -m unittest discover -s tests -p test_http.py -k test_exact_stock_reservation_retries_cancel_and_confirm -v`：本地 HTTP 实际返回 `(409, {"error": "库存不足"})`，与预期 200 不符。首次在沙箱内无法绑定本地端口，取得本地测试权限后重跑，得到上述业务失败证据。
- 修复后 `python3 -m compileall -q inventory tests`：退出 0。项目无独立构建或类型检查步骤。
- 修复后 `python3 -m unittest discover -s tests -v`：32 项通过，退出 0（15.793 秒），使用临时数据库与绑定 `127.0.0.1` 的真实 HTTP 服务，启动和 `/health` 检查通过。
- 上述 HTTP 回归复用原请求 `POST /reservations`，订单 `boundary-order`、商品 `DEMO`、数量 10：返回 200 / `RESERVED`，查询为 stock 10、reserved 10、available 0；多申请 1 件返回 409 且库存不变。取消后恢复 10 件可用，重新等量预占并确认后 stock / reserved / available 均为 0；重复操作不重复占用、释放或扣减。
- 原有回归包含并发不能超卖、订单冲突、事务回滚、重启持久化及最大整数等量预占，全部通过。
- `git diff --check`：退出 0。提交后 `git status --short`：无输出。

## 遗留项

本职实施无阻断。独立代码验收与独立原场景复验由主会话安排；本次验证不能替代该阶段结论。真实用户审阅仍待确认。本次未改规范、方案、流程索引或运行记录。
