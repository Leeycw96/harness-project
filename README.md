# Keel

当前版本: **4.0.8**（见 `VERSION`）。

版本更新记录见 [CHANGE_LOG.md](CHANGE_LOG.md)。

命令入口为 `keel`，开发模式为 `dev`，计划与运行数据使用 `.keel/`。本次更名直接使用新名称，不提供旧命令别名或自动迁移。

Keel 是一组面向 Codex App 的 skills + agent 手册，用于编排 Planner、Builder、QA 和 DocWriter，完成从业务理解到代码交付的开发工作流。

## 目录结构

```text
keel-project/
├── bin/keel          # 部署 CLI
├── install.sh        # 把 bin/ 写入 PATH
├── common/           # 共享规范和脚本，部署到 .codex/common/
├── keel-plan/        # /keel-plan 编排、Planner、模板与渲染入口
├── keel-dev/         # dev skills 与 Codex custom agents
└── keel-test/        # 库存服务的隔离试验产物与审阅示例
```

模式目录使用 `keel-<mode>/skills/` 和 `keel-<mode>/agents/`。

## 安装 CLI

```bash
git clone <this-repo>
cd keel-project
./install.sh
source ~/.zshrc      # 或新开一个终端
```

`install.sh` 只把 `bin/` 加入 PATH,不会部署任何 skill。

## 部署

使用 `--codex` 部署。默认目标为当前目录:

```bash
cd /path/to/your/project
keel dev --codex
```

也可以指定目标目录:

```bash
keel dev --codex /path/to/your/project
```

`keel dev` 会同时部署 `/keel-plan`、`/keel-dev` 和 `/keel-fix`。

旧格式不再支持:

- `keel dev`
- `keel dev /path/to/project`
- `keel --codex dev`
- `keel --runtime ...`
- `keel ... --codex-cli`

## Codex App 部署结果

```text
.agents/
└── skills/
    ├── keel-plan/
    │   ├── SKILL.md
    │   ├── assets/
    │   │   ├── plan-template.md
    │   │   ├── plan-template.features/  # 按功能拆分的文档示例
    │   │   ├── plan-review-template.md
    │   │   └── plan-view-template.html
    │   └── scripts/
    │       └── render-plan-html.sh
    ├── keel-dev/
    └── keel-fix/
.codex/
├── common/
│   ├── refs/
│   │   ├── keel-delivery-spec.md      # S：通用交付标准
│   │   ├── keel-document-writing-spec.md # S：简短易懂的 Markdown 表达
│   │   ├── keel-code-quality-spec.md  # S：代码与测试质量
│   │   ├── keel-investigation-spec.md # S：问题调查
│   │   ├── keel-proposal-spec.md      # S：方案设计与编写
│   │   ├── keel-fix-review-spec.md    # S：修复说明编写
│   │   ├── keel-implementation-spec.md # S：代码实施
│   │   ├── keel-acceptance-spec.md    # S：交付验收
│   │   ├── keel-qa-scoring-spec.md    # S：评分记录
│   │   ├── keel-flow-index-spec.md    # S：流程文档维护
│   │   ├── keel-bug-scope-spec.md     # S：局部修复边界
│   │   ├── keel-code-change-spec.md   # S：改造点表达
│   │   └── keel-business-flow-spec.md # S：业务流程表达
│   └── scripts/
├── agents/
│   ├── keel-planner.md
│   ├── keel-planner.toml
│   ├── keel-builder.md
│   ├── keel-builder.toml
│   ├── keel-qa.md
│   ├── keel-qa.toml
│   ├── keel-doc-writer.md
│   └── keel-doc-writer.toml
└── .keel/
    └── installed-manifest
```

## 语言与项目适配

业务开发规则与语言无关：先识别项目既有语言、架构、测试和 CI 配置，再选择代码落点与验证命令。业务契约可由模块、函数或类方法承载，不强制 Controller/Service 分层、Java 测试后缀或 Maven。多语言仓库按受影响模块分别验证；没有独立编译阶段时使用适用的类型/语法、加载和测试检查，不把未执行记录为通过。

模板保留明确标注的 Java/PostgreSQL 示例用于说明写法，实际计划必须替换为项目事实。Python 3 和 PlantUML/Java 是 Keel HTML 渲染工具的依赖，不要求业务项目采用 Python 或 Java。

## 阶段职责

借鉴 [Karpathy 启发的四项原则](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/README.zh.md)，按 Keel 职责整合：Plan 在制定计划时核实假设、调研歧义并请用户完成关键取舍；Dev 按已确认方案落实简洁优先、精准修改与目标驱动，Builder 实现，QA 对照目标与实际结果验收，并按 QA 结果返修。

## ASO 设计规范

本项目按 **Agent、Spec、Orchestration** 组织能力。A 定义角色与做事风格，S 约束产出物，O 由 Skill 安排任务和协作。管理者给清任务及交付要求，Agent 自主决定如何完成。

| 层次 | 应包含 | 不应包含 |
| --- | --- | --- |
| **A（Agent）** | 角色、能力、做事风格：专业方法、行为边界、事实判断 | 固定项目规范路径、公司协作流程、状态字段、重试次数、完成命令 |
| **S（Spec）** | 产物的内容、格式、质量及适用条件：代码、文档、图表、报告、评分 JSON | Agent 的工作步骤、工具选择、操作权限、调度和恢复 |
| **O（Orchestration）** | `SKILL.md` 中的高层编排：主要步骤及顺序、执行者、任务与 Spec、必要的用户决策和步骤衔接 | 重写 Agent 的做事风格，重复维护 Spec 中的标准，细管 Agent 的执行方法，堆叠限制，将编排主线拆到独立编排文档 |

### 编写与调整要求

1. Agent Markdown 固定为“角色、能力、做事风格”。风格约束行为，如最小修改、TDD、先核实事实、只读调查不改代码、独立验收；换项目仍成立，不放项目路径或固定检查清单。TOML 只注册并加载角色说明。
2. Spec 按使用场景组织，只定义产物的内容、格式、质量和适用条件。Builder 与 QA 使用同一份代码和测试标准。本次目标与授权范围放在任务中；如何调查、实现或验收由 Agent 自主决定。
3. 每个 `SKILL.md` 说明从接收输入到最终交付的主要步骤及顺序，包括主会话承担的沟通、调度和交付。涉及 subagent 时，明确调用哪个 Agent、这一步要完成什么、依据什么 Spec，并提供必要的任务资料；仅在影响步骤衔接时补充输出、分支或恢复说明，不要求每一步套用完整字段模板。
4. 信任 Agent 的专业能力，由其依据任务、Spec 和项目事实自主选择调研路径、工具与局部执行方法。编排聚焦目标和协作，不逐项规定模型能够自主完成的操作，不重复角色风格或 Spec，不堆叠禁止事项。仅保留授权边界、关键用户决策、必要质量门禁和跨步骤交接要求；主会话依据结果推进，已有明确决定直接沿用。
5. 编排流程和 A/S 选择统一维护在所属 `SKILL.md`，不另设 `keel-dev-orchestration.md` 一类独立编排文件。可引用场景 Spec、模板和可执行脚本；`SKILL.md` 只说明必要调用及结果衔接，不展开脚本内部实现，不以外部引用代替流程主线。
6. A/S 可以独立替换，O 核对能力、引用和交付接口。缺资料、规范冲突或超出授权时说明原因，不能静默回退或扩大任务。
7. 重组文件时保留目标、质量要求和门禁，同步调用方、部署、模板、校验与测试；旧 Spec 接口不保留。体量统计区分编排、固定输入和动态任务资料，不把搬文件当成上下文节省。

归属示例：任务说明“只读调查退款失败”；做事风格说明“先核实事实，不擅自改代码”；Spec 说明“报告包含根因、影响和未确定事项”。文档栏目顺序属于产物格式，“先读代码再运行测试”属于工作方法。

### 方案从简设计

- **只设计本期必要改动**：沿用现有架构与能力，不顺带重做整个功能，不为未来需求增加抽象或配置。
- **变化点讲清楚**：写明新增或修改的条件、状态、数据和行为；未改动部分只说明沿用哪些已有步骤及依据。
- **图表表达主线**：时序图保留关键交互、业务分支和事务边界；SQL、锁、错误码等必要细节放功能 MD 或接口设计。完整性按整份设计判断，不要求把全部约束塞入图中。
- **明确本期不涉及的内容**：MD 保留固定章节，无模型或接口变化时标注“本期不涉及变更，沿用现有实现”；HTML 省略无变更的可选栏目；按共用粒度判定业务流程有变化时必须有总览，无变化可省略。
- **先核实影响再标注**：新增状态可能改变接口枚举、数据库约束或失败重试逻辑；未新增接口/字段不等于没有契约或 SQL 变化。引用本次其他功能的共享设计仍属于本期涉及。

### 共用业务流程粒度

`common/refs/keel-business-flow-spec.md` 由 Plan 和开发编排分别下发给 Planner、DocWriter。一个流程围绕独立业务目标，从业务触发到明确结果；节点按业务阶段或决策划分，HTTP/RPC、MQ 消费、定时任务和回调是技术触发点，不能直接当作业务节点或按入口数量分文件。

比较当前与目标流程时使用同一粒度：触发场景、结果类型、阶段、先后关系、业务分支或责任交接变化，才算业务流程变化。内部实现、规则细节或状态表达变化，若业务阶段与路径不变，则总览可省略；需要用户查看整体流程时仍可提供。

DocWriter 仍按原维护条件检查入口、异步推进、状态及流转变化，记录业务入口、主流程与状态；省略 Plan 总览不等于跳过索引维护。普通内部调用栈不展开，两个角色共用粒度，但 Plan 设计本次目标流程，DocWriter 记录验收后代码实际具备的流程，各自职责和门禁不变。

Plan 与 Fix 的改造点共用 `common/refs/keel-code-change-spec.md`：按真实类、模块或文件列出一句话改动，避免展开方法、行号和测试细节。Plan 起草/修订时下发给 Planner，Fix 编写/修订说明时由主会话加载，执行者依目标和调查依据自主定位。

### 职责与文件归属

各职责的文件归属如下：

| 工作 | A | S | O |
| --- | --- | --- | --- |
| 方案设计 | Planner | 方案编写 + 通用交付 + 业务流程/改造点表达 | keel-plan 的 SKILL.md：调研、决策沟通、起草/修订、渲染与最终确认 |
| 开发 | Builder | 代码实施 + 通用交付 + 代码与测试质量 | keel-dev 的 SKILL.md：初始化、实现、验收、返修与交付 |
| 验收 | QA | 交付验收 + 通用交付 + 同一代码与测试质量 + 评分记录 | 所属 keel-dev 或 keel-fix 的 SKILL.md |
| 流程维护 | DocWriter | 流程文档维护 + 通用交付 + 业务流程表达 | keel-dev 的 SKILL.md：判断是否需要维护、调度与结果处理 |
| 局部缺陷修复 | Builder、QA | 按步选择调查/实施/验收规范 + 局部修复边界；说明编写另用修复说明与改造点表达 | keel-fix 的 SKILL.md：定位、分流、独立审阅、修复验收与现场复验 |

Plan 的主会话负责沟通、调度、渲染和交付，调研与文档编写交给 Planner。生成的 HTML 与执行 MD 使用同一份设计内容。

### Spec 格式与引用

Spec 位于 `common/refs/`，按使用场景和共享标准分类，完整清单见 [Spec 目录](docs/specs/README.md)。每份文件开头用 YAML 声明 `name` 和 `description`：`name` 全局唯一，当前采用文件名去掉 `.md`；`description` 简述用途和使用场景。

正文直接列简短易懂的产物要求，正确或错误示例按需添加并保留前缀。当前 Skill 直接选择场景规范，旧名称与章节入口已移除。

Planner、Builder、QA 和 DocWriter 的 Spec 输入共用 `keel-document-writing-spec`：Markdown 用短句和直白说法，少写重复背景、过程和图表复述；只保留必要设计、字段、SQL、图表及验证结果，不要求整理证据或保存验证日志。它作为写作规范输入，不增加产物检查或固定字数限制。

Agent 的做事风格不固化项目检查清单。需要增删某项 QA 检查时，直接修改对应 Spec；Skill 继续下发同一份规范并编排执行，不增加检查开关或自动高分策略。

### 产物表达

| 产物 | 正文重点 | 详细信息的位置 |
| --- | --- | --- |
| Plan 业务总览 | 同一个业务的完整生命周期，通常一张图覆盖触发、主要阶段、关键分支和结果 | 对应功能的执行设计；总览不按接口拆图或展开技术处理 |
| Plan 时序图 | 关键交互、业务分支，以及必须一起成功或失败的操作 | 功能 MD 的必要说明和接口设计，保留 SQL、锁、错误码等约束 |
| QA 结果 | 通过时只返回简短结论、当次评分路径和必要遗留项，可省略报告；未通过时报告简述阻断项、原因与影响 | 评分 JSON 只保留检查项和对应分数，不要求逐项解释、证据引用或日志存档 |

QA 通过时默认省略 `qa-feedback.md`，如需生成也只写简短概要；失败、遗漏或未验证事项说明必要的原因与影响。完整性按模型、图与说明、接口共同判断；图外约束保留在下载 MD 和开发快照中，不要求全部塞入图里，也不设统一字数上限。具体要求见方案和验收 Spec，Skill 的编排及 Agent 的工作方法保持各自职责。

### QA 评分与查看

QA 交付当前规范要求的检查结果与评分 JSON，可用 `keel-qa-score.py` 生成和查看。Spec 规定记录格式与算分规则，Agent 自主选择生成方法。目标完成率为完成目标数 ÷ 快照总目标数 × 100；全部验收条件通过才算完成，遗漏或未验证仍计入总数。其他检查按实际条目计分，没有结果时不补满分。

目标总数由工具读取快照，遗漏目标补 0 分；其他检查由 QA 按当前规范列全。每项已验证通过记 100，其余记 0，工具负责汇总，不将检查平均分当成验收结论。

初验保存在本次报告目录的 `qa-score.json`，复验保存独立的 `qa-score-retest-*.json`；不会以修好后的满分覆盖初次成绩。分数、验收结论及现场复验事项分开记录；工具不操作运行状态或决定下一次检查内容。

```bash
# results.json 为 QA 的业务检查结果，可用 - 从标准输入读取
python3 .codex/common/scripts/keel-qa-score.py record results.json --plan /path/to/run/plan.md --output-dir /path/to/run
# Fix 使用 --fix /path/to/bugs/BUG-001/bug.md；复验增加 --retest
python3 .codex/common/scripts/keel-qa-score.py history /path/to/project --last 10
python3 .codex/common/scripts/keel-qa-score.py history /path/to/project --include-retests --json
```

评分 JSON 只有 `goals` 和 `checks` 两组，每项为名称与分数，不包含逐项理由、证据、日志、来源摘要或其他元数据。`goals` 使用计划中的 feature slug，Fix 使用 `bug`；`checks` 使用本次检查项名称，例如：

```json
{
  "goals": {"cancel-order": 100, "confirm-refund": 0},
  "checks": {"关键分支测试": 100, "异常处理": 0}
}
```

APPROVED/REJECTED 由 QA 返回；通过时可省略 `qa-feedback.md`，必要遗留项在返回消息中说明，未通过时报告简述阻断项、原因与影响。Dev/Fix 依据当前 QA 结论推进，评分 JSON 独立保存，复验使用本次复验文件。评分不代替验收结论。历史工具兼容旧评分，简版记录从路径和文件时间识别项目、Dev/Fix 与初验/复验；简版不记录 Builder 身份，旧记录仍可按 Builder 筛选。检查内容可以随 Spec 增删，工具不内置质量检查种类或通过阈值。

### Skill 与 Agent 协议

Plan、Dev、Fix 给 Agent 的业务输入只有两段：

- **任务**：本步目标、范围与授权、必要资料引用（含项目手册）和交付要求。
- **Spec**：产物规范的 name 与绝对路径列表；`#二级标题` 引用包含子节，到下一二级标题结束。

调用层加载注册角色配置并提供项目环境，工具支持时使用独立上下文、关闭完整历史继承。Agent 依据任务与 Spec 完成本职产出；实现中的 Builder 只需简短通知完成，不要求汇总实际改动、验证结果、commits、遗留项或流程影响，遇到阻碍或设计冲突时说明。DocWriter 按需直接维护流程文档，不要求固定结论或报告。QA 仍返回 APPROVED/REJECTED、当次评分路径及必要遗留项，未通过时保留简短报告。

主会话选择 Agent/Spec，负责沟通、调度与交付，从 Git 获取本轮 commits；依据当前结果继续工作，汇报产物与提交。各 Agent 对本职产出负责，代码交付由 QA 独立验收。Agent 仅接收任务与 Spec。

运行阶段登记、确认留档、固定返修/恢复次数、超时计时和历史状态兼容已移除。Plan 按反馈修订方案；Dev/Fix 按 QA 阻断项返修后再验收，遇到实际阻碍时说明原因。

## 使用

1. 在 Codex App 运行 `/keel-plan`，生成 `.keel/plans/<name>.md` 功能索引、`<name>.features/<slug>.md` 功能文档、`<name>.review.md` 审阅素材及同名 `.html` 用户审阅入口。
2. 已确认计划统一运行 `/keel-dev <plan-path>`，由编排决定实现切片与 DocWriter 调用。
3. 新提交的 BUG 直接运行 `/keel-fix <问题描述或资料路径>`；定位阶段不要求预先生成 Plan。

```text
/keel-dev <plan-path>
```

`keel-fix` 编排 Builder 根据问题、代码、配置与日志定位根因，本地复现是可选定位方法。Builder 必须区分已定位、候选原因与暂未定位；主会话按定位需要请求现有资料或现场验证，不能把日志语句当作本次运行记录，也不能靠猜测修改代码。

定位后由主会话分流：明确、局部且不改变既定设计的缺陷走独立 fix；需求变更或涉及业务状态/流程、接口、数据模型、迁移及高风险设计的修复，说明原因并提示用户走 `/keel-plan`。尚未定位时继续调查，不误判为需求。fix 只编排 Builder 和 QA，不调用 Plan/Dev Skill 或 DocWriter。

`.keel/bugs/<id>/bug.md` 与同名 HTML 仅简述“问题、原因、改造点、影响点、建议验证点”五章，影响和建议回归按业务流程表达。预期依据、分流结论与设计边界保留在同目录 `investigation.md` 的“修复资格”章节，其他章节记录调查进展；HTML 不展示调查代码或重复的完整源文档，保留 Markdown 下载。

修复说明由脚本验证并渲染，用户明确确认后由 Builder/QA 直接读取 bug.md 和 investigation.md，产物保存在 BUG run 目录。不另存批准或运行记录；旧三章说明继续兼容，代码验收通过后仍待原场景复验。

```bash
python3 .agents/skills/keel-fix/scripts/keel-fix.py render .keel/bugs/<id>/bug.md
# 用户明确确认当前 HTML 后，主会话调度修复与验收。
```

Codex App 的 Plan 编排 Planner 核对相关 DocWriter 和实际代码，返回带 slug 的候选功能与调研结果，再由主会话让用户选择哪些功能生成 PlantUML 时序图（部分、全部或不生成）；已有明确选择时不重复询问。其余只询问必须由用户决定、且无法从需求、代码或项目惯例确定的事项，内容可推导时直接起草，不逐章确认。

Planner 按本期变化设计方案：时序图表达关键交互、业务分支和原子操作，必要实现约束在功能 MD 中用少量文字保留；模型、图与说明、接口共同支撑完整设计。确实无模型/接口变更时在 MD 写“本期不涉及变更，沿用现有实现”，HTML 继续省略对应可选栏目。仅增加内部状态的完整小方案见 `keel-plan/skills/keel-plan/assets/incremental-example.md` 及关联文件。合约开发的完整示例见 `keel-plan/skills/keel-plan/assets/contract-example.md` 及关联文件。主会话收到 Planner 源文档后直接渲染并交用户审阅；脚本校验失败时按错误安排修订。

执行文档按功能拆分。轻量索引保留各功能目标、逐项验收、依赖及文件链接；目标只说明技术上要达到的功能效果，不包含实现过程。每份功能 MD 保留数据模型、功能时序图、接口设计、代码改造点四章；涉及智能合约开发时，在数据模型之前增加合约设计，先列合约、简要说明及本期变化，再用 PlantUML 展示关系和实例基数（1:1、1:N、N:M，按需细化零或多个）。模型写实际表/列或 JSON 结构差异，SQL 按迁移需要提供；时序图写关键交互，必要实现约束留在该章节图外文字，接口设计写 HTTP/RPC 请求/响应契约，改造点按共用规范列实际类、模块或文件与一句话改动。共享合约设计、模型或接口由一个功能定义，其他功能引用其对应章节，SQL 不重复执行。全部计划 MD 与 HTML 不包含开发自测内容，不列测试文件、用例、命令、操作步骤、验证安排或记录；验收标准仅保留可观察的功能结果，Builder 与 QA 按开发规范自行组织测试。Builder 读索引后仅加载当前功能和必要引用章节；QA 按功能逐份验收。

HTML 按背景、功能目标、业务流程总览、按需状态机、按需合约设计、按需数据模型设计、选定时序图、按需 HTTP/RPC 接口设计、代码改造点展示。背景仅展示理解后的 User Story 列表，不按功能分类；功能目标单独展示技术上需要达到的效果，验收标准逐条列出，不混入 HTTP 契约或事务等实现细节。业务流程总览按共用粒度有变化时必需，无变化可省略；审阅素材标题下记录业务流程变化判定和依据，渲染器拒绝有变化却缺总览的文档。总览参考流程索引并核对现状，以 PlantUML 展示本次方案完成后的目标业务阶段、关键分支和结果，标明新增/修改并简述沿用部分；全新业务也要画出目标流程，不能只展示当前缺少能力。判定字段不另展示为 HTML 栏目。流程图和状态图前只标业务流程或实体名称，如“订单取消流程”“订单状态机”，不另加图表复述、图例解说或设计历史。新增实际表/列时展示 ER 图，JSON 结构调整展示精简字段差异；仅索引、既有字段或数据回填的 SQL 仍保留在执行 MD。时序图栏目只展示功能标题和已选图，不附图外实现文字。接口设计按 HTTP 方法与路径或 RPC 签名组织，不包含功能编号和功能名称。有状态调整时用绿/蓝/红区分新增/修改/删除，删除节点隔离展示。不增加技术约束、实施顺序、验证方案或“其他必要说明”章节。

HTML 从索引、功能文档和审阅素材共同生成，目标、验收、合约设计、模型、时序图、接口及改造点直接复用执行文档；审阅素材只补充 User Stories、本次目标业务流程和状态图。下载文档包包含索引和全部功能 MD，保留相对链接，不重新合并成大 MD。用户反馈修改对应源文件后重新生成 HTML；未选画图的功能仍可保留文字执行说明。Dev 初始化将索引与关联文档一起快照到 run，后续按需读取该快照。最终 HTML 未确认或渲染失败时不能进入 Dev。

渲染依赖 Python 3 和本地 `plantuml` 命令，或通过 `KEEL_PLANTUML_JAR` 指定本地 jar 并提供 Java。图表使用 PlantUML 内置布局，无需 Graphviz；渲染后嵌入 HTML，可离线打开，不向远程服务发送计划。页面默认深色，可在顶部切换浅色，并在浏览器存储可用时记住选择；打印使用浅色。缺少审阅素材、依赖或图语法错误会明确失败并保留旧 HTML。命令行为参考 [PlantUML CLI](https://plantuml.com/command-line)。

```bash
bash .agents/skills/keel-plan/scripts/render-plan-html.sh .keel/plans/example.md .keel/plans/example.html
```

开发只保留 `/keel-dev` 一个入口。小任务一次实现并创建聚焦提交，大任务按依赖分片；两者使用相同的 Builder、QA 和质量规范。QA 通过后按实际改动决定是否需要 DocWriter，不按任务大小或是否展示业务总览直接跳过。

```text
/keel-dev <plan-path>
```

Codex App 的 dev run 在 Preflight 后直接由 Builder 按 Markdown 计划构建，再由 QA 验收，最后按需维护 DocWriter。局部调整与复杂业务流程、数据库迁移、权限、事务/并发、跨模块状态流转都由此入口执行。Codex App 不再生成或审查 build-scope；方案和边界必须在 Plan 阶段完成确认。


DocWriter 按需调度：主会话依据本轮全部实现与返修范围判断流程影响，明确没有外部入口、异步推进点、业务状态节点、流转条件或业务入口符号变化时直接交付，存在变化或不确定时调度独立 DocWriter。DocWriter 按需直接更新 `.keel/call-chain/` 文档；是否更新的结论不另写文档，也不要求 NOOP/UPDATED 或汇总报告。历史 diff 受控评测结果可用 `scripts/check-call-chain-controlled-eval.sh` 汇总，不代表本次流程已通过模型评测。

DocWriter 文档以用户或客户的业务目标命名，如 `user-order.md`（用户下单），只保留主流程说明、状态机和业务入口。主流程用简短编号步骤，状态用文本箭头并标注对应步骤；入口列 HTTP、RPC、MQ、定时任务或回调的实际业务处理位置，例如业务 Job，而非框架配置或通用调度器。不展开 PlantUML、详细流转表、状态写入位置、参数、SQL、日志或测试记录。内容以验收后的实现为准，需要维护时直接更新文档，仅任务明确要求时提交。默认输入的 [流程文档 Spec](common/refs/keel-flow-index-spec.md) 内嵌完整写法示例，随 runtime 部署供后续 DocWriter 使用；维护受影响旧文档时也整体收敛为这三部分。[用户下单业务流程](keel-test/.keel/call-chain/user-order.md) 是现有项目示例。

QA 发现阻断问题时安排返修并再次验收。

run 目录最小结构:

```text
.keel/iterations/<branch>/run-N/
  plan.md                    # 功能目标与文档索引
  <name>.features/            # 各功能的设计 MD
  qa-feedback.md             # REJECTED 时必需，APPROVED 时可省略
  qa-score.json              # 本次初验评分
  qa-score-retest-*.json      # 复验评分，与初验分开
  fix-brief.md
```

旧 `keel-dev-fast` 已合并；重新部署会按 manifest 清理其旧 Skill 和已移除的运行助手，不删除未被跟踪的用户文件。

新 run 只保存计划快照与任务产物；初始化返回快照 `plan.md`，主会话通过原生消息跟进当前 Agent。不支持旧格式（包括单份大 MD）的计划，不自动拼接历史输入。

## 开发与验证

常用验证命令:

```bash
bash -n bin/keel
find common -type f -name '*.sh' -exec bash -n {} \;
bash -n keel-plan/skills/keel-plan/scripts/render-plan-html.sh
scripts/check-runtime-contract.sh
scripts/check-planning-contract.sh
# check-runtime-contract 已包含 ASO 边界、部署和运行协议验证
python3 scripts/test-qa-score.py
scripts/keel-metrics.sh
scripts/check-slimming-targets.sh
scripts/check-call-chain-controlled-eval.sh
tmp=$(mktemp -d)
bin/keel dev --codex "$tmp"
find "$tmp/.agents/skills" "$tmp/.codex" -maxdepth 4 -type f | sort
rm -rf "$tmp"
git status --short
```

对 `bin/keel` 做端到端测试时,目标目录必须用 `mktemp -d` 创建,测试结束后清理,避免污染真实项目。

库存预占服务的试验产物保存在 [keel-test](keel-test/README.md)。审阅入口：

- [Plan HTML](keel-test/.keel/plans/inventory-reservations.html)：一个生命周期总览与三个精简时序图。
- [Fix HTML](keel-test/.keel/bugs/BUG-001/bug.html)：问题、原因、改造点、影响点和建议验证点五段说明。
- [QA 摘要示例](keel-test/.keel/eval/concise-output-example/qa-feedback.md)：按三个功能目标汇报，详细证据使用引用。
- [测试报告](keel-test/TEST_REPORT.md)：原始评估结果、首稿问题和后续表达修订。

最新 Plan 展示稿和 QA 摘要为手工精简示例，尚未重跑新规范下的 Agent 首稿评估；原始快照、评分和日志保留。表达修订的 95 项契约验证及精简门槛已通过，真实用户对 HTML 的审阅仍待确认。再次执行完整试验仍使用临时项目。

输入体量按 Agent 实际加载的角色配置和场景 Spec 统计；动态任务、项目资料和真实模型用量由行为评估记录，见 [评估说明](evals/keel/README.md)。

## 部署行为

- Codex skills 部署到 `.agents/skills/`
- Codex agents 部署到 `.codex/agents/`
- Codex common 部署到 `.codex/common/`
- Codex manifest 写入 `.codex/.keel/installed-manifest`
- 同名文件直接覆盖
- 只删除当前 runtime 上次由 manifest 记录、但本次源里已不存在的旧文件

## 安全

- Keel 不会自动 merge、squash、push 或清理 Builder commits。
- Deployment 会覆盖目标项目中的同名 Keel 文件。
