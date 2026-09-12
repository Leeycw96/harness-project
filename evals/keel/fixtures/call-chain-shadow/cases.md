# CallChain Shadow Cases

所有 case 均视为一次 full run 的全部 Builder diff。除 case 内明确说明外，基线不存在 `.keel/call-chain/` 文件。

## CASE-01

```diff
diff --git a/src/main/java/com/example/order/api/OrderView.java b/src/main/java/com/example/order/api/OrderView.java
@@
 public class OrderView {
     private String orderNo;
+    private String displayName;
     private BigDecimal amount;
 }
```

## CASE-02

```diff
diff --git a/src/main/java/com/example/pricing/PricingService.java b/src/main/java/com/example/pricing/PricingService.java
@@
 public Money calculate(Order order) {
-    return calculator.calculate(order);
+    Money subtotal = calculator.calculate(order);
+    return couponPolicy.apply(order.getCoupon(), subtotal);
 }
```

## CASE-03

```diff
diff --git a/src/main/java/com/example/order/OrderRepository.java b/src/main/java/com/example/order/OrderRepository.java
@@
-@Query("select o from Order o where o.userId = :userId")
+@Query("select o from Order o where o.userId = :userId order by o.createdAt desc")
 List<Order> findByUserId(Long userId);
```

## CASE-04

```diff
diff --git a/src/test/java/com/example/pricing/PricingServiceTest.java b/src/test/java/com/example/pricing/PricingServiceTest.java
@@
+@Test
+void appliesCouponAfterSubtotalCalculation() {
+    assertThat(service.calculate(orderWithCoupon())).isEqualTo(money("90.00"));
+}
```

## CASE-05

```diff
diff --git a/src/main/java/com/example/order/CreateOrderCommand.java b/src/main/java/com/example/order/CreateOrderCommand.java
@@
 public record CreateOrderCommand(
     @NotNull Long userId,
-    String remark
+    @Size(max = 200) String remark
 ) {}
```

## CASE-06

该系统原来没有商品备注管理入口。本轮增加一个单步同步 CRUD 接口。

```diff
diff --git a/src/main/java/com/example/catalog/RemarkController.java b/src/main/java/com/example/catalog/RemarkController.java
new file mode 100644
@@
+@RestController
+class RemarkController {
+    @PostMapping("/products/{id}/remark")
+    void update(@PathVariable Long id, @RequestBody RemarkRequest request) {
+        remarkService.update(id, request.remark());
+    }
+}
diff --git a/src/main/java/com/example/catalog/RemarkService.java b/src/main/java/com/example/catalog/RemarkService.java
new file mode 100644
@@
+@Transactional
+public void update(Long productId, String remark) {
+    repository.updateRemark(productId, remark);
+}
```

## CASE-07

系统已有 `POST /orders` 创建订单。本轮新增订单创建后的异步履约消费者。

```diff
diff --git a/src/main/java/com/example/order/OrderCreatedConsumer.java b/src/main/java/com/example/order/OrderCreatedConsumer.java
new file mode 100644
@@
+@Component
+class OrderCreatedConsumer {
+    @KafkaListener(topics = "order-created")
+    public void consume(OrderCreated event) {
+        fulfillmentService.reserveInventory(event.orderId());
+        orderRepository.markReserved(event.orderId());
+    }
+}
```

## CASE-08

系统已有支付单创建接口。本轮增加超时关闭调度，并新增 `PENDING -> EXPIRED` 状态变化。

```diff
diff --git a/src/main/java/com/example/payment/PaymentTimeoutJob.java b/src/main/java/com/example/payment/PaymentTimeoutJob.java
new file mode 100644
@@
+@Component
+class PaymentTimeoutJob {
+    @Scheduled(fixedDelayString = "${payment.timeout-scan-ms}")
+    @Transactional
+    public void expirePendingPayments() {
+        repository.findTimedOutPending().forEach(Payment::expire);
+    }
+}
diff --git a/src/main/java/com/example/payment/Payment.java b/src/main/java/com/example/payment/Payment.java
@@
+public void expire() {
+    requireStatus(PENDING);
+    status = EXPIRED;
+}
```

## CASE-09

系统已有向外部物流商提交发货的 Service。本轮新增物流回调入口，并由回调推进终态。

```diff
diff --git a/src/main/java/com/example/shipping/CarrierCallbackController.java b/src/main/java/com/example/shipping/CarrierCallbackController.java
new file mode 100644
@@
+@RestController
+class CarrierCallbackController {
+    @PostMapping("/callbacks/carrier/delivered")
+    void delivered(@RequestBody DeliveredCallback callback) {
+        shippingService.markDelivered(callback.shipmentNo());
+    }
+}
diff --git a/src/main/java/com/example/shipping/ShippingService.java b/src/main/java/com/example/shipping/ShippingService.java
@@
+@Transactional
+public void markDelivered(String shipmentNo) {
+    repository.get(shipmentNo).transition(IN_TRANSIT, DELIVERED);
+}
```

## CASE-10

基线订单流程由下单接口写入 `CREATED`，支付回调写入 `PAID`。本轮在两者之间增加风控异步阶段。

```diff
diff --git a/src/main/java/com/example/order/OrderService.java b/src/main/java/com/example/order/OrderService.java
@@
 public void confirmPayment(Long orderId) {
-    repository.transition(orderId, CREATED, PAID);
+    repository.transition(orderId, CREATED, RISK_PENDING);
+    riskPublisher.publish(new RiskCheckRequested(orderId));
 }
diff --git a/src/main/java/com/example/order/RiskResultConsumer.java b/src/main/java/com/example/order/RiskResultConsumer.java
new file mode 100644
@@
+@RabbitListener(queues = "risk-result")
+public void consume(RiskResult result) {
+    OrderStatus target = result.approved() ? PAID : RISK_REJECTED;
+    repository.transition(result.orderId(), RISK_PENDING, target);
+}
```
