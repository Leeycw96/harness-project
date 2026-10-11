# 库存预占服务

- 业务流程变化：有
- 判定依据：现状仅能查询库存（inventory/http.py、inventory/service.py）；目标新增申请预占、成交确认和取消释放三条业务路径，从触发到成功或拒绝结果均有变化。规则来自 requirements.md，现状与 .keel/eval/research.md 一致。

## 背景

- User Story：作为下单方，我希望先预留足够的库存，以便多个订单同时申请时不会超卖。
- User Story：作为下单方，我希望成交时扣减库存、放弃时释放库存，以便库存反映订单的实际结果。

## 业务流程总览

### 申请预占流程

```plantuml
@startuml
start
:[新增] 提交订单、商品和数量;
if (申请有效?) then (是)
  if (订单已有预占?) then (是)
    if (商品和数量相同?) then (是)
      :[新增] 返回同一预占的当前结果;
    else (否)
      :[新增] 拒绝冲突申请;
    endif
  else (否)
    if (商品存在且库存足够?) then (是)
      :[新增] 预留库存，返回有效预占;
    else (否)
      :[新增] 拒绝申请，库存不变;
    endif
  endif
else (否)
  :[新增] 拒绝无效申请，库存不变;
endif
stop
@enduml
```

### 成交确认流程

```plantuml
@startuml
start
:[新增] 提交成交确认;
if (预占存在?) then (是)
  if (已确认?) then (是)
    :[新增] 返回已确认结果，不再扣减;
  elseif (仍为有效预占且账面库存足够?) then (是)
    :[新增] 扣减账面库存，完成确认;
  else (否)
    :[新增] 拒绝确认，库存不变;
  endif
else (否)
  :[新增] 告知预占不存在;
endif
stop
@enduml
```

### 取消释放流程

```plantuml
@startuml
start
:[新增] 提交取消申请;
if (预占存在?) then (是)
  if (已取消?) then (是)
    :[新增] 返回已取消结果，不再释放;
  elseif (仍为有效预占?) then (是)
    :[新增] 取消预占，恢复可用库存;
  else (否)
    :[新增] 拒绝取消，库存不变;
  endif
else (否)
  :[新增] 告知预占不存在;
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
