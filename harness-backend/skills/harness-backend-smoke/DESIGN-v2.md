# harness-backend-smoke v2 优化设计

> 状态:草案,待用户审阅。来源:真实业务场景使用反馈(2026-05)。
> 本文件不写实现细节,只描述"改什么、改到什么形态、为什么"。实施时按"实施顺序"小节逐项落到 SKILL.md / harness-qa-AGENTS.md / smoke-common.sh。

## 背景:用户的 4 条反馈

1. **启停由用户**:agent 直接 fork-exec 让用户失去随时介入 Debug 的能力
2. **用例视角设计脚本**:当前脚本只关心"调谁、断言什么",缺"由谁(actor)调"、"需预置什么"、"非 HTTP 触发怎么办"——希望开跑前有一份准备清单
3. **单步执行**:碰问题时希望 step 维度暂停,而不是整个中断重来
4. **复利经验**:每次冒烟踩的坑应能沉淀,下次自动加载、用户确认后才生效

## 总体设计原则

- **结构化优先**:跨步骤、跨次、跨 agent 的传递一律走文件(JSON/XML/markdown 文档),不依赖 stdout 截取
- **用户为主、agent 为辅**:agent 提议、用户决策——所有"沉淀"动作都需 `AskUserQuestion` 确认
- **职责不漂移**:qa 仍负责脚本编写,smoke skill 仍负责运行/引导/汇总。新增工件归属要明确

---

## 方案 A:启停权交还给用户

### 现状
- `SKILL.md:74-76` 由 skill 调 `bash .harness/smoke-tests/{slug}/smoke.sh`
- 用户无法 Ctrl+C、加 `bash -x`、手动改 env 重跑;失败时 stdout 在 skill 上下文里,易被截断/噪音污染

### 改法

**A1 — orchestrator 落盘结构化结果**(改 smoke-common.sh + 模板):
- 新增公共函数 `result_init` / `result_record_pass {step}` / `result_record_fail {step} {reason}` / `result_record_skip {step} {reason}` / `result_finalize`
- 在 `{slug}/.run/result.json` 写入:
  ```json
  {
    "slug": "order-create",
    "started_at": "2026-05-15T10:00:00+08:00",
    "ended_at": "2026-05-15T10:03:21+08:00",
    "exit_code": 1,
    "summary": {"pass": 4, "fail": 1, "skip": 0},
    "steps": [
      {"file": "01-login.sh", "status": "PASS"},
      {"file": "02-create-order.sh", "status": "FAIL", "reason": "expected status=PENDING got null"}
    ]
  }
  ```
- orchestrator 退出前调用 `result_finalize`,即使中途 trap 退出也要写出快照(部分结果)

**A2 — SKILL.md 第 4 步改成"引导用户在自己终端跑"**:
- skill 不再 `bash smoke.sh`,而是打印:
  ```
  请在你自己的终端执行(支持 Ctrl+C / bash -x / 改 env):
    cd <repo-root>
    bash .harness/smoke-tests/{slug}/smoke.sh

  跑完后回到本会话输入「跑完了」,我从 .run/result.json 读结果。
  ```
- 阻塞等用户回报后,**只读 result.json**,不读 stdout;读不到 result.json 就提示用户"orchestrator 异常退出,请贴最后几行 stdout 给我"

**A3 — 多 slug 顺序运行**:不再由 skill 自动接续。每跑完一个 slug,引导用户决定下一个的启动时机(回到第 6 步 checkpoint 即可)

### 收益
- 用户随时介入,Debug 体验跃迁
- skill 永远拿结构化结果,失败诊断输入更稳定

### 代价
- 每次切换"贴命令 ↔ 回报"的人机切换成本;但单次冒烟也就几次,可接受
- orchestrator 模板要改(qa 需更新 harness-qa-AGENTS.md 的脚本编写规则)

---

## 方案 B:用例视角的脚本设计 + 准备清单

### 现状
- qa 写脚本时只规划"调哪个接口、断言什么";缺乏 actor / 数据 / 触发方式的统一出口
- Scheduler / MQ / RPC 当前只能 `wait_user_action` 引导用户去后台手动触发,体验最差
- smoke skill 开跑前没有"准备清单确认"环节,经常跑到一半才发现资源未就绪

### 改法分两侧

#### B1 — qa 侧(改 `harness-qa-AGENTS.md:288` 起的"冒烟脚本编写规则")

每个 slug 必须额外产出 `00-prepare.md`(命名前缀 `00-` 是为了与 step 文件并列、视觉上排在最前;文件名固定):

```markdown
---
slug: order-create
generated: 2026-05-15
generator: harness-qa
---

## Actor 表(谁调谁)

| step 文件          | 调用接口                    | 角色      | 凭据获取                                |
|--------------------|----------------------------|-----------|----------------------------------------|
| 01-login.sh        | POST /auth/login           | 普通用户  | 用例账号 user_smoke_001 / pwd 见 vault |
| 02-create-order.sh | POST /orders               | 普通用户  | 复用 01 的 token                       |
| 03-approve.sh      | POST /admin/orders/approve | 管理员    | 用例账号 admin_smoke_001 / pwd 见 vault|

## 预置数据

| 库表            | 关键字段             | 期望状态                                |
|-----------------|---------------------|----------------------------------------|
| product         | sku=SKU001          | status=ON_SHELF, stock>=10             |
| user            | username=user_smoke_001 | status=ACTIVE                       |

## 外部依赖

- Redis(localhost:6379)需可达
- 短信网关 mock 服务需在 8090 端口启动

## 非 HTTP 触发点

| 触发点              | 类型      | 当前触发方式                            |
|--------------------|-----------|----------------------------------------|
| OrderCancelScheduler | 定时任务  | 临时入口 POST /_smoke/trigger/order-cancel |
| order.paid          | MQ topic  | 后台手动:rabbitmqadmin publish ...     |
```

**生成 prepare.md 之前**,qa 必须 `AskUserQuestion`:

> 该流程有 N 个非 HTTP 触发点(列出名称),要不要让 builder 临时加 `/_smoke/trigger/{name}` 内部入口?加了之后:① 体验从"去后台戳"变成"curl 直接触发";② prepare.md 里会标注"临时入口,冒烟后清理"

**用户选"加"** → qa **不拉 tmux 里的 builder pane**(那是重型协作),而是用 Agent 工具临时唤起一个 subagent(general-purpose 即可),给它的小任务:

> 在 `{src 路径}` 下添加一个 `@RestController` 内部接口 `POST /_smoke/trigger/{name}`,直接调用 `{Scheduler/Listener handler 全限定名}` 的对应方法。要求:
> - 路径必须以 `/_smoke/` 开头
> - 类/方法上加注释 `// smoke-only, remove before merge`
> - 不写测试,不改其他文件
> - 完成后输出新增的文件路径列表

subagent 完成后返回,qa 把"临时入口"信息写进 prepare.md 的对应栏(包括新增文件的绝对路径列表,**清理时要用**)。

**用户选"不加"** → qa 仍按当前"`wait_user_action` 引导用户后台触发"的方式写,但 prepare.md 必须把触发指令写得足够具体(命令示例、后台路径)。

#### B3 — 冒烟结束的临时入口清理(改 SKILL.md 第 7 步汇总后)

如果本 slug 的 prepare.md 标注了临时入口文件,第 7 步汇总报告之后追加一次 `AskUserQuestion`:

> 本次冒烟使用了 N 个临时入口(列出 prepare.md 里的文件路径),如何处理?
> - **撤销**:对每个文件执行 `git checkout HEAD -- {file}` 还原(只对原本已 tracked 的文件生效;新增文件提示用户手动 `rm`)
> - **暂不处理**:保留在工作区,由你自己决定后续(stash / 留到下次 / 手动提交)
> - **提交到远程**:正常 `git add {files} + git commit + git push`(默认提示用户检查 commit message)

不靠 CI、不靠纪律——清理决策在每次冒烟结束时显式做掉,不留隐患。

#### B2 — smoke 侧(改 SKILL.md 第 3 步「执行计划」)

执行计划表渲染后,**追加 prepare.md 的渲染**:把 actor 表 / 预置数据 / 外部依赖 / 非 HTTP 触发点逐段呈现给用户。

随后**一次性** `AskUserQuestion`(批量问):
- 「以下准备项是否全部就绪?」
  - 「全部就绪,开跑」(默认)
  - 「未就绪 / 需调整,先暂停」
  - 「prepare.md 内容已过期,请通知 qa 更新」

未就绪时不开跑;过期时中止并提示用户回流到 qa。

### 收益
- 把"冒烟前准备"从口头交接变成可审计文档
- 非 HTTP 入口体验大幅改善,且不需要重型 tmux 编排
- 过期信号有明确出口

### 代价
- qa 每个 slug 多产一份文档 + 一次决策对话
- 临时入口在冒烟结束时由用户显式清理(撤销 / 暂存 / 提交三选一),不依赖 CI 或纪律
- 设计方案 B 不能与"轻量 builder subagent 加入口"解耦——这是它能成立的前提

---

## 方案 C:逐 step 暂停(默认行为,无模式切换)

### 现状
- orchestrator 顺序跑 step,只在脚本里写了 `wait_user_action` 才停
- 纯 HTTP step(如登录)跑完就直接进下一个,用户没机会查 DB 核验
- 卡住时只能整个中断重来,丢失 state.env 上下文

### 改法

**前提**:用户每次 step 后都要查表确认数据状态——所以根本不存在"连续跑"的合理场景。删除最初设想的"连续/单步"模式选择,**默认行为就是逐 step 暂停**。

**C1 — smoke-common.sh 加新函数 `step_checkpoint`**:
- orchestrator 模板里,在每个 step 调用**之后**插入 `step_checkpoint {step-file} {result}`(不需要 step 之前的 checkpoint——反正都要停一次,合并到 step 后即可)
- 函数无需开关,默认生效。非交互环境(`HARNESS_NONINTERACTIVE=1`)下自动跳过(沿用现有约定)

**C2 — checkpoint 交互**:
打印 step 结果摘要 + state.env 关键字段(token / orderNo 等) + DB 核验提示(若该 step 的 prepare 标注了核验点),然后等用户输入:

| 输入 | 行为 |
|------|------|
| `c`  | 继续下一 step(默认) |
| `s`  | 跳过下一 step(标记 SKIP,继续后续) |
| `r`  | 重跑当前 step(状态保留,清掉本次失败标记) |
| `d`  | 调试模式:打印 `state.env` 路径 + 在另一个终端的重跑命令,阻塞等用户调试完输入 `c` |
| `a`  | 中止整个冒烟 |

**C3 — 与现有 `wait_user_action` 的关系**:
- step 内部已有的 `wait_user_action`(业务侧的人工触发 / 数据核验)**保留不动**——那是脚本作者写死的业务核验点
- `step_checkpoint` 是 step 外的统一暂停,即使 step 内部没写 `wait_user_action` 也会停
- 如果某个 step 既有 `wait_user_action` 又触发 `step_checkpoint`,用户体验上会是"step 内核验一次 → step 结束再确认一次"。可以接受(频次低,且语义不同:前者是脚本指定的"必须核验",后者是技术性"是否进入下一 step")

### 收益
- 与"每次都查表"的真实工作方式契合
- 失败时 state 不丢,可重跑/调试
- 删掉模式选择,SKILL.md 第 3 步少一个询问

### 代价
- 新增一个公共函数 + 模板每个 step 后多一行 `step_checkpoint`
- "调试模式 d" 的"另开终端"心智成本——用户需要理解不能在 smoke 进程里调试同一个 step

---

## 方案 D:复利经验 (XML 仓储)

### 现状
- 每次冒烟是孤立事件,踩过的坑下次还要再踩
- 没有沉淀机制,经验仅存于用户脑中

### 改法

#### D1 — 仓储位置与 schema

每 slug 一份:`.harness/smoke-tests/{slug}/lessons.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lessons slug="order-create" updated="2026-05-15" version="1">

  <category name="trigger-essentials" label="触发要点">
    <item id="auth-token">
      创建订单需先调 /auth/login,token 30min 过期。
      step 01 已固化此流程,无需手动准备。
    </item>
  </category>

  <category name="data-prep" label="数据准备">
    <item id="product-stock">
      product_stock 需预置 sku=SKU001 的库存 ≥ 10,否则 step 03 必失败。
    </item>
  </category>

  <category name="known-pitfalls" label="已知坑">
    <item id="mq-delay">
      order.paid MQ 消费有 5s 延迟,step 04 的 wait_until 至少给 10s,否则误报 FAIL。
    </item>
  </category>

</lessons>
```

**Schema 约定**:
- `<lessons>` 根节点必须有 `slug`、`updated`、`version` 属性
- `<category>` 的 `name` 是 slug-friendly 标识符(用于去重/合并),`label` 是中文展示名
- 推荐(非强制) category:`trigger-essentials` / `data-prep` / `known-pitfalls` / `account-matrix` / `perf-baseline`
- `<item>` 必须有 `id`(slug-friendly,便于"更新而不是新增"),body 是自由文本
- 解析时:同 `id` 的 item 视为同一条经验,合并按"用户确认的最新版本"覆盖

**为什么 XML 不是 JSON/Markdown**:
- 比 JSON 人类可读、可手改
- 比 Markdown 可结构化解析(skill 合并新经验时按 id 找到旧条目)
- 节点属性自然承载 metadata(slug / updated / version)
- 主流语言/工具(包括 bash 的 xmllint)都能处理

#### D2 — 加载时机:SKILL.md 第 3 步

如果选定 slug 下存在 `lessons.xml`,在 prepare.md 渲染**之前**先渲染 lessons:

```
本 slug 累积的复利经验(共 N 条):
  [触发要点]
    - auth-token: 创建订单需先调 /auth/login,token 30min 过期
  [数据准备]
    - product-stock: product_stock 需预置 sku=SKU001 ...
```

随后 `AskUserQuestion`:
- 「以上经验仍然适用?」
  - 「全部仍适用」(默认)
  - 「部分已过期,我手动改 lessons.xml 后重启」(中止当前流程)
  - 「全部跳过,不参考」(本次不应用,但不删除文件)

#### D3 — 总结时机:新增 7.2「复利经验提议」

放在第 7 步「汇总并报告」之后、修复模式询问之前:

skill 基于本次冒烟现场,**主动提议** 0-3 条候选经验。来源:
- 用户在 `wait_user_action` 时输入的提示文本(口头注意事项)
- prepare.md 之外、用户临时补的资源(说明 prepare.md 不全)
- 修复模式触发的真 bug 类型(说明该流程对 X 类问题敏感)
- 单步模式下用户多次重跑同一 step(说明该 step 易踩)

每条候选用 `AskUserQuestion`:
- 「采纳并写入 lessons.xml」
- 「修改后采纳」(进入二次输入,采纳用户改写后的版本)
- 「拒绝」

**采纳逻辑**:
- 提议时 skill 必须给出 `category` + 候选 `id`
- 若 lessons.xml 已存在同 id 的 item → 询问"覆盖 / 追加为新 id / 拒绝"
- 写入后更新 `<lessons updated="..." version="N+1">`

**禁止 skill 静默写入**——任何写入必须经用户 `AskUserQuestion` 明确同意。

#### D4 — 与 prepare.md 的关系

| 工件         | 产出方  | 时机              | 性质                       |
|--------------|---------|-------------------|---------------------------|
| prepare.md   | qa      | 脚本生成时静态产出 | 功能性需求(必须就绪)      |
| lessons.xml  | smoke   | 多次冒烟动态总结   | 经验性提示(参考性、可迭代)|

两者并列,渲染时分两段;prepare.md 缺失 = 必须回流 qa,lessons.xml 缺失 = 正常(首次冒烟没有经验积累)。

### 收益
- "踩过的坑"沉淀成下次自动加载的资产
- 跨次、跨人持久化,不依赖任何记忆/上下文

### 代价
- 新增长期工件,需要约定"什么是值得记的经验"(避免冗余/噪音)
- 总结环节多 1-3 次人机对话(可接受,也可在 SKILL.md 里允许用户一键"本次不总结")

---

## 实施顺序与依赖

```
A (启停权 + result.json)
  ├─ A1 落盘 result.json: smoke-common.sh + 模板
  └─ A2 SKILL.md 第 4 步改"引导式"
        ↓ result.json 是基础设施,B/C/D 都受益
B (准备清单 + 用例视角)
  ├─ B1 改 harness-qa-AGENTS.md 冒烟脚本编写规则
  │     - 强制产出 prepare.md
  │     - 加"是否需要临时 HTTP 入口" AskUserQuestion
  │     - 临时入口走 Agent 工具唤起 subagent (轻量)
  └─ B2 改 SKILL.md 第 3 步,加 prepare.md 渲染 + 就绪确认
C (逐 step 暂停,默认行为)
  ├─ C1 smoke-common.sh 加 step_checkpoint(默认生效)
  └─ C2 模板里在每个 step 调用之后插入 checkpoint
D (复利经验)
  ├─ D1 lessons.xml schema 落地
  ├─ D2 SKILL.md 第 3 步加载 lessons + 适用性确认
  └─ D3 SKILL.md 新增 7.2 经验提议
```

**推荐先后**:A → B → C → D。

理由:
- A 是基础设施(其他都受益于 result.json)
- B 是体验改造主菜,改面最大,需要 qa 配合
- C 独立,可在 A 之后任意时机做
- D 依赖 B 的 prepare.md(同形态长文件,加载/渲染逻辑可复用),应最后

---

## 已决决策记录

设计评审时讨论过的几个问题,最终决定:

1. **临时 HTTP 入口不靠 CI 红线**,改为 SKILL.md 第 7 步汇总后用 `AskUserQuestion` 让用户三选一(撤销 / 暂存 / 提交)。决策权在用户,不依赖外部检查机制。详见方案 B3。
2. **lessons.xml 永久保留,不做陈旧判定**。不加 `confirmed_at`,每次加载全量展示,用户自己判断哪些仍适用。
3. **删除"连续 vs 单步"模式选择,默认就是逐 step 暂停**。理由:用户每次 step 后都要查表核验,根本不存在"连续跑"的合理场景。详见方案 C。
4. **多 slug 启停疲劳问题不存在**:实际场景几乎总是一次只跑 1 个 slug。原方案 A 不需要"批量 escape hatch"。多 slug 顺序运行的相关分支(SKILL.md 第 6 步 checkpoint)在本次改造中维持现状即可。
