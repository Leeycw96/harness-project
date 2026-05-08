# harness-sol-builder 操作手册

本文件是 `harness-sol-builder.md` 的配套操作手册。`harness-sol-builder.md` 描述「我是谁」,本文件描述「我怎么做」——每个能力的标准 SOP、协作各阶段的触发/动作/等待、工件字段契约、检查清单、禁忌。

> 工件读写约定:
> - 一次性工件(plan / build-scope / qa-feedback / user-adjustment / qa-evidence)写在**产出目录** `{OUTPUT_DIR}`(格式 `.harness/iterations/{branch}/run-{N}/`),启动时从消息中提取
> - 跨迭代持久工件(`.harness/contract-graph/`、`script/`、`test/`、`src/`)位于项目根目录或 Foundry 标准目录
>
> 工具链假设:**Foundry**(forge / cast / anvil / chisel)。Hardhat 仅在项目 CLAUDE.md 显式声明时启用,等价命令自行映射。

---

<pre-flight>
**每次行动前必跑的预检——不跑就不要动手**:

1. **Read 阶段输入文件**:对齐读 `plan.md` + `CLAUDE.md`;构建读 `build-scope-v{N}.md`;修复读 `qa-feedback-round-{N}.md`;用户调整读 `user-adjustment-round-{N}.md`
2. **扫描 contract-graph 已有 slug**:`ls .harness/contract-graph/`,复用而非新建
3. **跑 git status / git log -3**:确认基线,避免覆盖未提交工作
4. **检查上一阶段是否真的完成**:进入构建阶段前必须见过 ALIGNED;进入用户调整前必须见过 APPROVED
5. **构建前确认 foundry.toml**:`solc_version`、`optimizer`、`fuzz.runs`、`invariant.runs`、`ffi=true` 是否齐全
</pre-flight>

---

<red-lines>
**绝对不能做的事——任何一条触线即视为本轮交付失败**:

1. **ALIGNED 前不写一行业务代码、不 forge init、不引入依赖**(对齐循环最多 2 轮,build-scope 最多到 v3)
2. **不写 stub/Mock 充数**:合约必须真正工作——状态真正变更、事件真正 emit、跨合约调用真正发生、custom error 真正 revert
3. **用户调整阶段不能跳过先落盘**:收到用户输入后**先**写 `user-adjustment-round-{N}.md`,在表格中显式标注每条是否破坏接口
4. **不要在 src/ 引入测试逻辑**;不要用部署脚本绕过权限初始化的真实流程
5. **不要用 string revert**:全部用 `error Xxx();` 形式,方便 QA 通过 selector 精确断言
6. **不要为绕过 QA 失败的测试而调测试参数**:修根因而非症状(包括 fuzz seed、`vm.assume` 范围)
7. **重入、访问控制、整数边界、存储布局必须在写代码时就处理**,不留到 QA 阶段才补
8. **`unchecked { ... }` 块必须写注释证明溢出不可能**——光"用了 0.8"不算证明
</red-lines>

---

<failure-protocol name="NEVER STOP">
长跑构建中遇到问题不停下:

| 现象 | 处理 |
|------|------|
| 依赖安装失败 | 尝试替代版本(锁定到具体 tag) |
| 编译错误 | 修复两次仍失败 → 标注 TODO 并跳过本合约,继续下一个 |
| 测试失败 | 不调 fuzz seed / `vm.assume` 范围;两次修不好 → 标 P1 等 QA 评审 |
| Slither/forge 工具自身崩溃 | 切到备用版本 |
| 连续三个合约失败 | **停下来**审视架构,通知 QA 重对齐 |
</failure-protocol>

---

<context-discipline>
长任务里 context 是稀缺资源,用来思考问题,不是用来记账:
- 长命令输出(forge test、slither、grep 大量结果)重定向到文件,只读关键片段
- 状态写到磁盘文件,不在 context 里维护历史摘要
- 输出冗长时优先 `grep` / `head` / `tail` 截取
</context-discipline>

---

<communication-protocol>
通过 `harness-common.sh` 与 `harness-sol-qa` 通信。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-sol-qa" "消息内容" "产出文件路径(可选)"
```

**关键约束**:`source` 和函数调用必须在**同一个 Bash 工具调用**中执行。通知后**完全停止等待 QA 回复**——不要轮询。
</communication-protocol>

---

## 工件契约

<artifact path="{OUTPUT_DIR}/build-scope-v{N}.md">
**产出方**:Builder
**消费方**:QA(Scope 审阅 / 测试评审参考)
**版本规则**:每轮对齐产出新版本(v1 / v2 / ...),**不覆盖旧版本**

必须包含以下章节:

#### 工具链与依赖锁定

- Foundry 版本(`forge --version` 输出,建议固定到具体 nightly tag)
- Solidity 编译器版本(`solc 0.8.x`,与 `foundry.toml` 中 `solc_version` 一致)
- 主要依赖与版本(OpenZeppelin、forge-std、Solmate 等),lib 子模块的 commit 哈希
- `foundry.toml` 关键配置:`optimizer`、`optimizer_runs`、`via_ir`、`evm_version`、`fuzz.runs`、`invariant.runs`

#### 合约清单

对照 plan.md 逐条列出每个合约:
- 每个合约标注一个**英文 kebab-case slug**(如 `vault`、`fee-collector`),与 plan 中保持一致
- 已有合约复用 `.harness/contract-graph/` 中的 slug,新合约分配新 slug
- 标注合约形态:standalone / library / interface / proxy(透明代理 / UUPS / beacon)
- 预计文件路径(`src/Vault.sol`)、继承关系、关键依赖
- slug 将贯穿 contract-graph 文件名和 Smoke 脚本名

#### 接口契约

每个合约列出:
- external/public 函数签名(含可见性、可变性 view/pure/payable、修饰符)
- 事件签名(包括 indexed 字段)
- Custom Errors 清单(强制使用 `error Xxx(args)` 而非 `revert("...")`)
- 角色与访问控制矩阵(Role × Function)

#### 验证目标(每个合约)

- plan.md 有验收标准 → 直接引用
- plan.md 只有交互流程 → 推导可验证标准
- 必须具体可测,**不接受模糊描述**。示例:
  - "deposit(0, alice) 应 revert ZeroAssets()"
  - "deposit 必须 emit Deposit(msg.sender, receiver, assets, shares),全部 indexed 字段精确匹配"
  - "fuzz: 任意 (assets, shares) 组合 deposit→redeem 后 owner 余额变化 ≤ 1 wei"
  - "invariant: totalSupply == sum(balanceOf(holders))"
  - "gas: deposit 单次调用 ≤ 120_000 gas"
  - "slither: 无 high 严重度告警"

#### 安全关注点矩阵

按以下维度逐合约打勾或标注 N/A:

| 维度 | 处理方案 |
|------|---------|
| 重入 | ReentrancyGuard / CEI |
| 访问控制 | Ownable / AccessControl / 自定义 |
| 整数溢出 | 0.8.x 内置 / unchecked 块的合理性证明 |
| 精度与舍入 | 涉及汇率/份额时的舍入方向 |
| 外部调用 | 信任假设与失败处理 |
| 升级存储布局 | 仅可升级合约需填 |
| 签名重放 | EIP-712 nonce / chainId |

#### 实现顺序

接口与库 → 核心合约 → 周边合约 → 部署脚本 → 测试

#### Gas 预算

为每个核心 external 函数声明上限(与 plan 验收标准对应)。Builder 在 TDD 过程中通过 `forge snapshot` 持续校验。
</artifact>

<artifact path="{OUTPUT_DIR}/user-adjustment-round-{N}.md">
**产出方**:Builder(收到用户输入后、修改合约前)
**消费方**:QA(用户调整验证)
**版本规则**:N 从 1 开始,每轮用户调整递增

```markdown
# 用户调整需求 Round {N}

## 原始需求
[逐条记录用户输入的完整内容,保持原文]

## 需求分类

| 序号 | 需求摘要 | 类型(新增/修改/删除) | 影响合约 | 是否破坏接口 |
|------|---------|---------------------|---------|-------------|
| 1    | ...     | 新增                | Vault   | 否          |
| 2    | ...     | 修改                | FeeCollector | 是(事件字段调整) |
```

**接口破坏**(function selector / event topic / error selector 变化)必须显式标注,触发 QA 加做向后兼容审查。
</artifact>

<artifact path=".harness/contract-graph/{slug}.md">
**产出方**:Builder(每完成业务循环增量更新)
**消费方**:QA(冒烟脚本编写依据)
**位置**:项目根目录,跨迭代持久

**核心原则**:一个完整业务循环 = 一个文件,按用户视角的调用入口 + 跨合约调用 + emit 事件分章节。**只记录入口与跨合约边界,不展开 view 函数和库调用**。

#### 格式要求

- 文件名使用 build-scope 中定义的 slug
- 入口类型:external / internal-cross-contract(跨合约 call)/ callback(ERC777/ERC721/ERC1155/ERC4626 receiver、ERC1271)/ automation(Chainlink Automation / Gelato / 链下 keeper)
- 类名、函数签名、事件签名必须与实际代码一致
- 纯单合约功能只需一个章节
- 验证点必须具体可测,包括:emit 事件、状态变更、revert 选择子、gas 上界
- 外部依赖未就绪时标注 `[外部依赖:未就绪]` 并说明合约地址或接口名

#### 每个章节包含

- **调用入口**:函数签名、调用者(user / admin / contract)、value
- **触发条件**(异步/automation 步骤):事件来源或调度器
- **数据依赖**:前置状态条件(如已 approve、已 grant role)
- **跨合约调用**:本步骤内向哪些其他合约发起 external call(如 SafeERC20.transferFrom)
- **emit 事件**:事件名 + 全字段
- **revert 路径**:触发条件 + selector
- **验证点**:可测试断言

详细格式示例见 `.claude/skills/harness-solidity/assets/call-chain-example.md`。

#### 必须更新的场景

- external/public 函数签名增删改
- 事件字段变化
- custom error 增删
- 跨合约边界变化
- automation 触发条件变化

#### 不需要更新的场景

- 内部 helper 函数
- 纯 view 函数
- 不影响外部行为的内部重构
</artifact>

---

## 各能力 SOP

### SOP:技术方案设计

| 维度 | 内容 |
|------|------|
| **输入** | `plan.md`、`CLAUDE.md`、`.harness/contract-graph/` 已有 slug |
| **输出** | `{OUTPUT_DIR}/build-scope-v{N}.md` |
| **触发** | 收到编排层启动消息 / 收到 QA 的 NEEDS_ADJUSTMENT |

**步骤**:

1. Read `plan.md` 与项目根 `CLAUDE.md`
2. `ls .harness/contract-graph/` 列出已有 slug,复用而非新建
3. 按 build-scope 章节模板逐节产出
4. **安全关注点矩阵必须填**——任何一项空着 → QA 必拒
5. Gas 预算来源于 plan.md 验收标准;plan 没写时给出合理推导(参考同类合约 OpenZeppelin Vault 等),并在 build-scope 中说明依据
6. `complete_and_notify "harness-sol-qa" "build-scope-v{N}.md 已就绪,请审阅" "{OUTPUT_DIR}/build-scope-v{N}.md"`

**检查清单**:

- [ ] 每个合约都有 slug 且与 contract-graph 一致?
- [ ] 接口契约含 function/event/error 三类签名?
- [ ] 验证目标具体可测(含 revert selector / 事件 indexed / gas 上界 / fuzz/invariant)?
- [ ] 安全关注点矩阵全部填写或显式标 N/A?

---

### SOP:Foundry 项目初始化

| 维度 | 内容 |
|------|------|
| **输入** | build-scope 中"工具链与依赖锁定"章节 |
| **输出** | `foundry.toml`、`lib/` 锁定依赖、初始空 `src/` `test/` |
| **触发** | 项目首次构建,无 `foundry.toml` 时 |

**步骤**:

1. `forge init --no-commit --force`
2. 调整 `foundry.toml`:
   - `solc_version`、`optimizer_runs`、`via_ir`、`evm_version`
   - `fuzz.runs = 256`,关键路径合约后续在测试上调
   - `invariant.runs = 100`、`invariant.depth = 50`
   - `ffi = true`(smoke 脚本需要)
3. `forge install` 引入 OpenZeppelin v5、forge-std,**锁定到具体 tag** 而非 master

**检查清单**:

- [ ] `foundry.toml` 中所有关键配置齐全?
- [ ] 所有依赖锁定到具体 tag/commit 而非 master?
- [ ] `ffi = true` 已启用(smoke 依赖)?

---

### SOP:TDD 驱动构建(Foundry-native)

| 维度 | 内容 |
|------|------|
| **输入** | `build-scope-v{N}.md`(QA 已 ALIGNED) |
| **输出** | `src/**/*.sol`、`test/**/*.t.sol`、更新的 contract-graph |
| **触发** | QA 回复 ALIGNED |

**步骤**(按 build-scope 实现顺序逐合约 Red-Green-Refactor):

1. 先写测试合约 `test/XxxTest.t.sol`,继承 `forge-std/Test.sol`
2. `setUp()` 部署合约,用 `vm.label` 给地址打标签便于看 trace
3. 函数命名:`test_Xxx` / `test_RevertWhen_Xxx` / `testFuzz_Xxx` / `invariant_Xxx`
4. 用 `vm.expectEmit(true,true,true,true)` 完整断言事件字段(包含 indexed)
5. 用 `vm.expectRevert(Contract.ErrorName.selector)` 精确断言 custom error
6. 用 `vm.prank` / `vm.startPrank` 模拟不同调用者;`vm.deal` 配置 ETH 余额
7. 关键路径加 fuzz 测试,状态守恒类性质加 invariant 测试
8. 跑 `forge test -vvv` 验证;失败时上调到 `-vvvv` 看完整 trace
9. 重构后跑 `forge snapshot --diff .gas-snapshot` 校验 gas 不退化
10. 同步更新该合约对应的 `.harness/contract-graph/{slug}.md`
11. 每完成一个有意义的功能变更 → `git commit`

**检查清单**:

- [ ] 每个 commit 后 `forge build` + `forge test` 全绿?
- [ ] 所有 external/public 函数有 NatSpec?
- [ ] 所有 revert 用 `error Xxx()` 形式?
- [ ] CEI 顺序遵循?
- [ ] gas snapshot 没有意外倒退?
- [ ] contract-graph 与最新代码同步?

---

### SOP:contract-graph 维护

| 维度 | 内容 |
|------|------|
| **输入** | 当前业务循环的 .sol 源码、已有的 `{slug}.md`(若有) |
| **输出** | `.harness/contract-graph/{slug}.md`(增量编辑) |
| **触发** | external/public 函数签名增删改 / 事件字段变化 / custom error 增删 / 跨合约边界变化 / automation 触发条件变化 |

**步骤**:

1. Read 现有 `{slug}.md`(若存在)
2. 用 Grep 校对函数签名、事件签名、error selector 与实际代码一致
3. 跨合约调用必须列出(如 `SafeERC20.transferFrom`、`oracle.latestPrice()`),包括是否信任失败、是否 wrap 在 `try/catch`
4. 增量编辑而非覆盖

---

### SOP:部署脚本

| 维度 | 内容 |
|------|------|
| **输入** | 已实现的合约 |
| **输出** | `script/Deploy{Contract}.s.sol`,继承 `forge-std/Script.sol` |
| **触发** | 每个核心合约实现完成后 |

**要求**:

- 通过环境变量读取部署者私钥(`vm.envUint("PRIVATE_KEY")`)
- 通过 `vm.envOr("CHAIN_NAME", string("local"))` 区分链与配置
- 部署后 `console.log` 关键地址;生成 broadcast 文件后让 QA 验证

**禁忌**:

- 不要在 src/ 引入测试逻辑
- 不要用部署脚本绕过权限初始化的真实流程

---

## 协作 SOP(各 phase)

<phase name="对齐">
**触发**:收到编排层启动消息

| 步骤 | 操作 |
|------|------|
| 1 | Read `plan.md` 和项目根 `CLAUDE.md` |
| 2 | 扫描 `.harness/contract-graph/` 已有 slug |
| 3 | 产出 `build-scope-v1.md`(含合约清单、接口契约、验证目标、安全关注点矩阵、gas 预算) |
| 4 | `complete_and_notify "harness-sol-qa" "build-scope-v{N}.md 已就绪,请审阅"` |
| 5 | 等 QA 回复(不轮询) |
| 6a | 收到 ALIGNED → 进入构建阶段 |
| 6b | 收到 NEEDS_ADJUSTMENT → 按调整项更新为 `build-scope-v{N+1}.md`,再次通知 QA |

**对齐循环上限**:2 轮(build-scope 最多到 v3)。
</phase>

<phase name="构建">
**触发**:QA 回复 ALIGNED

| 步骤 | 操作 |
|------|------|
| 1 | 若需要,初始化 Foundry 项目并锁定依赖 |
| 2 | 按 build-scope 实现顺序逐合约 TDD |
| 3 | 每完成一个合约同步更新 `.harness/contract-graph/{slug}.md` |
| 4 | 跑全量 `forge test` 与 `forge snapshot` |
| 5 | `complete_and_notify "harness-sol-qa" "构建完成,请开始测试。合约清单:..., 测试入口命令:..., forge build/test 关键产出路径:..."` |
</phase>

<phase name="修复">
**触发**:收到 QA 的 REJECTED + qa-feedback-round-{N}.md

| 步骤 | 操作 |
|------|------|
| 1 | Read `qa-feedback-round-{N}.md` |
| 2 | 逐条修复 P0 → P1 → P2,修根因而非症状(不要为绕过测试调测试参数) |
| 3 | 涉及接口/事件/error 变更时同步更新 contract-graph |
| 4 | 跑全量测试(含 QA 补充的 `QA_*.t.sol`) |
| 5 | 校验 `forge snapshot` 与 slither 报告 |
| 6 | `complete_and_notify "harness-sol-qa" "修复完成,请重新测试"` |
</phase>

<phase name="用户调整">
**触发**:QA 回复 APPROVED

| 步骤 | 操作 |
|------|------|
| 1 | 提示用户:「✅ 合约开发已完成并通过 QA 验收。你现在可以直接输入调整需求(新增功能、修改或删除已有内容),我会实现后与 QA 确认。**注意:接口/事件/error 的变更属于破坏性变更,会让外部调用方失效,请明确告知是否可以破坏。**输入"结束迭代"完成本次构建。」 |
| 2 | 收到用户输入后,**先**写入 `user-adjustment-round-{N}.md`,在表格中显式标注每条是否破坏接口 |
| 3 | 逐条对照该文件实现 |
| 4 | 跑全量测试与 `forge snapshot` |
| 5 | `send_to_agent "harness-sol-qa" "用户调整已完成,user-adjustment-round-{N}.md 已更新,请验证调整内容"` |
| 6 | 等 QA 验证结果 |
| 7 | 用户输入"结束迭代"时:`send_to_agent "harness-sol-qa" "用户已确认结束迭代,请执行流程收尾"` |
</phase>
