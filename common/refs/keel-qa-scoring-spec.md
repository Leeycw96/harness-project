---
name: keel-qa-scoring-spec
description: 规定验收评分与 JSON 记录，用于近期成绩分析。
---

# QA 评分规范（S）

## 评分记录

- 记录对应当前 Spec 的检查结果，应检未检为 unverified，不漏报或补满分。
- 目标结果 goal_results 的 id 为快照中的 feature slug，全部验收条件通过才算完成。目标分=完成数÷确认总数×100，失败、遗漏、未验证不算完成。Fix 用 bug 单目标，现场缺口列入 limitations。
- checks 包含当前规范适用的其他组及条目，分数=通过数÷条目数×100。空组不评分；未验收目标时 goal_results 及目标分为空，不推算分数。
- JSON 须有 schema_version: 1、review（initial/retest）、verdict（APPROVED/REJECTED）和 blockers 文本列表；builder、commits、limitations 按任务记录，未知 builder 为 unknown。
- goal_results 条目用 id；checks 组有 name、items，条目用 name。各条含 status（passed/failed/unverified）和 evidence；未验证写 reason，其他状态须可定位证据。
- 最终 JSON 符合 `.codex/common/scripts/keel-qa-score.py` 的读取格式，含记录时间、目标来源及摘要、goal_score、check_scores 和内容摘要 data_sha256；分数与明细一致，目标总数来自确认快照，遗漏仍计入总数。
- 初验记录为 qa-score.json，复验为独立的 qa-score-retest-*.json，初次成绩不被复验覆盖。分数与验收结论分别保留。
