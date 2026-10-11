# confirm-reservation — 确认扣减

## 数据模型

- 结构变更：无
- 引用：[reserve-stock](reserve-stock.md#数据模型)

## 功能时序图

- 时序图：生成

```plantuml
@startuml
actor 调用方 as Caller
participant "inventory.http [新增入口]" as API
participant "inventory.service [新增操作]" as Service
database SQLite as DB
Caller -> API : 确认订单预占
API -> Service : order_id
group 写事务 [新增]
  Service -> DB : BEGIN IMMEDIATE
  Service -> DB : 按 order_id 查询预占
  alt 预占不存在
    Service -> DB : ROLLBACK
    Service --> API : 404 预占不存在
  else 已为 CONFIRMED
    Service -> DB : COMMIT，不扣减
    Service --> API : 同一已确认记录
  else 已为 CANCELLED
    Service -> DB : ROLLBACK
    Service --> API : 409 已取消，不能确认
  else 为 RESERVED
    Service -> DB : stock >= quantity 时扣减 quantity
    alt 更新未成功，库存数据不一致
      Service -> DB : ROLLBACK
      Service --> API : 409 库存数据不一致
    else 扣减成功
      Service -> DB : 仅把 RESERVED 改为 CONFIRMED
      Service -> DB : COMMIT
      Service --> API : 已确认记录
    end
  end
end
API --> Caller : 结果或明确错误
note over Service,DB
扣减和状态更新一起提交；任一异常回滚，未提交前不返回成功。
两次条件更新均须影响一行，否则回滚并返回库存数据不一致。
与创建共用写锁等待、错误处理和连接关闭规则。
并发确认、取消按获得写锁后的状态决定，只能进入一种终态。
确认后 stock 和有效预占量同减，可用量不变。
end note
@enduml
```

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
