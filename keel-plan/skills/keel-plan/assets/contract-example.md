# 项目合约与专属资金托管

## 功能目标

### create-project — 创建项目与托管

- 文档：[create-project](contract-example.features/create-project.md)
- 依赖：无
- 目标：创建具有独立身份与专属资金托管能力的项目。

验收标准：

- 创建成功后，项目可被查询且拥有唯一的专属托管实例。
- 创建失败不留下可用的半初始化项目。

### configure-rules — 配置参与资格规则

- 文档：[configure-rules](contract-example.features/configure-rules.md)
- 依赖：create-project
- 目标：允许项目管理者配置可复用的参与资格规则。

验收标准：

- 项目管理者可替换本项目的规则集合，无权操作的请求被拒绝。
- 同一规则可供多个项目使用，各项目的规则配置互不影响。
- 参与者须满足全部已配置规则；空规则集合不附加资格限制。
