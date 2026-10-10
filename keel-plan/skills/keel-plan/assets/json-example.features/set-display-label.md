# set-display-label — 设置显示名称

## 数据模型

- 结构变更：JSON结构调整
- SQL迁移：不需要

存储位置：既有 `profiles.attributes` JSON 列。

| 字段路径 | 类型 | 结构约束与兼容 |
| --- | --- | --- |
| `$.displayLabel`（新增） | string | 可选；缺键表示未设置 |

## 功能时序图

- 时序图：不生成

ProfilePresenter.toView 有 displayLabel 时采用该值，缺键时回退 profiles.name。

## 接口设计

本期不涉及接口变更，沿用现有实现。

## 代码改造点

- `src/ProfilePresenter.ts`：按新增键和缺省兼容规则计算既有显示名称输出。
