# cancel-order — 发起取消

## 数据模型

- 结构变更：新增字段

旧订单的新增字段保留 NULL，不回填。以下为 PostgreSQL 示例，实际计划须替换为项目数据库方言及迁移约定。

### 订单域

```plantuml
@startuml
hide circle
entity "orders（订单）" as orders {
  * id : varchar(64) <<PK>> — 订单编号
  --
  refund_requested_at : timestamp [新增，可空] — 申请退款时间
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
participant 订单接口 as API
participant 订单服务 as Service
database 订单库 as DB
participant 退款派发 as Job
participant 退款渠道 as Gateway
用户 -> API : 申请取消订单
API -> Service : 处理取消申请
Service -> DB : 沿用订单与取消条件校验
alt 已有同一退款申请
  Service --> API : 返回原申请结果
  API --> 用户 : 当前退款状态
else 首次允许取消
group 本地事务 [修改]
  Service -> DB : 标记待退款，保存申请时间与退款任务
end
  Service --> API : 返回退款申请结果
  API --> 用户 : 退款处理中
  Job -> DB : 读取已保存退款任务
  Job -> Gateway : 沿用退款派发与重试
end
@enduml
```

- 事务内按 `PAID` 条件更新为 `REFUND_PENDING`，记录 `refund_requested_at` 并写入退款任务；任一失败全部回滚，提交后才返回成功。
- 派发与重试复用同一退款请求 ID；已有查询、归属和渠道校验规则沿用 `OrderService.cancel`。

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

- `src/main/java/example/OrderService.java`：将直接取消改为事务内记录待退款、申请时间及退款任务。
- `src/main/java/example/Order.java`：映射新增的退款申请时间。
- `src/main/resources/db/migration/V42__refund_requested_at.sql`：新增订单退款申请时间列迁移。
