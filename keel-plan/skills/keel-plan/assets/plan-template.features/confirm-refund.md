# confirm-refund — 确认退款

## 数据模型

- 结构变更：无
- 引用：[cancel-order](cancel-order.md#数据模型)

沿用订单状态与退款任务关系；SQL 迁移由 cancel-order 执行，本功能不重复执行。

## 功能时序图

- 时序图：不生成

执行说明（不生成时序图）：沿用渠道验签，按请求 ID 定位订单；退款成功时条件更新 REFUND_PENDING → CANCELLED，并通过既有事务消息保证取消通知去重；失败时保留状态并记录原因。下线新逻辑前停止新取消入口并核对在途退款，不得直接取消未退款订单。

## 接口设计

### POST `/refunds/callback`

入参：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| requestId | String | 是 | 退款请求 ID |
| result | String | 是 | SUCCESS / FAILED |
| signature | String | 是 | 签名 |

出参：200，无响应体。

失败响应：验签失败返回 401，不修改订单。

请求 JSON：

```json
{"requestId": "refund-123", "result": "SUCCESS", "signature": "example-signature"}
```

## 代码改造点

- `src/main/java/example/RefundController.java`，`callback`（新增）：接收退款回调并交给订单服务处理。
- `src/main/java/example/OrderService.java`，`confirmRefund`（新增）：验签后按退款结果幂等更新订单并触发取消通知。
