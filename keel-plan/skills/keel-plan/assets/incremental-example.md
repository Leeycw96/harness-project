# 导出任务增加校验中状态

## 功能目标

### mark-verifying — 标记校验阶段

- 文档：[mark-verifying](incremental-example.features/mark-verifying.md)
- 依赖：无
- 目标：导出任务执行既有文件校验时进入校验中状态，能区分生成与校验阶段，保持既有成功、失败及对外行为。

验收标准：

- 文件生成后、调用既有校验前，内部状态由 RUNNING 进入 VERIFYING。
- 原校验成功后进入 COMPLETED，失败后进入 FAILED；原校验规则和业务返回保持不变。
- VERIFYING 仍受原超时处理覆盖，不因新增状态留下无法处理的任务。
