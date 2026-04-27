# 工件格式规格

本文档定义 harness-backend 流程中所有工件的格式要求。Builder 和 QA 在产出对应文件时必须遵循这些规格。

> 所有工件读写于**产出目录**（`{OUTPUT_DIR}`，格式为 `.harness/iterations/{branch}/run-{N}/`），启动时从消息中提取路径。例外：call-chain、smoke-tests 位于项目根目录。

---

## 文件总览

| 文件 | 产出者 | 位置 | 生命周期 |
|------|--------|------|---------|
| `plan.md` | 编排层 | `{OUTPUT_DIR}/` | 只读输入 |
| `build-scope-v{N}.md` | Builder | `{OUTPUT_DIR}/` | 每轮对齐一个版本 |
| `qa-feedback-round-{N}.md` | QA | `{OUTPUT_DIR}/` | 每轮评审一份 |
| `user-adjustment-round-{N}.md` | Builder | `{OUTPUT_DIR}/` | 用户调整阶段每轮一份 |
| `{slug}.md` | Builder | `.harness/call-chain/` | 跨迭代持久，功能变更时更新 |
| `QA_*.java` | QA | `src/test/java/` | Git 跟踪 |
| `smoke-common.sh` | QA | `.harness/smoke-tests/` | 跨迭代持久 |
| `smoke-{slug}.sh` | QA | `.harness/smoke-tests/` | 跨迭代持久 |
| `README.md` | QA | `.harness/smoke-tests/` | 跨迭代持久 |
| `*.log` | QA | `{OUTPUT_DIR}/qa-evidence/` | 运行副产品 |
| `done` | QA | `.harness/` | 完成信号 |

---

## build-scope-v{N}.md

Builder 产出的技术方案，必须包含以下章节：

### 技术栈确认
基于 CLAUDE.md 中的技术栈信息，列出选型及理由。

### 功能实现清单
对照 plan.md 逐条列出每个功能：
- 每个功能标注一个**英文 kebab-case slug**（如 `user-registration`、`create-order`）
- 已有功能复用 `.harness/call-chain/` 中的 slug，新功能分配新 slug
- 标注预计的实现方式摘要
- slug 将贯穿 call-chain 文件名和 E2E 脚本名

### 每个功能的验证目标
- plan.md 有验收标准 → 直接引用
- plan.md 只有交互流程 → 推导可验证标准
- 必须具体可测（如"POST /api/users 返回 201 并包含 userId 字段"），**不接受模糊描述**

### 实现顺序
基础架构 → 核心功能 → 增强功能 → AI 集成

---

## qa-feedback-round-{N}.md

QA 每轮评审产出的报告：

```markdown
# QA 评审报告

## 总评
[1-2 句话：质量概述 + 最关键问题]

## 分数总览

| 标准 | 分数 | 阈值 | 是否通过 |
|------|------|------|---------|
| 功能完整性 | X/10 | 7 | PASS/FAIL |
| 产品深度 | X/10 | 6 | PASS/FAIL |
| 接口规范性 | X/10 | 6 | PASS/FAIL |
| 代码质量 | X/10 | 6 | PASS/FAIL |

## 逐功能验证

### 功能 1：[名称]
| 验证目标 | 结果 | 测试方式 | 证据 |
|----------|------|---------|------|
| [目标] | PASS/FAIL | JUnit/curl/sh/代码审查 | [输出摘要或证据文件路径] |

## 必须修复的问题（按优先级）

### P0 - 阻断性问题
1. **[标题]**
   - 重现步骤：...
   - 预期行为：...
   - 实际行为：...
   - 根因分析：...
   - 建议修复方向：...

### P1 - 重要问题
### P2 - 改进建议

## Java 测试汇总

| 项目 | 结果 |
|------|------|
| 构建工具 | Maven / Gradle |
| Builder 测试类数量 | X 个 |
| Builder 测试通过/失败 | X / Y |
| QA 补充测试类数量 | X 个 |
| QA 补充测试通过/失败 | X / Y |
| 测试覆盖的功能模块 | [列出] |

## E2E 集成测试汇总

| 项目 | 结果 |
|------|------|
| E2E 脚本数量 | X 个 |
| 通过/失败/跳过 | X / Y / Z |
| 覆盖的业务流程 | [列出] |
| 异步链路验证 | 是/否（方式：HTTP 轮询/DB 查询/Java） |

## 最终判定
**APPROVED** / **REJECTED**
[如 REJECTED，列出最小必修集]
```

---

## user-adjustment-round-{N}.md

Builder 在用户调整阶段产出，**收到用户输入后、实现代码前**写入，确保用户原始需求不因上下文压缩而丢失。N 从 1 开始，每轮用户调整递增。

```markdown
# 用户调整需求 Round {N}

## 原始需求
[逐条记录用户输入的完整内容，保持原文]

## 需求分类

| 序号 | 需求摘要 | 类型（新增/修改/删除） |
|------|---------|---------------------|
| 1    | ...     | 新增                |
| 2    | ...     | 修改                |
```

QA 验证时逐条对照此文件与代码变更（git diff），确认 Builder 没有遗漏任何用户需求。

---

## Call-Chain 文件

位置：`.harness/call-chain/{slug}.md`（项目根目录，跨迭代持久）

**核心原则**：一个完整业务流程 = 一个文件，按业务步骤分章节。**只记录入口方法，不展开内部调用链**。

### 格式要求

- 文件名使用 build-scope 中定义的 slug
- 入口方法类型：Controller 方法、Listener、ScheduledTask、Executor
- 不记录入口方法内部的 Service/Repository/Utils 调用
- 类名和方法签名必须与实际代码一致
- 纯同步功能只需一个章节
- 验证点必须具体可测
- 外部依赖未就绪时标注 `[外部依赖：未就绪]` 并说明服务名称和预期接口

### 每个章节包含

- **API/异步入口**：端点或入口方法签名、请求/响应格式
- **触发条件**（异步步骤）：事件来源
- **数据依赖**：前置状态条件
- **验证点**：该步骤的可测试断言

详细格式示例见 `.claude/skills/harness-backend/assets/call-chain-example.md`。

---

## 冒烟测试脚本

位置：`.harness/smoke-tests/`（项目根目录，跨迭代持久）

定位：把 call-chain 描述的业务流程脚本化为半自动冒烟测试——HTTP 步骤自动跑，非 HTTP 触发（Scheduler / MQ / RPC）引导用户手动完成。全程真实链路，不写 Mock 代码、不新增 Java 测试类。

### smoke-common.sh — 公共函数库

提供所有冒烟脚本复用的函数：

| 函数 | 用途 |
|------|------|
| `start_service()` | 启动应用，后台运行并记录 PID |
| `wait_for_service()` | 轮询端口/健康检查，超时失败 |
| `stop_service()` | 优雅关闭（kill PID） |
| `login()` | 调用登录接口，导出 TOKEN 变量 |
| `assert_status()` | 检查 HTTP 状态码 |
| `assert_json_field()` | 检查 JSON 响应字段 |
| `assert_db_row()` | DB 查询单行，校验字段值 |
| `assert_db_count()` | DB 查询行数，校验数量 |
| `db_query()` | 任意 DB 查询，返回结果供脚本捕获 |
| `wait_until()` | 通用条件轮询（HTTP 或 DB），超时失败 |
| `wait_user_action()` | 人工触发步骤：打印指令并阻塞 read，接受 c/s/a；非交互环境（`HARNESS_NONINTERACTIVE=1`）自动 SKIP |
| `skip_if_unavailable()` | 检查外部依赖，不可用时输出 SKIP（不判 FAIL） |
| `log_pass()` / `log_fail()` / `log_skip()` | 结果记录 |

### smoke-{slug}.sh — 功能冒烟脚本

每个脚本是自包含的完整生命周期：启动服务 → 等待就绪 → [登录] → 业务步骤（接口断言 + DB 断言）→ [异步轮询 / 人工触发等待 → 后置 DB 断言] → 停止服务。

编写规则：
- 简单功能（登录）：启动 → curl → 接口断言 → DB 断言 → 关闭
- 业务功能（创建订单）：启动 → 登录 → 请求 → 接口断言 → DB 断言 → [异步轮询 / 人工触发 → 后置 DB 断言] → 关闭
- 跨功能流程：一个脚本中串联多步骤；步骤间通过捕获接口返回值（orderNo 等）作为下一步 DB 查询条件或入参
- 验证维度：每步至少接口断言 + 数据状态断言；仅断言 HTTP 200 不算冒烟测试
- 异步与人工触发：自动可达走 `wait_until`；自动不可达（Scheduler / MQ / RPC）走 `wait_user_action` 引导用户手动触发，完成后立刻执行后置 DB 断言
- 外部依赖 `[未就绪]`：用 `skip_if_unavailable` 包裹，保留完整逻辑以便依赖就绪后启用

### 人工触发步骤片段

```bash
wait_user_action \
  "请触发 OrderTimeoutScheduler 任务（订单超时关单）" \
  "管理后台 → 任务调度 → OrderTimeoutScheduler → 立即执行"
# 用户输入 c 后到达此处，立刻执行后置 DB 断言
assert_db_row "orders" "order_no='${ORDER_NO}'" "status" "CLOSED"
```

### README.md

必须包含：
- 概述和前置条件（JDK 版本、数据库、端口、CLI 工具）
- 文件清单表（脚本 | 测试功能 | 涉及接口 | 是否含人工触发 | 外部依赖）
- 外部依赖状态表（服务 | 影响脚本 | 被 skip 步骤 | 负责人 | 预计就绪时间）
- 运行方式和维护说明
