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
participant 库存接口 as API
participant 库存处理 as Service
database 库存库 as DB
Caller -> API : 申请预占商品
API -> Service : 处理申请
group 预占事务 [新增]
  Service -> DB : 查询订单已有预占
  alt 已有相同申请
    Service --> API : 返回原预占的当前结果
  else 同一订单的申请内容不同
    Service --> API : 拒绝冲突申请
  else 新订单
    Service -> DB : 核实商品与可用库存
    alt 商品存在且库存足够（包含等量）
      Service -> DB : 保存有效预占，不扣账面库存
      Service --> API : 返回预占结果
    else 商品不存在或库存不足
      Service --> API : 拒绝申请，库存不变
    end
  end
end
API --> Caller : 结果
@enduml
```

- 参数按下文接口约定校验。相同订单的申请冲突先于商品和库存判断；原记录即使已确认或取消也不重新激活。
- 创建、确认、取消共用 `BEGIN IMMEDIATE` 写事务，先获得写锁再读取并修改。失败全部回滚，提交成功后返回，连接用后关闭；沿用 10 秒等待，超时及数据库错误按接口契约响应。
- 库存查询用单条汇总查询同时取账面量和有效预占量，保证数字来自同一快照；响应丢失后重试读取原记录，不重复占用。

事务选择依据：[SQLite 事务说明](https://www.sqlite.org/lang_transaction.html)。

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
