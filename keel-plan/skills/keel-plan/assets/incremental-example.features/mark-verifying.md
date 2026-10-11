# mark-verifying — 标记校验阶段

## 数据模型

- 结构变更：无

本期不涉及数据模型变更，沿用现有实现。

示例中的 export_tasks.phase 为无数据库枚举或 CHECK 约束的字符串字段，VERIFYING 仅新增业务值，无 SQL 调整；实际项目必须核对字段约束，不能照搬此结论。

## 功能时序图

- 时序图：生成

```plantuml
@startuml
participant 导出任务 as Job
participant 导出处理 as Service
participant 文件校验 as Validator
database 导出任务库 as DB
participant 超时扫描 as Timer
par 文件校验路径
  Job -> Service : 沿用任务领取与文件生成
  Service -> DB : [新增] 条件更新 RUNNING → VERIFYING
  opt 状态更新成功
    Service -> Validator : 校验文件
    alt 校验成功
      Service -> DB : [修改] VERIFYING → COMPLETED
    else 校验失败
      Service -> DB : [修改] VERIFYING → FAILED
    end
  end
else 独立超时处理
  Timer -> DB : [修改] 将 RUNNING、VERIFYING 中的超时任务标记失败
end
@enduml
```

- 状态更新沿用原独立事务及并发保护，条件未命中时按原规则退出；文件生成与校验不进入该事务。
- 完成、失败和超时处理仍按原条件更新；超时扫描范围新增 `VERIFYING`，其余重试和恢复规则沿用。

## 接口设计

本期不涉及接口变更，沿用现有实现。

## 代码改造点

- `src/ExportPhase.java`：增加内部校验中状态值。
- `src/ExportService.java`：在既有校验前记录校验中状态，并调整完成条件。
- `src/TimeoutScanner.java`：把校验中状态纳入原运行中超时处理范围。
