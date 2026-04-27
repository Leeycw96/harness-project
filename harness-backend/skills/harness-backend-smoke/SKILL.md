---
name: harness-backend-smoke
description: 基于 .harness/call-chain/ 中的业务流程文档生成冒烟测试脚本,引导用户半自动验证业务流程。脚本由 harness-qa 在第三层产出,由用户通过 /harness-backend-smoke 运行。
user-invocable: true
---

# harness-backend-smoke:冒烟测试脚本

## 定位

把一条 call-chain 描述的业务流程脚本化为半自动冒烟测试:HTTP 步骤由脚本自动 `curl` + 接口/数据双层断言;非 HTTP 触发(Scheduler / MQ / RPC)由脚本暂停并引导用户手动触发,完成后继续执行后置数据断言。**全程真实链路,不写 Mock 代码、不新增任何 Java 测试类**。

## 输入

- `.harness/call-chain/{slug}.md`:业务流程调用链文档,定义入口方法、主流程、验证点
- `.claude/skills/harness-backend/assets/specs.md` 的"冒烟测试脚本"一节:脚本格式契约与公共函数签名(本文档不重复)

待处理的 call-chain 列表由调用方决定:若调用方已传入列表,直接使用;否则使用 AskUserQuestion 让用户从 `.harness/call-chain/` 中选择。

## 输出

- `.harness/smoke-tests/smoke-{slug}.sh`:每个 call-chain 一个冒烟脚本,跨迭代持久
- `.harness/smoke-tests/smoke-common.sh`:首次产出时一并创建公共函数库

## 编写规则

### 1. 一对一约定

一个 call-chain 对应一个冒烟脚本,文件名使用 call-chain 文件的 slug:`.harness/call-chain/order-create.md` → `.harness/smoke-tests/smoke-order-create.sh`。

### 2. 自包含的完整生命周期

每个脚本独立可运行,内部完成:

```
启动服务 → 等待就绪 → [登录]
       → 业务步骤 → 接口断言 → 数据状态断言
       → [人工触发等待 → 后置数据断言]
       → 停止服务
```

服务的启动与停止由脚本负责,确保脚本结束后无遗留进程。

### 3. 公共函数库

首次为项目编写冒烟脚本时一并创建 `smoke-common.sh`,具体函数清单与签名见 specs.md。所有 `smoke-{slug}.sh` 都 source 该公共库。

### 4. 验证维度

每个步骤至少做两层断言:

- **接口断言**:HTTP 状态码 + 响应字段(成功标识、关键返回值)
- **数据状态断言**:对受影响的表执行 `select`,校验记录的增 / 删 / 改

仅断言 HTTP 200 不算冒烟测试。**步骤返回值(orderNo、userId、token 等)必须捕获**,作为后续步骤 DB 查询的 `where` 条件或下一步接口的入参,实现步骤间数据流。

### 5. 异步与人工触发

按可达性分两条路径:

- **自动可达**(异步副作用通过 HTTP 轮询或 DB 轮询能直接观测):脚本内置 `wait_until` 类轮询,设置最大等待时间;超时则按断言失败处理
- **自动不可达**(由 Scheduler / MQ 消费者 / RPC Provider 触发,sh 无法直接发起):走"人工触发步骤"

### 6. 人工触发步骤

每个人工步骤由三段组成:

1. **指令**:明确告诉用户要触发什么、怎么触发——给出 Scheduler 名 / MQ topic / RPC 方法,以及可执行的触发方式提示(管理后台路径、命令示例,从 call-chain 中尽量摘取;无法摘取时留 TODO)
2. **等待**:通过公共函数 `wait_user_action <prompt> <hint>` 阻塞,接受三种用户输入——`c` 继续 / `s` 跳过该步及其依赖项(整条标记 SKIP)/ `a` 中止脚本
3. **后置数据断言**:用户输入 `c` 后,脚本立刻执行 DB 查询,验证人工触发的副作用是否落库

非交互环境下(`HARNESS_NONINTERACTIVE=1`),`wait_user_action` 自动 SKIP 该步骤并记录原因,后续依赖项一并 SKIP。

### 7. 依赖处理

- **基础设施暂时不可用**(MQ broker、SMTP 等):用 `skip_if_unavailable` 包裹,输出 SKIP 而非 FAIL,保留完整逻辑以便依赖就绪后启用
- **业务流程由非 HTTP 机制触发**:走"人工触发步骤",不写 Mock Controller / 测试触发端点

### 8. 脚本编写模式

- **简单接口**(如登录):启动 → curl → 接口断言 → DB 断言 → 关闭
- **业务流程**(如创建订单):启动 → 登录 → 请求 → 接口断言 → DB 断言 → [异步轮询 / 人工触发 → 后置 DB 断言] → 关闭
- **跨功能链路**:在一个脚本中串联多步骤,每步遵循"验证维度"两层;步骤间通过捕获接口返回值串联

## 执行流程

本 skill 面向两类调用方,职责不同:

### qa 引用(只产出脚本,不运行)

适用于 harness-qa 第三层。

1. 检查 `.harness/call-chain/` 是否存在且非空,否则要求 builder 先生成
2. 取 build-scope 中规划的 call-chain 列表,逐条读取入口方法、主流程、验证点
3. 检查 `.harness/smoke-tests/smoke-common.sh` 是否存在;不存在则按上述规则生成
4. 按编写规则生成每条 `smoke-{slug}.sh`
5. 完成交付,不试运行 — 失败诊断不在 qa 职责内

### 用户运行(`/harness-backend-smoke`)

1. 检查 `.harness/call-chain/` 与 `.harness/smoke-tests/` 状态:
   - call-chain 缺失 → 提示用户先生成
   - smoke 脚本缺失 → 按上述规则补生成
2. 使用 AskUserQuestion 让用户选择要跑的 call-chain
3. 运行对应 `smoke-{slug}.sh`,过程中遇到人工触发步骤,按"人工触发步骤"约定与用户交互
4. 报告 PASS / FAIL / SKIP 与原因

## 失败诊断

仅在用户运行场景下出现。脚本失败时,先诊断再判定:

1. **脚本与 call-chain 不一致**(call-chain 改了脚本没跟):自行更新脚本重跑
2. **两者一致但 call-chain 可能过期**(实现已变,call-chain 落后):提示用户人工核对,确认后由调用方按各自协议处理(如通知 builder 更新 call-chain)
3. **诊断后仍失败**:判定 FAIL,输出失败原因
