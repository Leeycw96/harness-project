# 按使用场景组织的 Spec

Spec 说明工作边界、质量要求和产物标准。规则使用简要描述，正确或错误示例按需添加。Skill 的调度与 Agent 输入仍沿用现有约定，后续单独调整。

## 场景规范

| 场景 | 规范 | 内容 |
| --- | --- | --- |
| 问题调查 | [keel-investigation-spec.md](../../common/refs/keel-investigation-spec.md) | 只读调查、证据、根因确定程度与现场缺口 |
| 方案设计与编写 | [keel-proposal-spec.md](../../common/refs/keel-proposal-spec.md) | 方案权限、目标设计、执行文档、模型、接口与图表标准 |
| 修复说明编写 | [keel-fix-review-spec.md](../../common/refs/keel-fix-review-spec.md) | 五项简要说明、HTML 展示、下载与旧文档兼容 |
| 代码实施 | [keel-implementation-spec.md](../../common/refs/keel-implementation-spec.md) | 授权内实现、测试与提交，遵守已确认设计 |
| 交付验收 | [keel-acceptance-spec.md](../../common/refs/keel-acceptance-spec.md) | 独立验收权限、统一标准、证据与报告 |
| 业务流程文档维护 | [keel-flow-index-spec.md](../../common/refs/keel-flow-index-spec.md) | 按实际代码维护流程索引、状态与证据 |

## 共享标准与场景补充

| 用途 | 规范 | 内容 |
| --- | --- | --- |
| 通用工作要求 | [keel-work-spec.md](../../common/refs/keel-work-spec.md) | 项目约定、授权、改动保护、相关资料与如实报告；不授予业务修改权限 |
| 代码与测试质量 | [keel-code-quality-spec.md](../../common/refs/keel-code-quality-spec.md) | 真实实现、根因、职责、测试与项目检查 |
| 改造点表达 | [keel-code-change-spec.md](../../common/refs/keel-code-change-spec.md) | 类、模块或文件加一句话改动，只约束说明列表 |
| 业务流程表达 | [keel-business-flow-spec.md](../../common/refs/keel-business-flow-spec.md) | 业务阶段与变化的共用粒度 |
| 局部修复边界 | [keel-bug-scope-spec.md](../../common/refs/keel-bug-scope-spec.md) | 修复适用范围、资格字段、批准依据与原场景复验 |

## 兼容引用

现有 `keel-dev-spec.md`、`keel-qa-spec.md`、`keel-fix-spec.md`、`keel-plan-spec.md`、`keel-call-chain-spec.md` 只保留原章节和新规范引用，不重复规则正文。

本次不改变 Skill 或 Agent 定义、输入组合、运行阶段、批准字段、模板和渲染接口。兼容入口仅保持当前引用有效，不代表新的场景输入组合已经接入。
