# 订单取消支持退款确认

## 功能目标

### cancel-order — 发起取消

- 文档：[cancel-order](plan-template.features/cancel-order.md)
- 依赖：无
- 目标：支持已支付订单申请取消，提供可识别的待退款状态和可追踪的退款申请结果。

验收标准：

- 首次取消由 PAID 进入 REFUND_PENDING，记录退款申请时间并返回退款请求 ID。
- 同一请求重复提交返回同一 ID，不重复发起退款。
- 无权操作或不满足取消条件时拒绝请求，订单与退款数据保持不变。
- 退款渠道暂时不可用时申请不丢失，恢复后能够继续处理。
- 等待退款期间不得提前进入 CANCELLED。

### confirm-refund — 确认退款

- 文档：[confirm-refund](plan-template.features/confirm-refund.md)
- 依赖：cancel-order
- 目标：支持接收退款结果，退款成功后完成订单取消，失败时保留待退款状态及失败原因。

验收标准：

- 有效成功回调将 REFUND_PENDING 改为 CANCELLED，并只发送一次取消通知。
- 不可信的退款回调被拒绝，不修改订单。
- 失败回调保留待退款状态并记录原因，不提前取消订单。
- 重复成功回调不重复更新订单或发送通知。
