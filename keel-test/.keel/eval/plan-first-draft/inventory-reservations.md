# 库存预占服务

## 功能目标

### reserve-stock — 创建预占

- 文档：[reserve-stock](inventory-reservations.features/reserve-stock.md)
- 依赖：无
- 目标：按订单预留商品库存，并让查询显示账面库存、预占量和可用量。

验收标准：

- 正整数数量小于或等于可用库存时创建成功；恰好用尽可用库存也允许。
- 同一订单重复相同申请返回同一预占，不重复占用；换商品或数量时拒绝。
- 已确认或已取消的订单重复申请不会重新预占。
- 商品不存在、数量无效或库存不足时拒绝，库存保持不变。
- 多个订单同时申请不会超卖，服务重启后仍能查询保存的库存和预占结果。
- 查询同时显示账面库存、仍被占用的数量和剩余可用数量。

### confirm-reservation — 确认扣减

- 文档：[confirm-reservation](inventory-reservations.features/confirm-reservation.md)
- 依赖：reserve-stock
- 目标：将有效预占确认为成交，并且只扣减一次账面库存。

验收标准：

- 首次确认有效预占后，账面库存和预占量减少相同数量，可用量保持不变。
- 重复确认返回已确认结果，不再次扣减。
- 已取消或不存在的预占不能确认，库存保持不变。
- 同一预占同时收到确认和取消时，只能成功进入其中一种终态。

### cancel-reservation — 取消释放

- 文档：[cancel-reservation](inventory-reservations.features/cancel-reservation.md)
- 依赖：reserve-stock
- 目标：取消有效预占，恢复可用库存，并且只释放一次。

验收标准：

- 首次取消有效预占后，账面库存不变，预占量减少，可用量恢复相同数量。
- 重复取消返回已取消结果，不再次释放。
- 已确认或不存在的预占不能取消，库存保持不变。
- 取消后重复创建同一订单不会重新占用库存。
