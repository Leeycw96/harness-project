# reserve-stock — 创建预占

## 数据模型

- 结构变更：新增表
- SQL迁移：需要

```plantuml
@startuml
hide circle
entity "products" as products {
  * sku : TEXT <<PK>>
}
entity "reservations [新增]" as reservations #DCFCE7 {
  * order_id : TEXT <<PK, NOT NULL>>
  --
  sku : TEXT <<FK, NOT NULL>>
  quantity : INTEGER <<NOT NULL, 正整数>>
  status : TEXT <<NOT NULL, RESERVED / CONFIRMED / CANCELLED>>
}
products ||--o{ reservations : 实际外键；一个商品可有多个预占
@enduml
```

```sql
CREATE TABLE IF NOT EXISTS reservations (
    order_id TEXT PRIMARY KEY NOT NULL,
    sku TEXT NOT NULL REFERENCES products(sku),
    quantity INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('RESERVED', 'CONFIRMED', 'CANCELLED'))
);
CREATE INDEX IF NOT EXISTS idx_reservations_sku_status ON reservations(sku, status);
```

初始化在现有迁移后执行新增迁移，保留原商品数据；新表初始为空。回退应用时先停用预占写入口并处理有效预占，保留新表和已写数据。

## 功能时序图

- 时序图：生成

```plantuml
@startuml
actor 调用方 as Caller
participant "inventory.http [新增入口]" as API
participant "inventory.service [新增操作]" as Service
database SQLite as DB
Caller -> API : 创建预占
API -> Service : 已解析的订单、商品和数量
alt 参数无效
  Service --> API : 400 参数错误
else 参数有效
  group 写事务 [新增]
    Service -> DB : BEGIN IMMEDIATE
    Service -> DB : 按 order_id 查询预占
    alt 已有预占，商品和数量相同
      Service -> DB : COMMIT，不修改记录
      Service --> API : 原预占的当前状态
    else 已有预占，商品或数量不同
      Service -> DB : ROLLBACK
      Service --> API : 409 订单预占冲突
    else 新订单
      Service -> DB : 查询商品及 RESERVED 数量之和
      alt 商品不存在
        Service -> DB : ROLLBACK
        Service --> API : 404 商品不存在
      else quantity 大于 stock 减有效预占量
        Service -> DB : ROLLBACK
        Service --> API : 409 库存不足
      else 库存足够，包含恰好相等
        Service -> DB : 新增 RESERVED 记录；不改 stock
        Service -> DB : COMMIT
        Service --> API : 已保存的预占
      end
    end
  end
end
API --> Caller : 结果或明确错误
note over Service,DB
现有 db.connect 为自动提交模式，写操作须显式开启事务。
创建、确认、取消均在获得写锁后读取和修改，连接用后关闭。
等待写锁沿用 10 秒；超时回滚并返回 503，可重试同一订单。
其他数据库异常回滚并返回 500；提交成功后才返回成功。
提交后响应丢失时，重试读取同一记录，不重复占用。
end note
@enduml
```

写锁选择依据：[SQLite 事务说明](https://www.sqlite.org/lang_transaction.html)。库存查询使用单条汇总查询，同时取 `stock` 和仅 `RESERVED` 的数量之和，保证三个数字来自同一快照。

## 接口设计

### POST `/reservations`

请求体必须是 JSON 对象；标识按原字符串匹配，不自动去空格或改大小写。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| order_id | String | 是 | 非空白订单标识，同时作为唯一预占标识 |
| sku | String | 是 | 非空白商品标识 |
| quantity | Integer | 是 | 1 至 9223372036854775807；拒绝布尔值、小数和数字字符串 |

成功均返回 200，下表是三个写接口共用的完整预占响应。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| order_id | String | 是 | 原订单标识 |
| sku | String | 是 | 原商品标识 |
| quantity | Integer | 是 | 原预占数量 |
| status | String | 是 | 当前状态：RESERVED、CONFIRMED 或 CANCELLED |

响应 JSON 示例：

```json
{"order_id":"order-001","sku":"DEMO","quantity":2,"status":"RESERVED"}
```

同一订单、商品和数量重试返回同一记录及当前状态，终态记录也保留；不重新激活。商品或数量不同始终返回冲突，先于商品存在性和剩余库存判断。

三个写接口共用错误响应 `{"error":"原因"}`。格式错误、缺字段或类型/范围错误返回 400；未知商品返回 404；订单冲突或库存不足返回 409。写锁等待超时返回 503，其他数据库异常返回 500；失败不改变库存。

### GET `/inventory/{sku}`

沿用现有商品查询和未知商品的 404；无请求体。成功仍返回 200，保留原字段，仅新增：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| reserved | Integer | 是 | 仅 RESERVED 记录的数量之和；没有记录时为 0 |
| available | Integer | 是 | stock 减 reserved |

响应 JSON（新增字段局部示例）：

```json
{"reserved":2,"available":8}
```

## 代码改造点

- `inventory/migrations/002_reservations.sql`：新增预占表、订单唯一约束和商品状态索引。
- `inventory/db.py`：初始化加载新增迁移，沿用文件数据库和外键约束。
- `inventory/service.py`：实现创建预占、显式事务和公共错误规则，库存查询增加有效预占量与可用量。
- `inventory/http.py`：增加创建预占入口、JSON 参数解析和错误响应。
