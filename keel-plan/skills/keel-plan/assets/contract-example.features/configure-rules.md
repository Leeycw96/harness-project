# configure-rules — 配置参与资格规则

## 合约设计

- 引用：[create-project](create-project.md#合约设计)

## 数据模型

- 结构变更：无

本期不涉及数据模型变更，沿用现有实现。

## 功能时序图

- 时序图：不生成

Project.setRules(address[]) 仅允许本项目管理者调用，用提交的合约地址集合替换原规则；拒绝零地址、非合约地址和重复项，接受空集合。参与资格校验逐个调用规则的 isEligible(address)，全部通过才允许继续；返回 false 或调用失败均拒绝本次参与。管理者按需部署 EligibilityRule，部署时写入固定地址白名单；isEligible(address) 返回地址是否在名单中。白名单不可修改，规则不保存各项目的配置或参与者状态；项目分别持有规则集合，复用规则不会修改其他项目的配置。本例不增加 HTTP/RPC 接口。

## 接口设计

本期不涉及接口变更，沿用现有实现。

## 代码改造点

- `contracts/Project.sol`，`setRules` / `isEligible`（新增）：限制规则配置权限并执行全部资格校验。
- `contracts/EligibilityRule.sol`，`constructor` / `isEligible`（新增）：保存固定地址白名单并提供可复用的资格校验。
