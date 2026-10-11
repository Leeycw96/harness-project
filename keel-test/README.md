# 库存预占服务 · Keel 流程试验

商品库存支持按订单预占、确认扣减和取消释放。用这个后端任务完整试验 Keel 的 Plan、Dev、Fix 产物。

- [Plan HTML](.keel/plans/inventory-reservations.html)
- [Fix HTML](.keel/bugs/BUG-001/bug.html)
- [测试结论](TEST_REPORT.md)

## 运行

无需安装业务依赖，初始商品 DEMO 有 10 件库存。

```bash
python3 -m inventory.http --db /tmp/inventory-demo.sqlite3 --port 8080
python3 -m unittest discover -s tests -v
```

接口：GET /health、GET /inventory/{sku}、POST /reservations，以及预占记录的 confirm/cancel 操作。具体契约见 Plan。

Fix 使用明确标记的库存边界故障样本。自动推进仅使用隔离测试确认，真实用户对 HTML 的审阅仍待确认。
