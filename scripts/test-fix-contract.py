#!/usr/bin/env python3
"""Exercise concise bug reviews, qualification gates and approval compatibility."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / 'keel-dev/skills/keel-fix'
spec = importlib.util.spec_from_file_location('keel_fix', SKILL / 'scripts/keel-fix.py')
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)
EXAMPLE = (SKILL / 'assets/bug-template.md').read_text()
REVISED_EXAMPLE = EXAMPLE + '\n补充回归优惠券叠加后的金额展示。\n'
LEGACY = (ROOT / 'evals/keel/fixtures/keel-fix/legacy-bug.md').read_text()
SECTIONS = ('问题', '原因', '改造点', '影响点', '建议验证点')
INVESTIGATION = '''# BUG-001 调查记录

## 调查进展

已复现折扣金额的小数位问题。

```python
evidence_code_should_stay_private = 10.05 * 0.9
```

## 修复资格

- 预期依据：项目已确认的金额舍入规则。
- 分流依据：只恢复已有金额舍入约定。
- 定位结论：已定位
- 事项分类：缺陷
- 处理路径：fix
- 业务状态调整：无
- 业务流程调整：无
- 接口契约调整：无
- 数据模型或迁移：无
- 高风险设计：无
'''


class FixContractTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='keel-fix-test-')
        self.project = Path(self.work.name).resolve()
        self.bug = self.project / '.keel/bugs/bug-001/bug.md'
        self.bug.parent.mkdir(parents=True)
        self.bug.write_text(EXAMPLE)
        self.investigation = self.bug.with_name('investigation.md')
        self.investigation.write_text(INVESTIGATION)

    def tearDown(self):
        self.work.cleanup()

    def approve(self):
        fix.render(self.bug)
        return fix.approve(self.bug, '确认此修复方案，请按此实施。')

    def assert_concise_review(self, page):
        self.assertEqual(re.findall(r'<h2[^>]*>(.*?)</h2>', page), list(SECTIONS))
        encoded = re.search(r'data:text/markdown;charset=utf-8;base64,([^"\s]+)', page)[1]
        self.assertEqual(base64.b64decode(encoded), self.bug.read_bytes())
        for private in ('预期依据', '定位结论', '事项分类', '处理路径', '分流依据',
                        '调查专用证据标记', 'evidence_code_should_stay_private', *fix.BOUNDARIES):
            self.assertNotIn(private, page)
        self.assertNotIn('<pre', page)
        self.assertNotIn('业务流程总览', page)
        self.assertIn('src/pricing.py', page)
        self.assertIn('折扣', page)

    def test_template_and_review_have_only_five_concise_sections(self):
        self.assertEqual(re.findall(r'^## (.+)$', EXAMPLE, re.M), list(SECTIONS))
        self.assertNotIn('```', EXAMPLE)
        output = fix.render(self.bug)
        page = output.read_text()
        self.assert_concise_review(page)
        self.assertNotIn('keel-fix-review', page)
        self.assertNotIn('application/json', page)
        self.assertFalse(self.bug.with_suffix('.review.json').exists())
        script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
        expected = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-" + expected + "'", page)
        self.assertIn('data-theme="dark"', page)
        self.assertIn('theme-toggle', page)
        self.assertFalse((self.project / '.keel/plans').exists())

    def test_investigation_without_evidence_renders_approves_and_checks(self):
        template = (SKILL / 'assets/investigation-template.md').read_text()
        self.assertNotRegex(template, r'(?m)^- 证据：')
        self.assertNotRegex(self.investigation.read_text(), r'(?m)^- 证据：')
        self.assert_concise_review(fix.render(self.bug).read_text())
        state_path = fix.approve(self.bug, '确认不附证据的修复方案')
        self.assertEqual(fix.check(state_path)['mode'], 'fix')

    def test_untrusted_markdown_is_escaped(self):
        self.bug.write_text(EXAMPLE.replace('折扣金额多保留了一位小数', '<img src=x onerror=alert(1)>') + '\n<script>alert(2)</script>\n')
        page = fix.render(self.bug).read_text()
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('<script>alert(2)', page)
        self.assertIn('&lt;script&gt;alert(2)', page)
        self.assertEqual(page.count('<script>'), 1)

    def test_new_review_rejects_missing_sections_empty_sections_and_code_fences(self):
        without_cause = re.sub(r'(?ms)^## 原因\n.*?(?=^## 改造点)', '## 原因\n\n', EXAMPLE)
        for source in (EXAMPLE.replace('## 影响点', '## 改造点'), without_cause,
                       EXAMPLE + '\n```python\nprint("evidence")\n```\n',
                       EXAMPLE + '\n```python\nunclosed', EXAMPLE + '\nTODO\n'):
            with self.subTest(source=source[-60:]):
                self.bug.write_text(source)
                with self.assertRaises(ValueError):
                    fix.validate(self.bug)

    def test_investigation_qualification_requires_complete_unfenced_fields(self):
        for source in (INVESTIGATION.replace('- 预期依据：', '- 资料：'),
                       INVESTIGATION.replace('- 分流依据：', '- 资料：'),
                       INVESTIGATION.replace('- 高风险设计：无\n', ''),
                       INVESTIGATION.replace('- 事项分类：缺陷', '```text\n- 事项分类：缺陷\n```'),
                       INVESTIGATION.replace('## 修复资格', '## 调查结论'),
                       INVESTIGATION.replace('- 处理路径：fix', '- 处理路径：unknown'),
                       INVESTIGATION.replace('- 高风险设计：无', '- 高风险设计：无\n- 高风险设计：无')):
            with self.subTest(source=source[-60:]):
                self.investigation.write_text(source)
                with self.assertRaises(ValueError):
                    fix.validate(self.bug)
        self.investigation.unlink()
        with self.assertRaises((OSError, ValueError)):
            fix.validate(self.bug)

    def test_only_local_defects_can_be_approved(self):
        changes = [('定位结论：已定位', '定位结论：候选原因'),
                   ('定位结论：已定位', '定位结论：暂未定位'),
                   ('事项分类：缺陷', '事项分类：需求变更'),
                   ('事项分类：缺陷', '事项分类：待判断'),
                   ('处理路径：fix', '处理路径：plan'),
                   ('处理路径：fix', '处理路径：待判断'),
                   ('处理路径：fix', '处理路径：待补证据')]
        changes += [(key + '：无', key + '：' + value)
                    for key in fix.BOUNDARIES for value in ('有', '待确认')]
        for old, new in changes:
            with self.subTest(change=new):
                self.investigation.write_text(INVESTIGATION.replace(old, new))
                fix.render(self.bug)
                with self.assertRaises(ValueError):
                    fix.approve(self.bug, '确认')
                self.assertFalse((self.bug.parent / 'runs').exists())

    def test_approval_does_not_compare_source_or_html_versions(self):
        fix.render(self.bug)
        self.bug.write_text(REVISED_EXAMPLE)
        page = self.bug.with_suffix('.html')
        page.write_text(page.read_text().replace('查看问题、修复方式和业务影响', '已查看问题与影响'))
        state_path = fix.approve(self.bug, '确认')
        self.assertEqual(Path(fix.check(state_path)['fix_path']).read_text(), REVISED_EXAMPLE)
        self.assertEqual(set(fix.check(state_path)['approval']), {'decision', 'confirmed_at'})

    def test_qualification_gate_applies_before_first_approval_only(self):
        fix.render(self.bug)
        self.investigation.write_text(INVESTIGATION.replace('业务流程调整：无', '业务流程调整：待确认'))
        with self.assertRaises(ValueError):
            fix.approve(self.bug, '确认旧方案')
        self.investigation.write_text(INVESTIGATION)
        state_path = self.approve()
        self.investigation.write_text(INVESTIGATION.replace('事项分类：缺陷', '事项分类：需求变更'))
        self.assertEqual(fix.check(state_path)['mode'], 'fix')
        self.assertEqual(fix.approve(self.bug, '再次确认旧方案'), state_path)
        self.assertEqual(len(list((self.bug.parent / 'runs').glob('run-*'))), 1)

    def test_approval_records_execution_inputs_without_document_version_checks(self):
        state_path = self.approve()
        state = fix.check(state_path)
        self.assertEqual(state['mode'], 'fix')
        self.assertEqual(state['project_dir'], str(self.project))
        self.assertNotIn('plan_path', state)
        self.assertNotIn('call_chain', state)
        self.assertEqual(set(state['artifacts']), {'qa_feedback', 'fix_brief'})
        self.assertEqual(state['limits'], {'fix_rounds': 3, 'stage_recoveries': 2})
        self.assertEqual(state['fix_path'], str(self.bug))
        self.assertEqual(state['investigation_path'], str(self.investigation))
        self.assertEqual({path.name for path in state_path.parent.iterdir()}, {'state.json'})
        approval = state['approval']
        self.assertEqual(set(approval), {'decision', 'confirmed_at'})
        self.assertEqual(approval['decision'], '确认此修复方案，请按此实施。')
        self.assertTrue(approval['confirmed_at'])
        self.assertFalse(self.bug.with_suffix('.review.json').exists())
        self.assertFalse((state_path.parent / 'progress.tsv').exists())
        mutations = [(self.bug, REVISED_EXAMPLE.encode()),
                     (self.investigation, b'updated investigation without qualification fields'),
                     (self.bug.with_suffix('.html'), b'tampered approved HTML')]
        for path, replacement in mutations:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(replacement)
                self.assertEqual(fix.check(state_path), state)
                if path == self.bug:
                    self.assertEqual(Path(fix.check(state_path)['fix_path']).read_bytes(), replacement)
                elif path == self.investigation:
                    self.assertEqual(Path(fix.check(state_path)['investigation_path']).read_bytes(), replacement)
                path.write_bytes(original)
        self.bug.with_suffix('.html').unlink()
        self.assertEqual(fix.check(state_path), state)
        self.assertEqual(fix.approve(self.bug, '再次确认'), state_path)
        for input_path in (self.bug, self.investigation):
            with self.subTest(missing=input_path.name):
                original = input_path.read_bytes()
                input_path.unlink()
                with self.assertRaises(ValueError):
                    fix.check(state_path)
                input_path.write_bytes(original)

    def test_optional_historical_evidence_and_progress_do_not_change_qualification_or_reset_run(self):
        fix.render(self.bug)
        original_html = self.bug.with_suffix('.html').read_bytes()
        updated = INVESTIGATION.replace('- 分流依据：', '- 证据：调查专用证据标记，历史字段可保留。\n- 分流依据：') + '\n## 补充调查\n\n补充日志与回归进展。\n'
        self.investigation.write_text(updated)
        state_path = fix.approve(self.bug, '确认此修复方案')
        state = fix.check(state_path)
        state['fix_round'] = 2
        state['phase'] = 'BUG_FIX'
        state_path.write_text(json.dumps(state))
        self.assertEqual(Path(state['investigation_path']).read_bytes(), updated.encode())
        self.investigation.write_text(updated + '\n更多现场日志。\n')
        self.assertEqual(fix.check(state_path)['fix_round'], 2)
        self.assertEqual(fix.approve(self.bug, '再次确认同一方案'), state_path)
        self.assertEqual(fix.check(state_path)['fix_round'], 2)
        self.assertEqual(Path(state['investigation_path']).read_bytes(), self.investigation.read_bytes())
        self.assertEqual(self.bug.with_suffix('.html').read_bytes(), original_html)
        fix.render(self.bug)
        self.assert_concise_review(self.bug.with_suffix('.html').read_text())
        self.assertEqual(self.bug.with_suffix('.html').read_bytes(), original_html)
        self.assertEqual(fix.approve(self.bug, '确认补充调查后的同一方案'), state_path)
        self.assertEqual(fix.check(state_path)['fix_round'], 2)

    def test_document_changes_and_finished_phases_do_not_start_or_reset_runs(self):
        first = self.approve()
        self.bug.write_text(REVISED_EXAMPLE)
        self.investigation.write_text(INVESTIGATION + '\n新增排查记录。\n')
        second = self.approve()
        self.assertEqual(first, second)
        state = fix.check(first)
        self.assertEqual(Path(state['fix_path']).read_text(), REVISED_EXAMPLE)
        self.assertEqual(Path(state['investigation_path']).read_bytes(), self.investigation.read_bytes())
        for phase in ('DONE', 'PAUSED', 'NEEDS_PLAN'):
            with self.subTest(phase=phase):
                state = fix.check(first)
                state.update(phase=phase, fix_round=3)
                first.write_text(json.dumps(state))
                original_state = first.read_bytes()
                self.assertEqual(fix.approve(self.bug, '再次确认同一 BUG'), first)
                self.assertEqual(first.read_bytes(), original_state)
        self.assertEqual(len(list((self.bug.parent / 'runs').glob('run-*'))), 1)

    def test_legacy_without_evidence_still_renders_approves_and_checks(self):
        self.investigation.unlink()
        legacy = re.sub(r'(?m)^- 证据：.*\n', '', LEGACY)
        legacy += '\n```python\nevidence_code_should_stay_private = 1\n```\n'
        self.bug.write_text(legacy)
        self.assertNotRegex(legacy, r'(?m)^- 证据：')
        self.assertTrue(fix.validate(self.bug)['eligible'])
        self.assert_concise_review(fix.render(self.bug).read_text())
        state_path = fix.approve(self.bug, '确认旧格式修复方案')
        state = fix.check(state_path)
        self.assertNotIn('investigation_path', state)
        self.assertNotIn('qualification_sha256', state['approval'])
        self.assertNotIn('investigation_sha256', state['approval'])
        self.assertEqual(Path(state['fix_path']).read_text(), legacy)
        self.assertEqual({path.name for path in state_path.parent.iterdir()}, {'state.json'})

    def test_legacy_invalid_or_ineligible_fields_keep_their_original_gate(self):
        self.investigation.unlink()
        for source in (LEGACY.replace('- 根因：', '- 资料：'),
                       LEGACY.replace('- 预期行为：', '- 资料：'),
                       LEGACY.replace('- 预期依据：', '- 资料：'),
                       LEGACY.replace('- 高风险设计：无\n', ''),
                       LEGACY.replace('- 事项分类：缺陷', '```text\n- 事项分类：缺陷\n```'),
                       LEGACY.replace('- 事项分类：缺陷\n', '').replace('## 修复方案', '## 修复方案\n\n- 事项分类：缺陷'),
                       LEGACY.replace('## 影响与验证', '## 修复方案'),
                       LEGACY.replace('- 根因：', '- 根因：TODO ')):
            with self.subTest(source=source[-60:]):
                self.bug.write_text(source)
                with self.assertRaises(ValueError):
                    fix.validate(self.bug)
        for old, new in [('处理路径：fix', '处理路径：plan'), ('业务状态调整：无', '业务状态调整：有')]:
            with self.subTest(change=new):
                self.bug.write_text(LEGACY.replace(old, new))
                fix.render(self.bug)
                with self.assertRaises(ValueError):
                    fix.approve(self.bug, '确认')

    def test_existing_legacy_approval_remains_usable_without_migration_or_rerender(self):
        self.bug.write_text(LEGACY)
        self.investigation.unlink()
        page = self.bug.with_suffix('.html')
        original_html = b'<html>Previously approved three-section legacy HTML</html>'
        page.write_bytes(original_html)
        review = {'source_sha256': 'ignored old source hash', 'html_sha256': 'ignored old HTML hash',
                  'qualification_sha256': 'ignored old qualification hash', 'investigation_sha256': 'ignored old investigation hash'}
        run = self.bug.parent / 'runs/run-1'
        run.mkdir(parents=True)
        (run / 'approved.md').write_bytes(self.bug.read_bytes())
        state_path = run / 'state.json'
        state = {'mode': 'fix', 'project_dir': str(self.project), 'output_dir': str(run),
                 'bug_path': str(self.bug), 'fix_path': str(run / 'approved.md'),
                 'phase': 'BUG_FIX', 'fix_round': 2,
                 'approval': {**review, 'decision': '确认旧版本方案', 'confirmed_at': '2026-10-01T00:00:00+00:00'}}
        state_path.write_text(json.dumps(state))
        original_state = state_path.read_bytes()
        self.assertEqual(fix.check(state_path)['fix_round'], 2)
        self.assertEqual(fix.check(state_path)['fix_path'], str(self.bug))
        (run / 'approved.md').unlink()
        self.assertEqual(fix.approve(self.bug, '再次确认旧方案'), state_path)
        self.assertEqual(page.read_bytes(), original_html)
        self.assertEqual(state_path.read_bytes(), original_state)
        self.assertFalse((run / 'approved-investigation.md').exists())
        self.assertFalse(self.bug.with_suffix('.review.json').exists())

    def test_existing_run_uses_current_inputs_after_snapshots_change_or_disappear(self):
        state_path = self.approve()
        run = state_path.parent
        snapshot = run / 'approved.md'
        investigation_snapshot = run / 'approved-investigation.md'
        snapshot.write_text('historical bug snapshot')
        investigation_snapshot.write_text('historical investigation snapshot')
        state = json.loads(state_path.read_text())
        state.update(fix_path=str(snapshot), investigation_path=str(investigation_snapshot),
                     phase='BUG_FIX', fix_round=2, retries={'keel-qa': 1})
        state_path.write_text(json.dumps(state))
        original_state = state_path.read_bytes()
        self.bug.write_text(REVISED_EXAMPLE)
        self.investigation.write_text('补充后的调查记录，无需重新确认。\n')
        for remove in (False, True):
            with self.subTest(remove=remove):
                if remove:
                    snapshot.unlink()
                    investigation_snapshot.unlink()
                else:
                    snapshot.write_text('changed historical bug snapshot')
                    investigation_snapshot.write_text('changed historical investigation snapshot')
                current = fix.check(state_path)
                self.assertEqual(current['fix_path'], str(self.bug))
                self.assertEqual(current['investigation_path'], str(self.investigation))
                self.assertEqual(Path(current['fix_path']).read_text(), REVISED_EXAMPLE)
                self.assertEqual(Path(current['investigation_path']).read_text(), self.investigation.read_text())
                self.assertEqual(current['fix_round'], 2)
                self.assertEqual(current['retries'], {'keel-qa': 1})
                self.assertEqual(fix.approve(self.bug, '再次确认'), state_path)
                self.assertEqual(state_path.read_bytes(), original_state)
        for source in (self.bug, self.investigation):
            with self.subTest(missing=source.name):
                original = source.read_bytes()
                source.unlink()
                with self.assertRaises(ValueError):
                    fix.check(state_path)
                source.write_bytes(original)

    def test_check_requires_confirmation_and_original_bug_path(self):
        state_path = self.approve()
        state = json.loads(state_path.read_text())
        invalid = [dict(state, approval={}), dict(state, approval={'decision': '确认'}),
                   dict(state, bug_path=''), dict(state, bug_path='bug.md')]
        for data in invalid:
            with self.subTest(data=data):
                state_path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    fix.check(state_path)

    def test_missing_confirmation_or_render_failure_does_not_approve_or_replace_review(self):
        with self.assertRaises(OSError):
            fix.approve(self.bug, '确认')
        self.assertFalse((self.bug.parent / 'runs').exists())
        page = fix.render(self.bug)
        original = page.read_bytes()
        with self.assertRaises(ValueError):
            fix.approve(self.bug, '  ')
        self.bug.write_text(EXAMPLE + '\n```python\nunclosed')
        with self.assertRaises(ValueError):
            fix.render(self.bug)
        self.assertEqual(page.read_bytes(), original)
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_deployed_cli_and_main_session_record_returns_without_losing_approval(self):
        result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.project / '.agents/skills/keel-fix/scripts/keel-fix.py'
        unrelated = self.project / 'common/scripts/keel-plan.py'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('raise RuntimeError("project code must not shadow deployed helpers")')
        for command, extra in [('render', []), ('approve', ['--decision', '确认当前方案'])]:
            result = subprocess.run([sys.executable, str(script), command, str(self.bug), *extra], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(result.stdout.strip())
        checked = subprocess.run([sys.executable, str(script), 'check', str(state)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout.strip(), str(self.bug))
        self.assertEqual({path.name for path in state.parent.iterdir()}, {'state.json'})
        data = json.loads(state.read_text())
        data.update(fix_round=2, retries={'keel-qa': 2},
                    aso_bindings={'builder': {'agent': 'keel-builder',
                                              'spec_refs': [str(self.project / '.codex/common/refs/keel-implementation-spec.md')]}})
        state.write_text(json.dumps(data))
        before_state = state.read_bytes()
        helper = self.project / '.codex/common/scripts/keel-common.sh'
        # Main-session recording follows approval validation; agents return business results only.
        record = 'set -euo pipefail\npython3 "$3" check "$1" >/dev/null\nexport KEEL_PROFILE="$1"\nsource "$2"\nupdate_progress keel-builder BUG_BUILD "已收到修复结果"\ncomplete_stage keel-builder BUG_BUILD_DONE "已核验修复结果" "$4"'
        args = ['fix-test', str(state), str(helper), str(script), str(self.bug)]
        result = subprocess.run(['bash', '-c', record, *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        log = state.parent / 'progress.tsv'
        self.assertFalse(log.exists())
        self.assertEqual(state.read_bytes(), before_state)
        self.assertEqual(fix.check(state)['fix_round'], 2)
        missing = subprocess.run(['bash', '-c', 'set -euo pipefail\nexport KEEL_PROFILE="$1"\nsource "$2"\ncomplete_stage keel-qa APPROVED "缺少验收报告" "$3"',
                                  'fix-test', str(state), str(helper), str(state.parent / 'missing-feedback.md')], capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(log.exists())
        self.assertEqual(state.read_bytes(), before_state)
        self.bug.write_text(REVISED_EXAMPLE)
        changed = subprocess.run(['bash', '-c', record, *args], capture_output=True, text=True)
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertFalse(log.exists())
        self.assertEqual(state.read_bytes(), before_state)
        self.assertFalse((self.project / '.keel/plans').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
