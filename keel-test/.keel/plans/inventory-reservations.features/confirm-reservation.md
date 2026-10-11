# confirm-reservation — 确认扣减

## 数据模型

- 结构变更：无
- 引用：[reserve-stock](reserve-stock.md#数据模型)

## 功能时序图

- 时序图：生成

```plantuml
@startuml
actor 调用方 as Caller
participant 库存接口 as API
participant 库存处理 as Service
database 库存库 as DB
Caller -> API : 确认订单预占
API -> Service : 处理确认
group 确认事务 [新增]
  Service -> DB : 查询预占状态
  alt 已确认
    Service --> API : 返回原确认结果，不再扣减
  else 有效预占
    Service -> DB : 一同扣减库存并标记已确认
    Service --> API : 返回确认结果
  else 已取消或不存在
    Service --> API : 拒绝确认，库存不变
  end
end
API --> Caller : 结果
@enduml
```

- 沿用[创建预占的写事务约束](reserve-stock.md#功能时序图)。扣减仅在 `stock >= quantity` 时执行，扣减和状态条件更新各须命中一行；任何失败全部回滚，按下文契约返回库存数据不一致。
- 与取消并发时，以获得写锁后的状态判断，只能成功进入一种终态。确认后账面量和预占量同减，可用量不变。

## 接口设计

- 引用：[reserve-stock](reserve-stock.md#接口设计)

### POST `/reservations/{order_id}/confirm`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| order_id（路径） | String | 是 | 原订单标识，作为一个 URL 编码的路径段 |

无请求体。成功返回 200 和共享预占响应，`status` 为 `CONFIRMED`；重复确认相同。未知预占返回 404，已取消或库存数据不一致返回 409；错误体及数据库异常沿用共享契约。

## 代码改造点

- `inventory/service.py`：在同一写事务内扣减账面库存并确认预占，按状态处理重复与冲突。
- `inventory/http.py`：增加确认入口，解析订单路径并返回业务结果。
