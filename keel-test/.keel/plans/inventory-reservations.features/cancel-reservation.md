# cancel-reservation — 取消释放

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
Caller -> API : 取消订单预占
API -> Service : 处理取消
group 取消事务 [新增]
  Service -> DB : 查询预占状态
  alt 已取消
    Service --> API : 返回原取消结果，不再释放
  else 有效预占
    Service -> DB : 标记已取消，恢复可用库存
    Service --> API : 返回取消结果
  else 已确认或不存在
    Service --> API : 拒绝取消，库存不变
  end
end
API --> Caller : 结果
@enduml
```

- 沿用[创建预占的写事务约束](reserve-stock.md#功能时序图)。只将 `RESERVED` 条件更新为 `CANCELLED`，不改 `stock`；状态更新须命中一行，失败回滚并返回冲突。
- 有效预占量只统计 `RESERVED`，取消后可用量自然恢复；确认和取消按获得写锁后的状态判断，终态不互换。

## 接口设计

- 引用：[reserve-stock](reserve-stock.md#接口设计)

### POST `/reservations/{order_id}/cancel`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| order_id（路径） | String | 是 | 原订单标识，作为一个 URL 编码的路径段 |

无请求体。成功返回 200 和共享预占响应，`status` 为 `CANCELLED`；重复取消相同。未知预占返回 404，已确认返回 409；错误体及数据库异常沿用共享契约。

## 代码改造点

- `inventory/service.py`：在写事务内取消有效预占，按状态拒绝取消已确认记录。
- `inventory/http.py`：增加取消入口，解析订单路径并返回业务结果。
