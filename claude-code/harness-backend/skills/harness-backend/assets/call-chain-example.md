# Call-chain 示例: 业务流程入口索引

`call-chain` 只记录跨迭代有价值的业务流程入口索引。它不是接口清单、不是方法调用链、不是 feature slug 历史。

## 文件粒度

一个文件对应一个**业务流程**,不是业务域、接口或 feature。

业务流程定义:

- 围绕一个明确业务目标从开始推进到终态。
- 由一个或多个外部可触发入口驱动。
- 文件名使用 `<业务域>-<业务流程>.md`,例如 `order-purchase.md`、`order-refund.md`、`settlement-payout.md`。

## 创建或更新条件

默认不创建。只有本轮变更出现业务流程可见变化,才允许创建或更新。

业务流程可见变化包括:

- 外部可触发入口新增、删除、重命名或语义变化。
- MQ、Scheduler、外部 callback、延迟任务等异步推进点新增、删除或语义变化。
- 已有 call-chain 对应业务对象的生命周期状态或状态流转变化。

创建新 call-chain 必须满足以下任一条件:

- 多入口参与同一业务目标,例如 HTTP 下单 + MQ 支付回调。
- 存在异步推进边界,例如 MQ、Scheduler、外部 callback、延迟任务继续推进业务。
- 存在多阶段状态流转,例如 `CREATED -> PAID -> SHIPPED -> DONE`,且不是一次同步调用内全部完成。

更新已有 call-chain 的条件:

- 本轮变化属于现有 call-chain 描述的业务流程;并且
- 入口目录、异步推进步骤、业务流程步骤或多阶段状态流转需要同步修正。

## 不创建的情况

- 简单查询、列表、详情、统计、导出。
- 单步同步 CRUD。
- 只有一个 Controller/RPC 入口且同步完成整个业务目标。
- Service 内部同步调用其他 RPC。
- DAO / Repository / DTO / Converter / 参数校验变化。

不确定是否达到创建标准时,默认不创建。

## 文件格式

```markdown
# 用户购买流程

## 业务说明
用户提交订单后,系统创建订单,后续由支付回调和物流消息推进状态。

## 入口目录
| 步骤 | 触发类型 | 入口类 | 入口方法 | 说明 |
|------|----------|--------|----------|------|
| 下单 | HTTP | OrderController | createOrder | 创建订单 |
| 支付回调 | MQ | PaymentCallbackListener | onMessage | 支付成功后推进订单状态 |
| 物流回调 | MQ | ExpressMessageListener | onMessage | 更新物流状态 |

## 流程
1. 用户通过 `OrderController#createOrder` 创建订单。
2. 支付成功后,`PaymentCallbackListener#onMessage` 接收支付回调并更新订单为已支付。
3. 物流系统发送消息后,`ExpressMessageListener#onMessage` 更新配送状态。

## 不记录
- Service 内部同步调用
- DAO / Repository 调用链
- DTO 转换
- 单纯查询接口
- 单步同步 CRUD
```
