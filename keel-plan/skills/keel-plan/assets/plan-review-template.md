# 订单取消支持退款确认

- 业务流程变化：有
- 判定依据：示例中取消完成由申请后立即完成改为等待退款结果确认，改变业务阶段顺序与完成时点；实际计划须以流程索引和代码核实。

## 背景

- User Story：作为购买者，我希望取消已支付订单后看到退款处理中，以便知道退款尚未完成。
- User Story：作为购买者，我希望退款成功后再看到订单已取消，以便确认交易已经结束。

## 业务流程总览

### 订单取消与退款确认流程

```plantuml
@startuml
start
:购买者申请取消已支付订单;
if (允许取消？沿用现有条件) then (是)
  :[修改] 登记退款申请，订单待退款;
  :沿用退款渠道发起退款;
  :[新增] 等待退款结果;
  if (退款成功?) then (是)
    :[修改] 完成订单取消并通知用户;
  else (否)
    :保留待退款状态并记录原因;
  endif
else (否)
  :告知不能取消;
endif
stop
@enduml
```

## 状态机

### 订单状态机

```plantuml
@startuml
state "已支付" as PAID
state "待退款 [新增]" as REFUND_PENDING #DCFCE7
state "已取消 [修改]" as CANCELLED #DBEAFE
[*] --> PAID
PAID -[#green]-> REFUND_PENDING : [新增] 申请退款
REFUND_PENDING -[#green]-> CANCELLED : [新增] 退款成功
CANCELLED --> [*]
state "本期删除（不参与新流转）" as REMOVED {
  state "取消中 [删除]" as CANCELLING #FEE2E2
}
@enduml
```
