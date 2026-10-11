---
name: keel-qa-scoring-spec
description: 规定验收评分与 JSON 记录，用于近期成绩分析。
---

# QA 评分规范（S）

## 评分记录

- 按当前 Spec 记录检查结果，不从历史自行减检。应检未检记 unverified，不漏报或补满分。
- 检查过目标时按快照的 feature slug 记录 goal_results，全部验收条件通过才算完成。目标分=完成数÷确认总数×100，失败、遗漏、未验证不算完成。Fix 用 bug 单目标，现场缺口记 limitations。
- checks 记录其他组及条目，分数=通过数÷条目数×100；随规范增删。空组不评分；未查目标不写 goal_results，不推算分数。
- JSON 须有 schema_version: 1、review（initial/retest）、verdict（APPROVED/REJECTED）和 blockers 文本列表；builder、commits、limitations 按任务记录，未知 builder 为 unknown。
- goal_results 条目用 id；checks 组有 name、items，条目用 name。各条含 status（passed/failed/unverified）和 evidence；未验证写 reason，其他状态须可定位证据。
- 运行 `python3 .codex/common/scripts/keel-qa-score.py record <JSON或-> --plan <快照> --output-dir <报告目录>`；Fix 改用 --fix <批准说明>。只生成报告。
- 初验保存 qa-score.json，同结果沿用，不被新结果覆盖；复验独立保存 qa-score-retest-*.json。分数不替代验收结论。
