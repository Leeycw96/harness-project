# 按使用场景组织的 Spec

Spec 说明工作边界、质量要求和产物标准。正文直接用条目列出规则，正确或错误示例按需添加并保留示例前缀。Skill 按步骤选择场景规范，通过“任务＋Spec”两段派发；调度和记录规则以各 Skill 为准。

每份 Spec 开头使用 YAML 信息块：`name` 为全局唯一的规范名称，当前采用文件名去掉 `.md`；`description` 简述规范用途与使用场景。兼容入口也有独立名称，并在说明中标明兼容用途。

## 场景规范

| 场景 | 规范 | 内容 |
| --- | --- | --- |
| 问题调查 | [keel-investigation-spec.md](../../common/refs/keel-investigation-spec.md) | 只读调查、证据、根因确定程度与现场缺口 |
| 方案设计与编写 | [keel-proposal-spec.md](../../common/refs/keel-proposal-spec.md) | 方案权限、目标设计、执行文档、模型、接口与图表标准 |
| 修复说明编写 | [keel-fix-review-spec.md](../../common/refs/keel-fix-review-spec.md) | 五项简要说明、HTML 展示、下载与旧文档兼容 |
| 代码实施 | [keel-implementation-spec.md](../../common/refs/keel-implementation-spec.md) | 授权内实现、测试与提交，遵守已确认设计 |
| 交付验收 | [keel-acceptance-spec.md](../../common/refs/keel-acceptance-spec.md) | 独立验收权限、统一标准、证据与报告 |
| 验收评分 | [keel-qa-scoring-spec.md](../../common/refs/keel-qa-scoring-spec.md) | 目标完成率、通用检查结果、初验与复验 JSON 记录 |
| 业务流程文档维护 | [keel-flow-index-spec.md](../../common/refs/keel-flow-index-spec.md) | 按实际代码维护流程索引、状态与证据 |

## 共享标准与场景补充

| 用途 | 规范 | 内容 |
| --- | --- | --- |
| 通用工作要求 | [keel-work-spec.md](../../common/refs/keel-work-spec.md) | 项目约定、授权、改动保护、相关资料与如实报告；不授予业务修改权限 |
| 文档表达 | [keel-document-writing-spec.md](../../common/refs/keel-document-writing-spec.md) | Markdown 用短句、直白说法和必要引用，保留设计与验证依据；作为 Agent 输入使用 |
| 代码与测试质量 | [keel-code-quality-spec.md](../../common/refs/keel-code-quality-spec.md) | 真实实现、根因、职责、测试与项目检查 |
| 改造点表达 | [keel-code-change-spec.md](../../common/refs/keel-code-change-spec.md) | 类、模块或文件加一句话改动，只约束说明列表 |
| 业务流程表达 | [keel-business-flow-spec.md](../../common/refs/keel-business-flow-spec.md) | 业务阶段与变化的共用粒度 |
| 局部修复边界 | [keel-bug-scope-spec.md](../../common/refs/keel-bug-scope-spec.md) | 修复适用范围、资格字段、批准依据与原场景复验 |

## 兼容引用

现有 `keel-dev-spec.md`、`keel-qa-spec.md`、`keel-fix-spec.md`、`keel-plan-spec.md`、`keel-call-chain-spec.md` 只保留原章节和新规范引用，不重复规则正文。

当前 Skill 直接选用场景规范；兼容入口用于已有文件和章节引用。角色定义由调用环境加载，Agent 仅接收任务与 Spec；主会话管理审批、阶段、进度和恢复，不再下发旧任务步骤或运行字段。旧 profile、批准快照、模板和渲染接口继续兼容。

Agent 保留换项目后仍适用的做事风格，具体检查内容集中在 Spec。直接增删 Spec 中的检查条目即可调整 QA 工作；Skill 继续编排同一组 Agent 和规范，不配置检查开关或高分减检策略。
