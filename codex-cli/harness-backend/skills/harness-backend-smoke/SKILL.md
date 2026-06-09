---
name: harness-backend-smoke
description: 读 .harness/call-chain/{slug}.md,逐入口生成 URL + 请求 JSON 报文给用户用 Postman 测试。非 HTTP 入口(Scheduler / MQ / RPC)可选 spawn subagent 加临时 /_smoke/trigger/{name} HTTP 入口。skill 只生成与引导,不执行任何业务请求。
user-invocable: true
---

# harness-backend-smoke:Postman 冒烟请求生成

## 定位

本 skill 不写 shell 脚本、不发任何业务请求。**它把一条 call-chain 解析成"按顺序、可直接复制到 Postman 的请求清单"**——URL、method、headers、body、期望响应都明示给用户;非 HTTP 入口(Scheduler / MQ / RPC)经用户同意后用 general-purpose subagent 加临时 `/_smoke/trigger/{name}` HTTP 入口,让用户在 Postman 也能戳到。

**逐步生成、逐步等用户反馈**:

- skill 一次只生成一条请求 → 落盘 → 展示给用户
- 用户在自己的 Postman 跑一次 → 回报「通过 / 参数有问题 / 是代码 bug」
- 通过 → skill 进入下一条
- 参数有问题 → skill 根据错误信息调整 URL/body,再让用户重测
- 代码 bug → skill 落盘失败记录 + 提示用户去 `/harness-plan` 或 `/harness-backend` 修复,本 skill **不**启动 builder/qa pane

> 历史包袱:`.harness/smoke-tests/{slug}/smoke.sh` 是旧 v2 时代由 qa 产出的 shell 冒烟脚本。新流程下 qa 不再产脚本,本 skill 也不再运行任何脚本。**已存在的 smoke-tests/ 目录保留不动,人工决定何时清理**。

## 输入

- `.harness/call-chain/{slug}.md`:业务流程入口清单(XML,只读)。schema 见 `harness-backend/skills/harness-backend/assets/call-chain-example.md`
- 项目源码:用于读 `@RequestMapping`、`@RequestBody` 的 DTO 字段

## 输出

```
.harness/smoke-requests/
  {slug}/
    00-overview.md              # 入口总览 + Postman 使用提示
    01-{verb}-{noun}.md         # 每条入口一份(序号 = call-chain 出现顺序)
    02-{verb}-{noun}.md
    ...
    temp-controllers.md         # (条件产出) 本次添加的临时 Controller 文件路径清单
    feedback.md                 # 用户对每条入口的回报记录(通过 / 调整 N 轮 / 代码 bug)
  failures/
    {slug}-{timestamp}.md       # (条件产出) 用户判定"代码 bug"时落盘的失败记录
```

> `.harness/smoke-requests/` 是新增长期工件目录,**不**进 `.gitignore`——请求清单本身是有价值的资产,可入仓评审。`failures/` 也建议入仓,作为修复任务的输入。

## 执行 SOP

### 1. 前置检查

| 检查项 | 缺失时的处理 |
|--------|------------|
| `.harness/call-chain/` 存在且至少有 1 个 `*.md` | 提示用户:「无可用 call-chain,请先让 harness-builder 在迭代中生成」,中止 |
| 选定 slug 的 call-chain 文件存在 | 用户选了不存在的 slug 时回到第 2 步重选 |
| 项目源码可读(任意 `*.java` 可 Read) | 不可达时直接报错,无法继续生成 |

### 2. 选择 call-chain

让用户从 `.harness/call-chain/*.md` 列表中**单选**一条 slug。多 slug 没有合并价值——每条流程独立成单元,跑完再选下一个更清晰。

### 3. 解析 call-chain,呈现总览

Read 选定的 call-chain 文件。按 XML 中 `<step>` 出现顺序整理一张总览表(注意:`<branch>/<path>` 内的 step 也要展开,加列标注分支):

```
[{slug}] 共 N 个入口

| # | step id            | entry-type | 入口类                                  | 所在分支       |
|---|--------------------|------------|----------------------------------------|----------------|
| 1 | submit             | http       | com.example.user.UserController#register | 主流程         |
| 2 | scheduler-step     | scheduler  | com.example.order.OrderExecutor#process  | 主流程         |
| 3 | action-step        | http       | com.example.admin.OrderFacade#approve   | 主流程         |
| 4 | exec-step          | scheduler  | com.example.order.PayExecutor#exec      | approved 分支  |
| 5 | exec-callback      | mq         | com.example.order.PayCallbackListener   | approved 分支  |
| 6 | reject-handler     | scheduler  | com.example.order.RejectHandler         | rejected 分支  |

非 HTTP 入口共 X 条(scheduler:Y, mq:Z, rpc:W)
```

总览**只读不写**,目的是让用户在生成请求前对全景有数。同时为下一步"临时 Controller 决策"做铺垫。

### 4. 非 HTTP 入口的临时 Controller 决策(条件触发)

**触发条件**:总览中存在 `entry-type` 为 `scheduler` / `mq` / `rpc` 的 step。

把非 HTTP 入口列出,让用户三选一:

> 该 call-chain 有 N 个非 HTTP 入口(列出 entry-type + 类名),要不要让 skill 用 subagent 加临时 `/_smoke/trigger/{name}` HTTP 入口?
>
> - **全部加**(推荐):体验从"去后台 / 命令行戳"统一成"Postman 一键触发";冒烟结束时由本 skill 引导清理(撤销 / 暂存 / 提交三选一)
> - **挑选加**:进入子流程,对每个非 HTTP 入口单独问"加 / 不加"
> - **全部不加**:在请求清单里给出手动触发指引(命令示例、后台路径,从 call-chain `<description>` 中尽量提取;提取不到则留 TODO 标注)

#### 4.1 spawn subagent 加临时入口

对每个被选"加"的入口,用 `Agent` 工具(`subagent_type: general-purpose`)起一个 subagent,任务边界写死:

```
在 {src 路径} 下添加一个 @RestController 内部接口 POST /_smoke/trigger/{name},
直接调用 {Scheduler/Listener handler 全限定名}.{方法名}()。

要求:
- 路径必须以 /_smoke/ 开头
- 类/方法上加注释 // smoke-only,冒烟后清理
- 不写测试,不改其他文件,不动配置
- 完成后输出新增/修改的文件路径列表(完整绝对路径)
```

subagent 返回路径列表后,本 skill 把这些路径写入 `.harness/smoke-requests/{slug}/temp-controllers.md`,格式:

```markdown
# 本次冒烟添加的临时 Controller 文件

冒烟结束时由 skill 引导清理(撤销 / 暂存 / 提交三选一)。

- src/main/java/com/example/smoke/SmokeTriggerController.java(新增)
- src/main/java/com/example/order/OrderCancelScheduler.java(改:加 public 方法)
```

子 step 的请求清单(第 5 步)按 `POST /_smoke/trigger/{name}` 生成,而非原生 entry-type。

#### 4.2 选"不加"或"挑选"中跳过的入口

在该 step 的请求清单文件里写"手动触发指引"段(没有 URL/body),内容尽量从 call-chain `<description>` 中提炼:

```markdown
## 触发方式(手动)

本入口是 MQ Listener,Postman 触发不到。请用以下方式之一触发:

- 命令行(推荐):rabbitmqadmin publish exchange=biz routing_key=order.paid payload='{"orderNo":"..."}'
- 管理后台:RabbitMQ Management UI → exchange:biz → Publish → routing_key=order.paid

触发后请人工核验数据状态。
```

call-chain 没写清楚的,留:

```markdown
> TODO: call-chain 未提供具体触发方式,需要补充。可以问 builder 或在管理后台找。
```

### 5. 逐步生成请求(核心循环)

**这是整个 skill 的核心**。**一次只生成一条**,落盘 → 展示 → 等用户反馈 → 决定下一步。不要批量生成,不要先把所有请求一起落盘——逐步交互是设计的灵魂,批量生成等于把回报机制架空。

#### 5.1 准备工作(生成第一条前一次性做)

创建目录 `.harness/smoke-requests/{slug}/` 并写入 `00-overview.md`:

```markdown
# {slug} 冒烟请求清单

由 harness-backend-smoke 从 .harness/call-chain/{slug}.md 生成。
用户用 Postman 逐条测试,每条等用户反馈后生成下一条。

## 入口总览

(第 3 步那张表原样复制到这里)

## Postman 使用提示

- 推荐建立一个 Environment,变量包括:
  - `baseUrl`(如 http://localhost:8080)
  - `TOKEN`(登录后填入,后续请求用 `Bearer {{TOKEN}}`)
  - 本次冒烟产生的关键字段(如 `ORDER_NO`、`USER_ID`)
- 每条请求文件中的 `{{XXX}}` 占位符对应 Environment 变量
- 临时 Controller 的请求路径以 `/_smoke/trigger/` 开头
```

#### 5.2 单条生成 SOP

对当前 step:

**a. 读源码,定位入口方法**

按 entry-type 分:

- **http**:从入口类 `@RequestMapping` / `@GetMapping` / `@PostMapping` 提取 method + path;入口方法的 `@RequestBody DTO` 类去 Read DTO 源码提取字段
- **scheduler / mq / rpc(已加临时入口)**:method = POST,path = `/_smoke/trigger/{name}`;body 视 handler 是否需要参数而定(无参用 `{}`)
- **scheduler / mq / rpc(未加临时入口)**:跳过 5.2.b/c,直接落盘"手动触发指引"段(第 4.2 节模板)

**b. 构造示例 JSON body**

按 DTO 字段类型给合理示例值,不要写 `"string"` 这种占位:

| 类型 | 示例值 |
|------|--------|
| `String username` | `"user_smoke_001"` |
| `String email` | `"smoke@example.com"` |
| `String password` | `"P@ssw0rd"` |
| `Long userId` / `Integer qty` | `1` |
| `BigDecimal amount` | `100.00` |
| `LocalDate` / `LocalDateTime` | `"2026-05-18"` / `"2026-05-18T10:00:00"` |
| `Boolean` | `true` |
| `List<X>` | 1 个示例元素 |
| 自定义对象 | 递归按上表 |

字段有 `@NotNull` / `@Size` / `@Pattern` 约束的,按约束给值;有 `enum` 的,从枚举中选第一个。

**关键字段需要从前置 step 传递**(典型如 `orderNo`、`userId`、`token`),用 `{{XXX}}` 占位符,并在请求文件中注明"来源:step XX 的响应字段 yy"。

**c. 落盘请求文件**

文件名:`NN-{verb}-{noun}.md`,`verb` 为 HTTP method 小写或动作动词(如 `post-register` / `trigger-cancel`),`noun` 为业务实体(如 `user` / `order`)。模板:

```markdown
# [step-id] {简短描述}

call-chain step: `{step-id}` (entry-type: {http/scheduler/mq/rpc})
入口类: `{全限定类名}#{方法名}`
所在分支: {主流程 / approved / rejected / ...}

## Request

```http
POST {{baseUrl}}/api/users
Content-Type: application/json
Authorization: Bearer {{TOKEN}}
```

### Body

```json
{
  "username": "user_smoke_001",
  "password": "P@ssw0rd",
  "email": "smoke@example.com"
}
```

### 字段来源

| 字段 | 来源 |
|------|------|
| `{{TOKEN}}` | 由 step 01-login 的响应字段 `data.token` 填入 Environment |
| `username` | 自由填写(示例 `user_smoke_001`) |

## 期望响应

- HTTP 状态码:201
- Body 含字段:`data.userId`(非空 Long)
- 写入 Environment 变量供后续 step 用:
  - `USER_ID` ← `data.userId`

## 数据状态人工核验

冒烟不连 DB,请用户在 Postman 跑通后自行查库确认:

```sql
SELECT id, username, status FROM user WHERE username = 'user_smoke_001';
-- 期望:status=ACTIVE,id 等于本次响应返回的 userId
```
```

非 HTTP 未加临时入口的 step 文件只含"call-chain 元信息 + 手动触发指引 + 数据状态人工核验"三段,无 Request/Body。

**d. 展示给用户 + 等反馈**

在对话里把刚落盘的请求文件**关键内容**摘要给用户:

```
[N/Total] {step-id} 请求清单已生成:.harness/smoke-requests/{slug}/NN-xxx.md

  Method: POST
  URL:    {{baseUrl}}/api/users
  Headers: Content-Type, Authorization Bearer {{TOKEN}}
  Body:
    {
      "username": "user_smoke_001",
      "password": "P@ssw0rd",
      "email": "smoke@example.com"
    }
  期望: 201, 含 data.userId

请在 Postman 跑一次后告诉我结果。
```

随后让用户三选一:

- **「通过,下一条」**:在 `feedback.md` 追加一行 `[step-id] PASS`,进入下一 step
- **「URL 或参数有问题,请调整」**:进入 5.3 调整子流程
- **「代码 bug,跳过本条继续」**:进入 5.4 代码 bug 处理子流程

#### 5.3 URL/JSON 调整子流程

让用户贴 Postman 的实际响应(状态码 + body)和报错信息。skill 基于错误信息复核:

| 常见错误 | 复核动作 |
|----------|----------|
| 400 "字段不能为空" | 复核 DTO 字段是否漏了 `@NotNull` 必填项,补字段重写 |
| 400 "类型不匹配" | 复核字段类型示例是否对(LocalDate vs Instant vs Long 时间戳) |
| 404 | 复核 path 是否拼对(class 上的 `@RequestMapping` + method 上的 path 是否漏拼) |
| 401 / 403 | 复核 Authorization header 是否带、Token 是否过期 |
| 415 | 复核 Content-Type 是否对(`application/json` vs `multipart/form-data`) |
| 其他 | 把 Postman 响应贴给 skill,skill 给出最可能的调整方向 |

调整后**覆盖**原 step 文件(同路径同名),在文件末尾追加一段:

```markdown
## 调整历史

- **2026-05-18 10:23**(第 1 轮):用户反馈 400,字段 `email` 缺失 `@Email` 校验通过的值
  - 调整:`email` 从 `"smoke"` 改为 `"smoke@example.com"`
```

重新摘要给用户测,再问一次反馈。直到「通过,下一条」为止。

调整轮次没有硬上限,但 ≥ 3 轮时主动询问用户:「调整 3 轮仍未通过,是否怀疑代码 bug?」给用户「再调一轮 / 当代码 bug 处理 / 跳过本条」三选一。

#### 5.4 代码 bug 处理子流程

用户反馈"是代码 bug"时:

1. 让用户用一两句话描述 bug 现象(如"返回 500,日志说 NullPointer at OrderService:123")
2. skill 落盘失败记录到 `.harness/smoke-requests/failures/{slug}-$(date +%Y%m%d-%H%M%S).md`:

   ```markdown
   # {slug} / {step-id} 代码 bug 记录

   - 时间:2026-05-18 10:30
   - call-chain:`.harness/call-chain/{slug}.md`
   - 入口类:`com.example.order.OrderController#submit`
   - 请求清单:`.harness/smoke-requests/{slug}/NN-xxx.md`
   - 用户描述:返回 500,日志 NullPointer at OrderService:123
   - 调整轮次(若来自 5.3):2 轮调整后仍是同一错误
   ```

3. 在 `feedback.md` 追加 `[step-id] CODE-BUG → failures/{slug}-XXX.md`
4. **不**启动 builder/qa pane(本 skill 是轻量 skill,修复不在职责范围)。提示用户:

   > 已落盘失败记录:`{path}`
   >
   > 这个 bug 该怎么处理?
   > - 影响小、清楚怎么改 → 启动 `/harness-backend` 让 builder + qa 直接修
   > - 影响较大、改动跨多个文件 → 先走 `/harness-plan` 把改动范围对齐再 `/harness-backend`
   >
   > 本 skill 跳过该 step,询问是否继续后续 step。
5. 向用户确认:「继续后续 step / 中止本次冒烟」

### 6. 全部跑完后的汇总

最后一条 step 反馈完毕后:

#### 6.1 写汇总报告

落盘 `.harness/smoke-requests/{slug}/feedback.md` 已经在 5 步循环中累积,此时 Read 它生成汇总表呈给用户:

```
[{slug}] 冒烟完成

| # | step             | 结果         | 备注                                |
|---|------------------|--------------|------------------------------------|
| 1 | submit           | PASS         | -                                  |
| 2 | scheduler-step   | PASS (临时入口) | 2 轮调整后通过                      |
| 3 | action-step      | CODE-BUG     | failures/xxx-20260518-103045.md     |
| 4 | exec-step        | SKIPPED      | 因 step 3 是代码 bug,流程中断       |

总计:PASS=2,CODE-BUG=1,SKIPPED=1
```

#### 6.2 临时 Controller 清理(条件触发)

**触发条件**:`.harness/smoke-requests/{slug}/temp-controllers.md` 存在且非空。

读取该文件,把所有临时 Controller 文件路径聚合,让用户三选一:

> 本次冒烟添加了 N 个临时 Controller 文件(列出路径),如何处理?
>
> - **撤销改动(默认)**:对每个文件:
>   - 已被 git tracked(`git ls-files --error-unmatch {file}` 成功) → `git checkout HEAD -- {file}` 还原
>   - 未 tracked(`git ls-files --error-unmatch {file}` 失败) → **不自动 `rm`**,列出来提示用户手动删除(避免误删用户其他工作)
> - **暂不处理**:文件保留在工作区,由用户自行决定后续(stash / 留到下次冒烟 / 手动整理)
> - **直接提交**:`git add {files} && git commit`(commit message 由用户提供或默认 `chore: smoke trigger endpoints for {slug}`)。**默认不 push**——push 是显著动作,需要用户再次确认目标 branch

执行完毕后简短回播清理结果(还原了哪些 / 保留了哪些 / 提交到了哪个 commit),作为本次冒烟的尾声。

#### 6.3 收尾提示

如果汇总中有 CODE-BUG:

> 本次冒烟发现 N 个代码 bug,失败记录在 `.harness/smoke-requests/failures/` 下。
> 建议:
> - 影响小 → `/harness-backend` 直接修
> - 影响大 / 跨文件 → `/harness-plan` 对齐范围 → `/harness-backend` 修
> 即使本会话中断,failures/ 下的记录可独立用于后续修复任务的输入。

如果全 PASS:

> 本次冒烟全部通过。请求清单保留在 `.harness/smoke-requests/{slug}/` 下,后续回归可直接复用(导入 Postman / 重新生成 Environment)。

## 边界与禁忌

- **不发任何业务请求**——本 skill 只读源码、生成请求清单,任何"我帮你测试一下"都越界
- **不写 shell 冒烟脚本**——`.harness/smoke-tests/` 是旧 v2 的产物,保留不动但不再产新内容
- **不启动 builder/qa pane**——修复职责完全外包给用户决策的 `/harness-backend` 或 `/harness-plan`
- **不批量生成请求**——逐步生成 + 等反馈是核心交互模式,违反等于把"用户校验"这一环架空
- **不修改 call-chain**——call-chain 是 builder/qa 产出的,本 skill 只读
- **不臆造字段**——示例值要基于 DTO 类型 + 约束注解给,猜不出来的字段(如业务特有的代码值)留 `"TODO: 业务侧填入"`,不要硬填
- **不静默写文件**——临时 Controller 清理、调整后的请求覆盖,关键节点必须经用户同意
