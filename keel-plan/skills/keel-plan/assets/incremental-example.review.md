# 导出任务增加校验中状态

- 业务流程变化：无
- 判定依据：示例已存在领取、生成、校验、完成/失败及超时处理；本期仅用 VERIFYING 表达既有校验阶段，业务阶段和路径不变，状态机仍须更新。依据 ExportService.execute、FileValidator.check、TimeoutScanner.scan 核实，实际项目须替换示例事实。

## 背景

- User Story：作为运维人员，我希望区分导出任务正在生成还是校验文件，以便定位处理卡点。

## 状态机

### 导出任务状态机

```plantuml
@startuml
state "生成中" as RUNNING
state "校验中 [新增]" as VERIFYING #DCFCE7
state "已完成" as COMPLETED
state "失败" as FAILED
[*] --> RUNNING
RUNNING -[#green]-> VERIFYING : [新增] 文件生成完成
VERIFYING -[#blue]-> COMPLETED : [修改] 原校验成功
VERIFYING -[#blue]-> FAILED : [修改] 原校验失败或超时
RUNNING --> FAILED : 原生成失败或超时
FAILED --> RUNNING : 原重试
COMPLETED --> [*]
@enduml
```
