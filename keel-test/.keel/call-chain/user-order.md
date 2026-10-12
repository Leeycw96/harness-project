# 用户下单业务流程

当前实现覆盖客户通过 HTTP API 下单时的库存处理：预占库存，随后确认扣减或取消释放。

## 主流程说明

1. 客户下单：库存充足时预占所需库存，减少可用库存。
2. 客户确认：扣减账面库存，结束预占。
3. 客户取消：释放预占，恢复可用库存。确认与取消是两个分支。

## 状态机

```text
未创建 --步骤1：客户下单并预占库存--> RESERVED
RESERVED --步骤2：客户确认并扣减库存--> CONFIRMED
RESERVED --步骤3：客户取消并释放预占--> CANCELLED
```

“未创建”是概念起点，不是持久化状态。`RESERVED` 表示已预占；`CONFIRMED`、`CANCELLED` 为终态。

## 业务入口

| 主流程步骤 | HTTP 入口 | 业务实现 |
| --- | --- | --- |
| 1. 客户下单 | `POST /reservations` | `inventory/service.py` 的 `reserve_stock` |
| 2. 客户确认 | `POST /reservations/{order_id}/confirm` | `inventory/service.py` 的 `confirm_reservation` |
| 3. 客户取消 | `POST /reservations/{order_id}/cancel` | `inventory/service.py` 的 `cancel_reservation` |
