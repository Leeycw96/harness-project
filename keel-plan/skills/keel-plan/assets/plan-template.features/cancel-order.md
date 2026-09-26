# cancel-order — 发起取消

## 数据模型

- 结构变更：新增字段

orders 新增可空 refund_requested_at，表示首次申请退款的时间；旧订单保留 NULL，不回填。以下为 PostgreSQL 示例，实际计划须替换为项目数据库方言及迁移约定。status 为已有文本字段，增加 REFUND_PENDING 业务值不修改列类型。

```plantuml
@startuml
hide circle
entity "orders（订单）" as orders {
  * id : varchar(64) <<PK>>
  --
  * status : varchar(32)
  refund_requested_at : timestamp [新增，可空]
}
entity "refund_tasks（已有退款任务）" as refunds {
  * request_id : varchar(64) <<PK>>
  --
  * order_id : varchar(64)
}
orders ||..o{ refunds : id = order_id（逻辑关联）
@enduml
```

仅列本次相关字段，其他既有字段省略；request_id 沿用现有唯一主键，不新增数据库外键。

```sql
ALTER TABLE orders ADD COLUMN refund_requested_at TIMESTAMP NULL;
```

先执行字段迁移再上线应用。恢复旧应用时保留新增列和已写数据；确认在途退款处理完成后再评估清理，不自动删除列。

## 功能时序图

- 时序图：生成

实现约定：沿用现有可靠任务和退款通道。订单状态、申请时间与退款任务同事务提交；重复请求复用原退款请求 ID，渠道暂时失败时继续使用该 ID 重试。新状态上线前先完成字段迁移与客户端适配。

```plantuml
@startuml
actor 用户
participant "OrderController.cancel" as API
participant "OrderService.requestRefund" as Service
database 订单库 as DB
participant "RefundJob.dispatch" as Job
participant 退款网关 as Gateway
用户 -> API : POST /orders/{id}/cancel
API -> Service : 校验归属、状态与幂等请求
alt 无权或不可取消
Service --> API : 403 或 409
API --> 用户 : 拒绝请求
else 已处理同一请求
Service --> API : 原退款请求 ID 与状态
API --> 用户 : 202 原结果
else 首次有效请求
group 本地事务
Service -> DB : PAID 条件更新为 REFUND_PENDING\n记录 refund_requested_at 并写入退款任务
DB --> Service : 提交成功
end
Service --> API : 状态与退款请求 ID
API --> 用户 : 202 REFUND_PENDING
Job -> DB : 读取已提交退款任务
Job -> Gateway : 使用请求 ID 幂等退款
alt 网关暂时失败
Gateway --> Job : 可重试错误
Job -> DB : 保留待重试任务
else 接受请求
Gateway --> Job : 已接受，等待回调
end
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
