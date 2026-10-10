# confirm-refund — 确认退款

## 数据模型

- 结构变更：无
- 引用：[cancel-order](cancel-order.md#数据模型)

## 功能时序图

- 时序图：不生成

成功回调按请求 ID 条件更新 REFUND_PENDING → CANCELLED，并在同一事务记录取消通知；重复成功回调不再更新或通知。失败回调保留待退款状态并记录原因。

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

- `src/main/java/example/RefundController.java`：新增退款回调接收并交给订单服务处理。
- `src/main/java/example/OrderService.java`：验签后按退款结果幂等更新订单并触发取消通知。
