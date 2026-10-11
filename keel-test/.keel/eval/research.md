# 库存预占调研

当前仅有 products 表、GET /health 与 GET /inventory/{sku}，两个基线测试通过。来源：inventory/service.py、inventory/http.py、inventory/migrations/001_products.sql、tests/test_inventory.py。

本期新增创建预占、确认扣减、取消释放。查询增加有效预占量和可用量；SQLite 同一事务内判断可用量并修改数据，避免并发超卖。同一订单相同请求幂等，不同商品或数量冲突。确认只扣减一次，取消只释放一次；两种终态不能互换。

新增预占表、唯一订单约束、状态机与三个操作接口。规则放 service.py，HTTP 层负责解析及响应。本期没有过期、认证或外部系统；三个功能都生成时序图，并提供总览、状态机和 ER 图。没有缺失的关键选型，具体契约由方案统一定义。

原生执行：/root/inventory_planner_research；只读调研，结束时临时项目工作区无改动。真实用户对 HTML 的审阅待确认。
