# 按使用场景组织的 Spec

Spec 只说明产出物要满足什么：内容、格式、质量和验收结果。Agent 的做事风格约束行为，Skill 负责安排任务与协作。正文直接列简短规则，正确或错误示例按需添加。

每份 Spec 开头使用 YAML 信息块：`name` 全局唯一，采用文件名去掉 `.md`；`description` 简述产物要求与使用场景。

## 归属判断

| 要求 | 放在哪里 | 示例 |
| --- | --- | --- |
| 本次要完成什么、允许改什么 | 任务 | 只读调查退款失败的原因；返回结论与未确定事项 |
| 交付结果必须具备什么 | Spec | 调查报告包含根因、影响范围和未确定事项 |
| Agent 如何工作 | 做事风格 | 先核实事实；只读调查时不改代码 |
| 谁接手、何时确认和推进 | Skill | 调度 Builder 调查；用户确认后安排修复 |

错误示例：Spec 要求“先读代码，再运行测试，最后写报告”。

正确示例：Spec 要求“报告有简短结论、实际验证结果和未验证事项”。

文档中的栏目顺序、代码运行后的业务行为属于产物要求；Agent 的操作顺序、工具选择和修改权限属于行为或本次任务授权。

## 场景规范

| 场景 | 规范 | 内容 |
| --- | --- | --- |
| 问题调查 | [keel-investigation-spec.md](../../common/refs/keel-investigation-spec.md) | 调查结论、根因确定程度与现场缺口 |
| 方案设计与编写 | [keel-proposal-spec.md](../../common/refs/keel-proposal-spec.md) | 调研结果、执行文档、模型、接口与图表标准 |
| 修复说明编写 | [keel-fix-review-spec.md](../../common/refs/keel-fix-review-spec.md) | 五项简要说明、HTML 展示与下载 |
| 代码实施 | [keel-implementation-spec.md](../../common/refs/keel-implementation-spec.md) | 实现、测试、验证和提交的交付结果 |
| 交付验收 | [keel-acceptance-spec.md](../../common/refs/keel-acceptance-spec.md) | 简短验收结论与未完成说明 |
| 验收评分 | [keel-qa-scoring-spec.md](../../common/refs/keel-qa-scoring-spec.md) | 功能目标与通用检查项分数、独立初验与复验 JSON |
| 业务流程文档维护 | [keel-flow-index-spec.md](../../common/refs/keel-flow-index-spec.md) | 主流程说明、文本状态机和业务入口；默认 Spec 内嵌完整示例，新旧文档都按用户/客户业务目标收敛 |

## 共享标准与场景补充

| 用途 | 规范 | 内容 |
| --- | --- | --- |
| 通用交付标准 | [keel-delivery-spec.md](../../common/refs/keel-delivery-spec.md) | 结果完整、真实、一致，改动符合授权范围 |
| 文档表达 | [keel-document-writing-spec.md](../../common/refs/keel-document-writing-spec.md) | Markdown 用短句、直白说法和必要引用，保留设计与验证依据；作为 Agent 输入使用 |
| 代码与测试质量 | [keel-code-quality-spec.md](../../common/refs/keel-code-quality-spec.md) | 真实实现、根因、职责、测试与项目检查 |
| 改造点表达 | [keel-code-change-spec.md](../../common/refs/keel-code-change-spec.md) | 类、模块或文件加一句话改动，只约束说明列表 |
| 业务流程表达 | [keel-business-flow-spec.md](../../common/refs/keel-business-flow-spec.md) | 业务阶段与变化的共用粒度 |
| 局部修复边界 | [keel-bug-scope-spec.md](../../common/refs/keel-bug-scope-spec.md) | 分类结论、资格字段、批准产物与验收记录 |

## 使用与调整

Skill 按场景选择规范，通过“任务＋Spec”两段派发。任务包含目标、范围与授权、必要资料和交付要求；Spec 输入为名称与绝对路径，可引用二级章节。角色及做事风格由调用环境加载。

只保留当前场景规范，旧 Dev、QA、Fix、Plan、CallChain Spec 入口及通用工作 Spec 已移除。当前引用统一使用通用交付标准和对应场景产物规范。

Agent 保留换项目后仍适用的做事风格，自主选择工作方法。直接增删 Spec 的产物要求即可调整 QA 的验收内容，Skill 无需跟着变化，不配置检查开关或自动减检。

验收正文简述总体结论和功能目标结果，失败、遗漏或未验证事项说明必要的原因与影响。评分 JSON 只有检查项和对应分数，不要求证据引用、逐项评分理由或日志存档。方案总览表达完整业务生命周期，时序图表达关键交互与原子操作，必要实现约束留在功能 MD；完整性按整份设计判断，避免报告和图表重复堆砌细节。
