# 订单取消支持退款确认

- 业务流程变化：有
- 判定依据：示例中取消完成由申请后立即完成改为等待退款结果确认，改变业务阶段顺序与完成时点；实际计划须以流程索引和代码核实。

## 背景

- User Story：作为购买者，我希望取消已支付订单后看到退款处理中，以便知道退款尚未完成。
- User Story：作为购买者，我希望退款成功后再看到订单已取消，以便确认交易已经结束。

## 业务流程总览

以下为示例当前流程。实际计划先参考相关 `.keel/call-chain/` 索引，再核对 OrderService.cancel、退款任务和测试，并在此简述已核实的证据路径。

```plantuml
@startuml
start
:购买者申请取消已支付订单;
if (允许取消?) then (是)
  :登记退款任务;
  :直接完成订单取消;
  :异步向退款渠道发起退款;
  :渠道处理退款结果;
else (否)
  :告知不能取消;
endif
stop
@enduml
```

## 状态机

绿色为新增，蓝色为修改，红色区域仅记录本期删除，不参与新流转。原 PAID → CANCELLING → CANCELLED 改为等待退款成功后取消。

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
