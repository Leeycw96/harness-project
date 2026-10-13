#!/usr/bin/env python3
"""Exercise concise bug reviews, qualification and independent QA scoring."""
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

    def deploy_runtime(self):
        result = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def qa_score(self, output_dir, score, retest=False):
        result = subprocess.run([sys.executable, str(self.project / '.codex/common/scripts/keel-qa-score.py'),
                                 'record', '-', '--output-dir', str(output_dir), '--fix', str(self.bug),
                                 *(['--retest'] if retest else [])],
                                input=json.dumps({'goals': {'bug': score}, 'checks': {'金额回归': score}}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

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
        script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
        expected = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-" + expected + "'", page)
        self.assertIn('data-theme="dark"', page)
        self.assertIn('theme-toggle', page)
        self.assertFalse((self.project / '.keel/plans').exists())

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

    def test_investigation_without_evidence_remains_eligible_and_renders(self):
        template = (SKILL / 'assets/investigation-template.md').read_text()
        self.assertNotRegex(template, r'(?m)^- 证据：')
        self.assertNotRegex(self.investigation.read_text(), r'(?m)^- 证据：')
        self.assertTrue(fix.validate(self.bug)['eligible'])
        self.assert_concise_review(fix.render(self.bug).read_text())

    def test_only_local_defects_are_eligible_for_fix(self):
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
                self.assertFalse(fix.validate(self.bug)['eligible'])
                self.assertIn('定位或范围未满足，不能进入修复', fix.render(self.bug).read_text())
                self.assertFalse((self.bug.parent / 'runs').exists())

    def test_optional_historical_evidence_and_progress_stay_private(self):
        original_html = fix.render(self.bug).read_bytes()
        updated = INVESTIGATION.replace('- 分流依据：', '- 证据：调查专用证据标记，历史字段可保留。\n- 分流依据：')
        self.investigation.write_text(updated + '\n## 补充调查\n\n补充日志与回归进展。\n')
        self.assertTrue(fix.validate(self.bug)['eligible'])
        self.assert_concise_review(fix.render(self.bug).read_text())
        self.assertEqual(self.bug.with_suffix('.html').read_bytes(), original_html)

    def test_legacy_without_evidence_still_validates_and_renders(self):
        self.investigation.unlink()
        legacy = re.sub(r'(?m)^- 证据：.*\n', '', LEGACY)
        legacy += '\n```python\nevidence_code_should_stay_private = 1\n```\n'
        self.bug.write_text(legacy)
        self.assertTrue(fix.validate(self.bug)['eligible'])
        self.assert_concise_review(fix.render(self.bug).read_text())
        self.assertFalse((self.bug.parent / 'runs').exists())

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
                self.assertFalse(fix.validate(self.bug)['eligible'])
                self.assertIn('定位或范围未满足，不能进入修复', fix.render(self.bug).read_text())

    def test_validate_is_read_only_and_render_creates_only_html(self):
        before = {path: path.read_bytes() for path in self.project.rglob('*') if path.is_file()}
        self.assertTrue(fix.validate(self.bug)['eligible'])
        self.assertEqual({path: path.read_bytes() for path in self.project.rglob('*') if path.is_file()}, before)
        page = fix.render(self.bug)
        self.assertEqual({path for path in self.project.rglob('*') if path.is_file()}, set(before) | {page})
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_render_failure_preserves_existing_html(self):
        page = fix.render(self.bug)
        original = page.read_bytes()
        self.bug.write_text(EXAMPLE + '\n```python\nunclosed')
        with self.assertRaises(ValueError):
            fix.render(self.bug)
        self.assertEqual(page.read_bytes(), original)
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_symlink_inputs_and_output_cannot_be_read_or_overwritten(self):
        self.bug.unlink()
        source = self.bug.with_name('original.md')
        source.write_text(EXAMPLE)
        self.bug.symlink_to(source)
        with self.assertRaises(ValueError):
            fix.validate(self.bug)
        self.bug.unlink()
        self.bug.write_text(EXAMPLE)
        self.investigation.unlink()
        details = self.investigation.with_name('original-investigation.md')
        details.write_text(INVESTIGATION)
        self.investigation.symlink_to(details)
        with self.assertRaises(ValueError):
            fix.validate(self.bug)
        self.investigation.unlink()
        self.investigation.write_text(INVESTIGATION)
        target = self.bug.with_name('original.html')
        target.write_text('existing HTML')
        self.bug.with_suffix('.html').symlink_to(target)
        with self.assertRaises(ValueError):
            fix.render(self.bug)
        self.assertEqual(target.read_text(), 'existing HTML')

    def test_qa_pass_score_does_not_require_feedback(self):
        self.deploy_runtime()
        run = self.bug.parent / 'runs/run-1'
        returned_score = self.qa_score(run, 100)
        self.assertEqual(returned_score, run / 'qa-score.json')
        record = json.loads(returned_score.read_text())
        self.assertEqual(record['goals']['bug'], 100)
        self.assertEqual({path.name for path in run.iterdir()}, {'qa-score.json'})

    def test_qa_retest_preserves_initial_score_and_feedback(self):
        self.deploy_runtime()
        run = self.bug.parent / 'runs/run-1'
        initial_score = self.qa_score(run, 0)
        initial_bytes = initial_score.read_bytes()
        feedback = run / 'qa-feedback.md'
        feedback.write_text('REJECTED：初验金额错误，保留原报告。')
        feedback_bytes = feedback.read_bytes()
        returned_score = self.qa_score(run, 100, retest=True)
        self.assertRegex(returned_score.name, r'^qa-score-retest-[0-9a-f]{12}\.json$')
        self.assertNotEqual(returned_score, initial_score)
        self.assertEqual(initial_score.read_bytes(), initial_bytes)
        self.assertEqual(feedback.read_bytes(), feedback_bytes)
        self.assertEqual({path.name for path in run.iterdir()},
                         {'qa-score.json', 'qa-feedback.md', returned_score.name})

    def test_deployed_cli_uses_runtime_helpers_and_creates_only_review(self):
        self.deploy_runtime()
        script = self.project / '.agents/skills/keel-fix/scripts/keel-fix.py'
        unrelated = self.project / 'common/scripts/keel-plan.py'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('raise RuntimeError("project code must not shadow deployed helpers")')
        before = {path: path.read_bytes() for path in self.project.rglob('*') if path.is_file()}
        validated = subprocess.run([sys.executable, str(script), 'validate', str(self.bug)], capture_output=True, text=True)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(validated.stdout.strip(), '可审阅的局部缺陷')
        rendered = subprocess.run([sys.executable, str(script), 'render', str(self.bug)], capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertEqual(rendered.stdout.strip(), str(self.bug.with_suffix('.html')))
        self.assert_concise_review(self.bug.with_suffix('.html').read_text())
        self.assertEqual({path for path in self.project.rglob('*') if path.is_file()},
                         set(before) | {self.bug.with_suffix('.html')})
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertFalse((self.bug.parent / 'runs').exists())

    def test_deployed_cli_reports_design_changes_without_starting_fix(self):
        self.deploy_runtime()
        script = self.project / '.agents/skills/keel-fix/scripts/keel-fix.py'
        self.investigation.write_text(INVESTIGATION.replace('业务流程调整：无', '业务流程调整：有'))
        validated = subprocess.run([sys.executable, str(script), 'validate', str(self.bug)], capture_output=True, text=True)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(validated.stdout.strip(), '继续定位或提示转 Plan，不可进入 fix')
        rendered = subprocess.run([sys.executable, str(script), 'render', str(self.bug)], capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn('定位或范围未满足，不能进入修复', self.bug.with_suffix('.html').read_text())
        self.assertFalse((self.bug.parent / 'runs').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
