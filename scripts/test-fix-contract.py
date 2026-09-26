#!/usr/bin/env python3
"""Exercise independent bug review, approval snapshots and runtime deployment."""
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


class FixContractTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='keel-fix-test-')
        self.project = Path(self.work.name).resolve()
        self.bug = self.project / '.keel/bugs/bug-001/bug.md'
        self.bug.parent.mkdir(parents=True)
        self.bug.write_text(EXAMPLE)

    def tearDown(self):
        self.work.cleanup()

    def approve(self):
        fix.render(self.bug)
        return fix.approve(self.bug, '确认此修复方案，请按此实施。')

    def test_review_contains_three_sections_and_exact_download(self):
        output = fix.render(self.bug)
        page = output.read_text()
        self.assertEqual(re.findall(r'<h2[^>]*>(.*?)</h2>', page), list(fix.SECTIONS))
        encoded = re.search(r'data:text/markdown;charset=utf-8;base64,([^"\s]+)', page)[1]
        self.assertEqual(base64.b64decode(encoded), self.bug.read_bytes())
        self.assertIn('src/pricing.py', page)
        self.assertIn('9.05', page)
        self.assertNotIn('业务流程总览', page)
        script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
        expected = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-" + expected + "'", page)
        self.assertIn('data-theme="dark"', page)
        self.assertIn('theme-toggle', page)
        self.assertFalse((self.project / '.keel/plans').exists())

    def test_untrusted_markdown_is_escaped(self):
        self.bug.write_text(EXAMPLE.replace('折扣金额多保留了一位小数', '<img src=x onerror=alert(1)>') + '\n```html\n<script>alert(2)</script>\n```\n')
        page = fix.render(self.bug).read_text()
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('<script>alert(2)', page)
        self.assertIn('&lt;script&gt;alert(2)', page)
        self.assertEqual(page.count('<script>'), 1)

    def test_incomplete_or_fenced_fields_cannot_satisfy_contract(self):
        for source in (EXAMPLE.replace('- 证据：', '- 资料：'),
                       EXAMPLE.replace('- 事项分类：缺陷', '```text\n- 事项分类：缺陷\n```'),
                       EXAMPLE.replace('## 影响与验证', '## 修复方案'),
                       EXAMPLE.replace('- 根因：', '- 根因：TODO ')):
            with self.subTest(source=source[:30]):
                self.bug.write_text(source)
                with self.assertRaises(ValueError):
                    fix.validate(self.bug)

    def test_only_local_defects_can_be_approved(self):
        changes = [('定位结论：已定位', '定位结论：候选原因'),
                   ('定位结论：已定位', '定位结论：暂未定位'),
                   ('事项分类：缺陷', '事项分类：需求变更'),
                   ('事项分类：缺陷', '事项分类：待判断'),
                   ('处理路径：fix', '处理路径：plan'),
                   ('处理路径：fix', '处理路径：待补证据')]
        changes += [(key + '：无', key + '：value') for key in fix.BOUNDARIES]
        for old, new in changes:
            for value in ('有', '待确认') if 'value' in new else ('',):
                with self.subTest(change=new, value=value):
                    self.bug.write_text(EXAMPLE.replace(old, new.replace('value', value)))
                    fix.render(self.bug)
                    with self.assertRaises(ValueError):
                        fix.approve(self.bug, '确认')
                    self.assertFalse((self.bug.parent / 'runs').exists())

    def test_changed_source_or_html_requires_new_review(self):
        fix.render(self.bug)
        self.bug.write_text(EXAMPLE.replace('9.05', '9.04'))
        with self.assertRaises(ValueError):
            fix.approve(self.bug, '确认')
        fix.render(self.bug)
        self.bug.with_suffix('.html').write_text('edited HTML')
        with self.assertRaises(ValueError):
            fix.approve(self.bug, '确认')
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_approval_creates_fix_state_and_detects_snapshot_or_source_drift(self):
        state_path = self.approve()
        state = fix.check(state_path)
        self.assertEqual(state['mode'], 'fix')
        self.assertEqual(state['project_dir'], str(self.project))
        self.assertNotIn('plan_path', state)
        self.assertNotIn('call_chain', state)
        self.assertEqual(set(state['artifacts']), {'qa_feedback', 'fix_brief'})
        self.assertEqual(state['limits'], {'fix_rounds': 3, 'stage_recoveries': 2})
        snapshot = Path(state['fix_path'])
        self.assertEqual(snapshot.read_text(), EXAMPLE)
        snapshot.write_text('tampered')
        with self.assertRaises(ValueError):
            fix.check(state_path)
        snapshot.write_text(EXAMPLE)
        self.bug.write_text(EXAMPLE.replace('9.05', '9.04'))
        with self.assertRaises(ValueError):
            fix.check(state_path)

    def test_repeated_approval_preserves_repair_count_and_new_version_keeps_old_snapshot(self):
        first = self.approve()
        state = json.loads(first.read_text())
        state['fix_round'] = 2
        state['phase'] = 'BUG_FIX'
        first.write_text(json.dumps(state))
        self.assertEqual(fix.approve(self.bug, '再次确认同一方案'), first)
        self.assertEqual(fix.check(first)['fix_round'], 2)
        self.bug.write_text(EXAMPLE.replace('9.05', '9.04'))
        second = self.approve()
        self.assertNotEqual(first, second)
        self.assertEqual((first.parent / 'approved.md').read_text(), EXAMPLE)
        self.assertEqual(fix.check(second)['fix_round'], 0)
        with self.assertRaises(ValueError):
            fix.check(first)

    def test_missing_confirmation_or_render_failure_does_not_approve_or_replace_review(self):
        page = fix.render(self.bug)
        original = page.read_bytes()
        with self.assertRaises(ValueError):
            fix.approve(self.bug, '  ')
        self.bug.write_text(EXAMPLE + '\n```python\nunclosed')
        with self.assertRaises(ValueError):
            fix.render(self.bug)
        self.assertEqual(page.read_bytes(), original)
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_deployed_cli_works_without_plan_and_reuses_progress_helpers(self):
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
        helper = self.project / '.codex/common/scripts/keel-common.sh'
        result = subprocess.run(['bash', '-c', 'set -euo pipefail\nexport KEEL_PROFILE="$1"\nsource "$2"\nupdate_progress keel-builder BUG_BUILD "正在修复"\ncomplete_stage keel-builder BUG_BUILD_DONE "已完成" "$3"',
                                 'fix-test', str(state), str(helper), str(state.parent / 'approved.md')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('BUG_BUILD_DONE', (state.parent / 'progress.tsv').read_text())
        self.assertFalse((self.project / '.keel/plans').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
