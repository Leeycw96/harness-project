---
name: harness-backend-coding-rules
description: harness-backend Builder 写代码与 QA 验收时共用的代码与测试质量红线。
audience: harness-builder,harness-qa
---

# Harness-Backend 代码质量红线

本文件抽取了所有"写代码动作"必须遵守的硬约束。它**不描述编排流程**,只描述"写出来的代码长什么样才算合格"。

各 agent 应在 `<reference>` 引用本文件,而非在自身文档内重复条款。条款修订只改本文件,所有引用方自动同步。

---

## 1. 真实实现零容忍 stub

- API 必须真工作、数据真持久化、CLI 真执行
- 跨模块依赖未就绪时,用 `// TODO: 等 X 模块就绪后接入` 明确标注,**不允许**返回硬编码或假数据糊弄
- 测试通过不等于功能可用 —— 通过 stub 让测试绿 = 欺骗

## 2. 修根因不修症状

- 测试失败:**先看代码逻辑**,不调测试参数让用例通过
- 调用链路异常:**修源头**,不在调用方加补丁绕过
- 修两次仍失败 → 标 TODO 跳过本功能,**不要无限重试**

## 3. TDD 边界(强制)

TDD 单测**只**针对业务域 Service 对外 public 方法 —— 这是契约层。其他对象按下表处理:

| 是否写单测 | 对象 |
|-----------|------|
| **必写** | 业务域 Service 的 public 方法(被 Controller / 其他业务域调用) |
| **不写** | Controller / RPC Provider / MQ Listener / Scheduler 入口层 |
| **不写** | 同一业务域内的 Service-to-Service、private/package 方法 |
| **不写** | DTO/VO 转换、Mapper、Converter、配置类、工具类 |

跨业务域调用(域 A 的 Service 调域 B 的 Service)→ 域 B 那个被调方法属于"域 B 对外契约",必须有 TDD 测试。

## 4. 入口层洁净(强制)

Controller / RPC Provider / MQ Listener / Scheduler 这四类入口**只做**:
- 参数校验
- 序列化 / 反序列化
- 调用 Service

**禁止**在入口层出现:
- if / for / 循环计算
- 状态判断
- 任何业务逻辑

理由:入口层没有单测保护,业务逻辑藏在这里 = 把无回归保护的代码留给人工端到端验证,而人工验证未必覆盖到所有分支。

## 5. 测试质量

- **空测试 = 没测**:`assertTrue(true)` / 只打 log / 空 `setUp` 等同于没有测试
- 必须覆盖业务域 Service 对外 public 方法的**关键分支**(正常 + 异常)
- 断言要有"期望值",不是"调用没抛异常就算过"
- QA 补充测试命名:`QA_<被测类名>_<场景>.java`,与被测类同包

## 6. 持续可运行

- 一个不能 build 的中间状态不是"还在做",是"已经坏了"
- 每个 commit 后应用都能正常启动
- 跨模块依赖处明确写 TODO,而不是返回假数据让构建通过
