# 库存预占服务

- 业务流程变化：有
- 判定依据：现状仅能查询库存，没有预留、成交扣减或取消释放阶段（inventory/http.py、inventory/service.py）。目标新增从预占申请到预留库存，再到确认成交或取消释放的生命周期，业务阶段和结果均有变化；规则来自 requirements.md，现状与 .keel/eval/research.md 一致。

## 背景

- User Story：作为下单方，我希望先预留足够的库存，以便多个订单同时申请时不会超卖。
- User Story：作为下单方，我希望成交时扣减库存、放弃时释放库存，以便库存反映订单的实际结果。

## 业务流程总览

### 库存预占生命周期

```plantuml
@startuml
start
:[新增] 申请预占;
if (申请有效且库存足够?) then (是)
  :[新增] 预留库存;
  :[新增] 等待订单成交或放弃;
  if (订单成交?) then (是)
    :[新增] 扣减账面库存，完成确认;
  else (放弃)
    :[新增] 取消预占，恢复可用库存;
  endif
else (否)
  :[新增] 拒绝申请，库存不变;
endif
stop
@enduml
```

## 状态机

### 预占状态机

```plantuml
@startuml
state "RESERVED 有效预占 [新增]" as RESERVED #DCFCE7
state "CONFIRMED 已确认 [新增]" as CONFIRMED #DCFCE7
state "CANCELLED 已取消 [新增]" as CANCELLED #DCFCE7
[*] -[#green]-> RESERVED : [新增] 首次申请成功
RESERVED -[#green]-> CONFIRMED : [新增] 确认成功，账面库存扣减一次
RESERVED -[#green]-> CANCELLED : [新增] 取消成功，可用库存恢复一次
RESERVED -[#green]-> RESERVED : [新增] 重复相同创建
CONFIRMED -[#green]-> CONFIRMED : [新增] 重复确认或相同创建
CANCELLED -[#green]-> CANCELLED : [新增] 重复取消或相同创建
note bottom of CONFIRMED
取消请求被拒绝，不进入 CANCELLED。
end note
note bottom of CANCELLED
确认请求被拒绝，不进入 CONFIRMED。
end note
@enduml
```
