```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
  ================================================================================
  【Contract-Graph Template】合约业务流程入口清单（Solidity 端到端测试数据源）
  ================================================================================

  用途：
    本文档作为模板，供开发者/AI 参考后，根据实际合约业务生成对应的
    {slug}.md 文件。文件中仅列出触发业务流转的全部入口与跨合约边界，
    不展开 view 函数和库调用。

  生成规则：
    1. 梳理业务全流程，按时间顺序依次排列 step。XML 标签出现的
       先后顺序即为业务流程的执行顺序，不依赖额外的序号属性。
    2. 每个 step 用唯一的 id 标识，供 branch 或外部引用。
    3. 每个 step 标注 entry-type，区分测试脚本可直接触发的类型：
       - "external"     → 用户/EOA 直接发交易触发
       - "cross-contract" → 由其他合约触发（callee）；测试需通过另一个 external 入口间接触达
       - "callback"     → 由协议钩子触发（ERC777/721/1155 receiver、ERC1271、Uniswap V3 mint/swap 回调）
       - "automation"   → 由链下 keeper / Chainlink Automation / Gelato 触发；测试脚本可通过 vm.warp / vm.roll 模拟
    4. 若某一步骤存在分支（如审批通过 vs 拒绝、价格上涨 vs 下跌），使用 <branch> 节点包裹
       不同的 <path>，并在 path 上标注 trigger="触发条件"。branch 通过
       from-step="某个 step 的 id" 来关联前置步骤。
    5. path 内部或末尾可包含 <goto ref="某个 step 的 id">，表达流程跳转
       回先前已出现过的 step（如清算未达条件后回退到健康检查节点）。
    6. 主动触发入口保留 <selector> + <signature>，供 AI 根据源码分析参数与 ABI。
    7. 被动触发（如兜底 fallback、Hook callback）保留 <signature>，但注明"无需测试脚本主动触发"。
    8. 如存在统一调度（如某个 Keeper 合约扫描多个目标），在 <automation-note> 中说明。

  文件名命名规范：
    {合约-业务流程}.md
    示例：vault-deposit-redeem.md / governor-proposal-execute.md

  ================================================================================
-->
<contract-graph version="1.0">

  <overview>
    <flow name="【替换为业务流程名称】" main-contract="【替换为主合约名】">

      <!-- ========================================================== -->
      <!-- step：业务流程中的单个阶段                                   -->
      <!-- 属性说明：                                                   -->
      <!--   id          → 唯一标识，供 branch 或 goto 引用              -->
      <!--   name        → 步骤标识名，英文蛇形命名                      -->
      <!--   entry-type  → 触发类型（external / cross-contract /        -->
      <!--                  callback / automation）                     -->
      <!--   actor       → 调用者角色（user / admin / contract / keeper）-->
      <!-- ========================================================== -->
      <step id="approve" name="approve_token" entry-type="external" actor="user">
        <description>
          【替换】用户对目标合约授权 ERC20 代币
        </description>
        <contract>USDC</contract>
        <signature>approve(address spender, uint256 value) returns (bool)</signature>
        <emits>
          <event>Approval(address indexed owner, address indexed spender, uint256 value)</event>
        </emits>
      </step>

      <step id="deposit" name="deposit" entry-type="external" actor="user">
        <description>
          【替换】用户向 Vault 存入资产，铸造 share
        </description>
        <contract>Vault</contract>
        <signature>deposit(uint256 assets, address receiver) returns (uint256 shares)</signature>
        <preconditions>
          <pre>用户已对 Vault approve 至少 assets</pre>
          <pre>vault.paused() == false</pre>
        </preconditions>
        <cross-contract-calls>
          <call>USDC.transferFrom(msg.sender, address(this), assets)</call>
          <call>internal _mint(receiver, shares)</call>
        </cross-contract-calls>
        <emits>
          <event>Deposit(address indexed sender, address indexed receiver, uint256 assets, uint256 shares)</event>
        </emits>
        <state-changes>
          <change>vault.totalAssets() += assets</change>
          <change>vault.balanceOf(receiver) += shares</change>
          <change>USDC.balanceOf(vault) += assets</change>
        </state-changes>
        <reverts>
          <revert selector="ZeroAssets()" trigger="assets == 0"/>
          <revert selector="EnforcedPause()" trigger="vault.paused() == true"/>
        </reverts>
        <gas-budget>120000</gas-budget>
      </step>

      <step id="accrue" name="accrue_yield" entry-type="automation" actor="keeper">
        <description>
          【替换】定时累计利息；由链下 keeper 周期性触发
        </description>
        <contract>Vault</contract>
        <signature>accrueYield()</signature>
        <trigger>每 1 小时由 Chainlink Automation 触发；测试通过 vm.warp(block.timestamp + 3600) + 直接调用</trigger>
        <emits>
          <event>YieldAccrued(uint256 amount, uint256 newTotalAssets)</event>
        </emits>
        <state-changes>
          <change>vault.totalAssets() 按利率公式增长</change>
        </state-changes>
      </step>

      <step id="redeem" name="redeem" entry-type="external" actor="user">
        <description>
          【替换】用户赎回 share 换回资产
        </description>
        <contract>Vault</contract>
        <signature>redeem(uint256 shares, address receiver, address owner) returns (uint256 assets)</signature>
        <emits>
          <event>Withdraw(address indexed sender, address indexed receiver, address indexed owner, uint256 assets, uint256 shares)</event>
        </emits>
        <reverts>
          <revert selector="ERC20InsufficientAllowance(address,uint256,uint256)" trigger="msg.sender != owner 且未 approve"/>
        </reverts>
      </step>

      <!-- ========================================================== -->
      <!-- branch：分支节点                                             -->
      <!-- 属性说明：                                                   -->
      <!--   from-step  → 触发分支的前置 step 的 id 属性值              -->
      <!--   name       → 分支标识名                                    -->
      <!-- ========================================================== -->
      <branch from-step="redeem" name="health-check">
        <description>
          【替换】赎回后根据剩余抵押率走不同清算路径
        </description>

        <path name="healthy" trigger="collateralRatio() >= MIN_RATIO">
          <step id="redeem-success" name="redeem_success" entry-type="external" actor="user">
            <description>赎回成功，无后续动作</description>
            <contract>Vault</contract>
            <signature>（同 redeem，仅状态变化）</signature>
          </step>
        </path>

        <path name="unhealthy" trigger="collateralRatio() < MIN_RATIO">
          <step id="liquidate" name="liquidate" entry-type="external" actor="liquidator">
            <description>
              第三方清算者发起清算
            </description>
            <contract>Vault</contract>
            <signature>liquidate(address borrower) returns (uint256 seized)</signature>
            <emits>
              <event>Liquidated(address indexed borrower, address indexed liquidator, uint256 seized)</event>
            </emits>
            <reverts>
              <revert selector="HealthyPosition()" trigger="collateralRatio() >= MIN_RATIO"/>
            </reverts>
          </step>
          <goto ref="accrue"/>
        </path>
      </branch>

      <step id="hook-callback" name="erc721_received" entry-type="callback" actor="contract">
        <description>
          【替换】例如：本合约持有 NFT 时实现 IERC721Receiver
          （被动 callback，无需测试脚本主动触发；测试需通过另一个 EOA 调用 ERC721.safeTransferFrom 间接触发）
        </description>
        <contract>Vault</contract>
        <signature>onERC721Received(address operator, address from, uint256 tokenId, bytes calldata data) returns (bytes4)</signature>
      </step>

    </flow>

    <automation-note>
      <description>
        【替换】描述统一 keeper 的触发频率和等待策略，例如：
        以上所有 entry-type="automation" 的节点，均由 Chainlink Automation registry
        定期扫描 Vault.checkUpkeep 触发。默认每 1 小时执行一次。
        端到端测试脚本通过 vm.warp(block.timestamp + 3600) 跳过等待，
        并直接调用对应 keeper 函数模拟触发。
      </description>
      <upkeep-contract>Vault</upkeep-contract>
      <check-function>checkUpkeep(bytes calldata) returns (bool, bytes memory)</check-function>
      <perform-function>performUpkeep(bytes calldata)</perform-function>
    </automation-note>
  </overview>

  <!-- ============================================================ -->
  <!-- 标签速查表（集中说明所有合法 XML 标签的含义和约束）             -->
  <!-- ============================================================ -->
  <tag-reference>

    <tag name="step" desc="业务流程中的单个阶段，按 XML 出现顺序排列">
      <attribute name="id" required="true" desc="唯一标识，供 branch 或 goto 引用"/>
      <attribute name="name" required="true" desc="步骤标识名，英文蛇形命名"/>
      <attribute name="entry-type" required="true" desc="触发类型：external/cross-contract/callback/automation"/>
      <attribute name="actor" required="true" desc="调用者角色：user/admin/contract/keeper"/>
      <child name="description" desc="该步骤的业务行为说明"/>
      <child name="contract" desc="承载该入口的合约名"/>
      <child name="signature" desc="函数签名（含可见性与可变性）"/>
      <child name="preconditions" desc="可选，前置状态条件"/>
      <child name="cross-contract-calls" desc="可选，本步骤内向其他合约发起的 external call"/>
      <child name="emits" desc="该步骤 emit 的事件清单"/>
      <child name="state-changes" desc="该步骤导致的状态变更清单"/>
      <child name="reverts" desc="可能触发的 revert 路径（selector + 触发条件）"/>
      <child name="gas-budget" desc="可选，单次调用 gas 上界（与 build-scope 一致）"/>
      <child name="trigger" desc="automation 类型必填，链下触发策略"/>
    </tag>

    <tag name="branch" desc="分支节点，表达流程因条件不同而走不同路径">
      <attribute name="from-step" required="true" desc="触发分支的前置 step 的 id 属性值"/>
      <attribute name="name" required="true" desc="分支标识名"/>
      <child name="description" desc="分支的判断依据"/>
      <child name="path" required="true" desc="至少包含一条 path，每条 path 代表一个独立分支路径"/>
    </tag>

    <tag name="path" desc="分支路径，被 branch 包裹">
      <attribute name="name" required="true" desc="路径标识名，如 healthy/unhealthy/liquidated"/>
      <attribute name="trigger" required="true" desc="进入该路径的触发条件描述（链上可观测的状态判定）"/>
      <child name="step" desc="路径内部的步骤"/>
      <child name="goto" desc="可选，放在路径末尾用于跳转到先前已出现的 step"/>
    </tag>

    <tag name="goto" desc="流程跳转，通常放在 path 末尾表达回退或循环">
      <attribute name="ref" required="true" desc="目标 step 的 id，必须是 flow 中已出现的 step"/>
    </tag>

    <tag name="revert" desc="可能触发的 revert 路径">
      <attribute name="selector" required="true" desc="Custom Error 的字符串签名，如 ZeroAssets() / InsufficientBalance(uint256,uint256)"/>
      <attribute name="trigger" required="true" desc="触发该 revert 的状态条件"/>
    </tag>

    <tag name="automation-note" desc="统一 keeper 说明，描述驱动多个 automation 节点的链下调度器">
      <child name="description" desc="调度频率、等待策略和测试建议"/>
      <child name="upkeep-contract" desc="实现 checkUpkeep / performUpkeep 的合约名"/>
      <child name="check-function" desc="checkUpkeep 函数签名"/>
      <child name="perform-function" desc="performUpkeep 函数签名"/>
    </tag>

  </tag-reference>

</contract-graph>
```
