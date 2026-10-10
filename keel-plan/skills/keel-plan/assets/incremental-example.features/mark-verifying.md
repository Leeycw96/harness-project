# mark-verifying — 标记校验阶段

## 数据模型

- 结构变更：无

本期不涉及数据模型变更，沿用现有实现。

示例中的 export_tasks.phase 为无数据库枚举或 CHECK 约束的字符串字段，VERIFYING 仅新增业务值，无 SQL 调整；实际项目必须核对字段约束，不能照搬此结论。

## 功能时序图

- 时序图：生成

```plantuml
@startuml
participant "ExportJob.run" as Job
participant "ExportService.execute" as Service
participant "FileValidator.check" as Validator
database 导出任务库 as DB
participant "TimeoutScanner.scan" as Timer
par 校验路径
group 沿用领取与文件生成（ExportJob.run）
Job -> Service : 领取任务并生成文件（沿用）
end
Service -> DB : [新增] 条件更新 RUNNING → VERIFYING
note over Service,DB
沿用原独立状态更新事务与并发保护
未命中条件时按原规则退出
文件生成与校验不纳入该事务
end note
opt 条件更新命中
Service -> Validator : 校验文件
alt 校验成功
Service -> DB : [修改] VERIFYING → COMPLETED（条件更新）
else 校验失败
Service -> DB : [修改] VERIFYING → FAILED（条件更新）
end
end
else 独立超时扫描
Timer -> DB : 扫描超时的运行中任务
note over Timer,DB
[修改] 扫描范围由 RUNNING 扩为 RUNNING、VERIFYING
end note
Timer -> DB : 按原并发条件更新为 FAILED（覆盖 VERIFYING）
end
@enduml
```

## 接口设计

本期不涉及接口变更，沿用现有实现。

## 代码改造点

- `src/ExportPhase.java`：增加内部校验中状态值。
- `src/ExportService.java`：在既有校验前记录校验中状态，并调整完成条件。
- `src/TimeoutScanner.java`：把校验中状态纳入原运行中超时处理范围。
