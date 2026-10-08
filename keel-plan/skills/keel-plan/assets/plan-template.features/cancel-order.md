# cancel-order — 发起取消

## 数据模型

- 结构变更：新增字段

旧订单的新增字段保留 NULL，不回填。以下为 PostgreSQL 示例，实际计划须替换为项目数据库方言及迁移约定。

```plantuml
@startuml
hide circle
entity "orders（订单）" as orders {
  * id : varchar(64) <<PK>>
  --
  refund_requested_at : timestamp [新增，可空]
}
@enduml
```

```sql
ALTER TABLE orders ADD COLUMN refund_requested_at TIMESTAMP NULL;
```

先执行字段迁移再上线应用。恢复旧应用前停止新取消入口并核对在途退款；恢复时保留新增列和已写数据，确认在途退款处理完成后再评估清理，不自动删除列。

## 功能时序图

- 时序图：生成

```plantuml
@startuml
actor 用户
participant "OrderController.cancel" as API
participant "OrderService.requestRefund" as Service
database 订单库 as DB
participant "RefundJob.dispatch" as Job
participant 退款网关 as Gateway
用户 -> API : POST /orders/{id}/cancel
API -> Service : requestRefund(id, key)
group 沿用订单查询与归属、可取消条件校验（OrderService.cancel）
Service -> DB : 查询并校验订单
end
alt 已有同一请求的退款申请
Service --> API : 原退款请求 ID 与状态
API --> 用户 : 202 原结果
else 首次有效请求
group 本地事务 [修改]
Service -> DB : [修改] PAID 条件更新为 REFUND_PENDING\n[新增] 记录 refund_requested_at 并写入退款任务
DB --> Service : 提交成功
end
Service --> API : 状态与退款请求 ID
API --> 用户 : 202 REFUND_PENDING
Job -> DB : 读取已提交退款任务
Job -> Gateway : 沿用既有退款派发与重试
note over Job,Gateway
本次任务与重试复用同一退款请求 ID
end note
end
@enduml
```

## 接口设计

### POST `/orders/{id}/cancel`

入参沿用：路径 id（String），请求头 Idempotency-Key（String），无请求体。

失败响应：无权操作返回 403，不满足取消条件返回 409。

出参（202，仅列变更）：

| 字段 | 类型 | 变更 |
| --- | --- | --- |
| status | String | 修改：新增枚举 REFUND_PENDING |
| refundRequestId | String | 新增：退款请求 ID |

响应 JSON（变更字段示例）：

```json
{"status": "REFUND_PENDING", "refundRequestId": "refund-123"}
```

## 代码改造点

- `src/main/java/example/OrderService.java`，`cancel` / `requestRefund`（新增）：将直接取消改为事务内记录待退款、申请时间及退款任务。
- `src/main/java/example/Order.java`，`refundRequestedAt`（新增）：映射退款申请时间字段。
- `src/main/resources/db/migration/V42__refund_requested_at.sql`（新增）：增加订单退款申请时间列。
