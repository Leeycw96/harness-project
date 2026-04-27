---
name: harness-backend-e2e
description: 基于 .harness/call-chain/ 中的业务流程文档生成端到端测试脚本。支持用户直接 /harness-backend-e2e 调用,也被 harness-qa 在第三层测试时引用。
user-invocable: true
---

# harness-backend-e2e:E2E 测试脚本生成

## 调用模式

本 skill 兼容两种上下文:

- **用户直接调用**(`/harness-backend-e2e`):走交互引导,通过 AskUserQuestion 选择 call-chain,产出脚本到 `.harness/e2e-tests/`
- **harness-qa 内部引用**:qa 在执行第三层测试时按本文档规则为每条 call-chain 产出 `qa-e2e-{slug}.sh`,**跳过所有交互**

具体上下文判定:`HARNESS_OUTPUT_DIR` 环境变量已设置 + `.harness/agent-registry` 存在 → 视为 qa 内部引用;否则视为用户直接调用。

## 输入

- `.harness/call-chain/{slug}.md`:业务流程调用链文档,定义入口方法、主流程、验证点
- `.claude/skills/harness-backend/assets/specs.md` 第 167 行起的"E2E 测试脚本"一节:脚本格式契约(本文档不重复)

## 输出

- `.harness/e2e-tests/qa-e2e-{slug}.sh`:每个 call-chain 一个 E2E 脚本,跨迭代持久
- `.harness/e2e-tests/qa-e2e-common.sh`:首次产出时一并创建公共函数库
- 必要时:`src/test/java/**/QA_E2E_{Slug}Verify.java`(异步验证工具类)

## 编写规则

### 1. 一对一约定

一个 call-chain 对应一个 E2E 脚本,文件名使用 call-chain 文件的 slug:`.harness/call-chain/order-create.md` → `.harness/e2e-tests/qa-e2e-order-create.sh`。

### 2. 自包含的完整生命周期

每个脚本独立可运行,内部完成:

```
启动服务 → 等待就绪 → [登录] → 业务操作 → 同步验证 → [异步验证] → 停止服务
```

### 3. 公共函数库

首次为项目编写 E2E 时一并创建 `qa-e2e-common.sh`,具体函数清单与签名见 specs.md。所有 `qa-e2e-{slug}.sh` 都 source 该公共库。

### 4. 异步验证优先级

`HTTP 轮询 > DB CLI 查询 > Java 测试类`。

只有当前两者都无法验证异步结果时,才编写 `QA_E2E_{Slug}Verify.java` 工具类:
- 路径:`src/test/java/**/QA_E2E_{Slug}Verify.java`
- 每个方法验证一个异步产物
- 在 sh 脚本中通过 `mvn test -Dtest="QA_E2E_{Slug}Verify#methodName"` 调用

### 5. 外部依赖处理

外部依赖(MQ、邮件服务等)不可用时:
- 用 `skip_if_unavailable` 包裹
- 输出 SKIP 而非 FAIL
- 保留完整逻辑,以便依赖就绪后启用

### 6. 脚本编写模式

- **简单接口**(如登录):启动 → curl → 验证 → 关闭
- **业务流程**(如创建订单):启动 → 登录 → 请求 → 同步验证 → 异步验证 → 关闭
- **跨功能链路**:在一个脚本中串联多步骤,每步带断言

## 失败诊断

E2E 脚本运行失败时,先诊断再判定:

1. **脚本与 call-chain 不一致**(call-chain 改了脚本没跟):自行更新脚本重跑
2. **两者一致但 call-chain 可能过期**(实现已变,call-chain 落后):由调用方(用户或 qa)按各自协议处理——qa 内部场景下需通知 harness-builder 更新 call-chain;用户直接调用场景下提示用户人工核对
3. **诊断后仍失败**:判定 FAIL,输出失败原因

## 用户直接调用流程

适用于 `/harness-backend-e2e` 入口。

1. 检查 `.harness/call-chain/` 是否存在且非空,否则提示用户先生成 call-chain 文档
2. **使用 AskUserQuestion 工具**列出该目录下所有 `.md` 文件,让用户选择
3. 读取选中的 call-chain,提取入口方法、主流程步骤、验证点
4. 检查 `.harness/e2e-tests/qa-e2e-common.sh` 是否存在;不存在则按上述规则生成
5. 按编写规则生成 `qa-e2e-{slug}.sh`
6. **使用 AskUserQuestion 工具**询问用户是否立即试运行
7. 试运行(可选)→ 报告 PASS/FAIL/SKIP 与原因

## 在 qa 内部被引用时

跳过所有用户交互,直接按 build-scope 中规划的 call-chain 列表为每条 call-chain 生成对应脚本。失败时按"失败诊断"流程处理;**通知 builder、写 qa-feedback** 等协作动作由 qa 自身负责,本 skill 不涉及。
