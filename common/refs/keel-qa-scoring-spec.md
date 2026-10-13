---
name: keel-qa-scoring-spec
description: 规定验收评分与 JSON 记录，用于近期成绩分析。
---

# QA 评分规范（S）

## 评分记录

- JSON 只有 goals 和 checks 两组键值，值为每项分数，不含状态、解释、运行元数据或内容摘要。
- goals 的键为确认计划中的 feature slug，Fix 按 bug.md 用 bug 单目标；checks 的键为当前 Spec 适用的检查项名称。全部目标和适用检查项都要列出，不漏报或补满分。
- 每项实际验证通过记 100，失败、遗漏或未验证记 0；目标的全部验收条件通过才记 100。提供确认计划或修复说明时，遗漏目标由工具补 0，全部目标仍纳入分母；未提供目标来源且不做目标评分时 goals 为 {}，无适用检查时 checks 为 {}。
- 最终 JSON 符合 `.codex/common/scripts/keel-qa-score.py` 的读取格式；汇总工具计算目标完成数÷确认总数×100，以及检查通过数÷条目数×100，空组不推算分数。
- 初验为 qa-score.json，复验为独立的 qa-score-retest-*.json，不覆盖初次成绩；每次返回当次评分路径。验收结论与未完成原因在消息或报告中说明，不写入评分 JSON。
