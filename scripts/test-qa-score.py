#!/usr/bin/env python3
"""Exercise business scoring, immutable first reviews and read-only history."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'common/scripts/keel-qa-score.py'
ASSETS = ROOT / 'keel-plan/skills/keel-plan/assets'


class QaScoreTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='keel-qa-score-test-')
        self.project = Path(self.work.name).resolve()
        self.plan = self.project / 'plan.md'
        shutil.copyfile(ASSETS / 'plan-template.md', self.plan)
        shutil.copytree(ASSETS / 'plan-template.features', self.project / 'plan-template.features')
        self.fix = self.project / 'approved.md'
        shutil.copyfile(ROOT / 'keel-dev/skills/keel-fix/assets/bug-template.md', self.fix)
        self.input = self.project / 'qa-input.json'

    def tearDown(self):
        self.work.cleanup()

    def cli(self, *args, success=True, stdin=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                input=stdin, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def payload(self):
        return {'schema_version': 1, 'builder': 'Builder A', 'review': 'initial',
                'verdict': 'REJECTED', 'blockers': ['退款失败场景未达到目标'],
                'goal_results': [
                    {'id': 'cancel-order', 'status': 'passed', 'evidence': ['验收报告#取消申请']},
                    {'id': 'confirm-refund', 'status': 'failed', 'evidence': '验收报告#退款失败'}],
                'checks': [{'name': '本次业务检查', 'items': [
                    {'name': '重复申请', 'status': 'passed', 'evidence': ['验证结果#重复申请']},
                    {'name': '失败回调', 'status': 'failed', 'evidence': ['验证结果#失败回调']},
                    {'name': '现场复验', 'status': 'unverified', 'reason': '等待现场确认'}]}],
                'limitations': ['原场景仍待现场复验'], 'commits': ['a' * 40]}

    def record(self, payload, name='run-1', scope='plan', success=True, stdin=False):
        output = self.project / name
        self.input.write_text(json.dumps(payload, ensure_ascii=False))
        source_args = [] if scope is None else ['--' + scope, self.plan if scope == 'plan' else self.fix]
        result = self.cli('record', '-' if stdin else self.input, '--output-dir', output,
                          *source_args, success=success,
                          stdin=json.dumps(payload, ensure_ascii=False) if stdin else None)
        return output, result

    def score(self, output):
        return json.loads((output / 'qa-score.json').read_text())

    def history(self, directory=None, *args):
        result = self.cli('history', directory or self.project, *args, '--json')
        return json.loads(result.stdout)

    def test_plan_feature_goals_define_denominator_and_score(self):
        output, _ = self.record(self.payload())
        record = self.score(output)
        self.assertEqual(record['goal_score'], {'completed': 1, 'total': 2, 'failed': 1,
                                                'unverified': 0, 'percent': 50})
        self.assertEqual(record['verdict'], 'REJECTED')
        self.assertEqual(record['source']['kind'], 'plan')
        self.assertEqual(record['source']['path'], str(self.plan))
        self.assertEqual({goal['id'] for goal in record['source']['catalog']},
                         {'cancel-order', 'confirm-refund'})

    def test_arbitrary_check_groups_can_be_added_removed_or_left_empty(self):
        payload = self.payload()
        payload.pop('goal_results')
        payload['checks'].append({'name': '临时自选检查', 'items': [
            {'name': '本次接口约定', 'status': 'passed', 'evidence': '接口检查记录'}]})
        payload['checks'].append({'name': '本次未选择检查项', 'items': []})
        output, _ = self.record(payload, name='custom-checks', scope=None)
        record = self.score(output)
        self.assertIsNone(record['goal_score'])
        groups = {group['name']: group for group in record['check_scores']}
        self.assertEqual(set(groups), {'本次业务检查', '临时自选检查', '本次未选择检查项'})
        self.assertEqual(groups['本次业务检查']['total'], 3)
        self.assertEqual(groups['本次业务检查']['completed'], 1)
        self.assertEqual(groups['本次业务检查']['failed'], 1)
        self.assertEqual(groups['本次业务检查']['unverified'], 1)
        self.assertAlmostEqual(groups['本次业务检查']['percent'], 100 / 3, places=2)
        self.assertEqual(groups['临时自选检查']['percent'], 100)
        self.assertEqual(groups['本次未选择检查项']['total'], 0)
        self.assertIsNone(groups['本次未选择检查项']['percent'])
        payload['checks'] = []
        output, _ = self.record(payload, name='removed-checks', scope=None)
        self.assertEqual(self.score(output)['check_scores'], [])
        self.assertIsNone(self.score(output)['goal_score'])

    def test_stdin_and_unknown_builder_support_check_only_records(self):
        payload = self.payload()
        payload.pop('builder')
        payload.pop('goal_results')
        output, _ = self.record(payload, name='stdin', stdin=True)
        record = self.score(output)
        self.assertEqual(record['builder'], 'unknown')
        self.assertIsNone(record['goal_score'])
        self.assertEqual(record['check_scores'][0]['completed'], 1)

    def test_deployed_cli_can_record_and_read_scores_with_its_shared_parser(self):
        deployed = subprocess.run([str(ROOT / 'bin/keel'), 'dev', '--codex', str(self.project)],
                                  capture_output=True, text=True)
        self.assertEqual(deployed.returncode, 0, deployed.stderr)
        script = self.project / '.codex/common/scripts/keel-qa-score.py'
        self.input.write_text(json.dumps(self.payload(), ensure_ascii=False))
        output = self.project / '.keel/iterations/test/run-1'
        recorded = subprocess.run([sys.executable, str(script), 'record', str(self.input),
                                   '--output-dir', str(output), '--plan', str(self.plan)],
                                  capture_output=True, text=True)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(self.score(output)['goal_score']['percent'], 50)
        viewed = subprocess.run([sys.executable, str(script), 'history', str(self.project), '--json'],
                                capture_output=True, text=True)
        self.assertEqual(viewed.returncode, 0, viewed.stderr)
        self.assertEqual(len(json.loads(viewed.stdout)['records']), 1)
        self.assertFalse((output / 'state.json').exists())

    def test_omitted_and_unverified_goals_do_not_shrink_denominator(self):
        payload = self.payload()
        payload['goal_results'] = payload['goal_results'][:1]
        output, _ = self.record(payload, name='omitted')
        self.assertEqual(self.score(output)['goal_score'],
                         {'completed': 1, 'total': 2, 'failed': 0, 'unverified': 1, 'percent': 50})
        payload['goal_results'][0] = {'id': 'cancel-order', 'status': 'unverified',
                                      'reason': '环境不可用'}
        output, _ = self.record(payload, name='unverified')
        self.assertEqual(self.score(output)['goal_score'],
                         {'completed': 0, 'total': 2, 'failed': 0, 'unverified': 2, 'percent': 0})

    def test_unknown_duplicate_or_unsupported_goal_results_are_rejected(self):
        for results in ([{'id': 'unknown', 'status': 'passed', 'evidence': ['证明']}],
                        [self.payload()['goal_results'][0]] * 2,
                        [{'id': 'cancel-order', 'status': 'passed'}],
                        [{'id': 'cancel-order', 'status': 'failed', 'evidence': []}],
                        [{'id': 'cancel-order', 'status': 'unverified'}]):
            with self.subTest(results=results):
                payload = self.payload()
                payload['goal_results'] = results
                output, _ = self.record(payload, name='invalid-result', success=False)
                self.assertFalse((output / 'qa-score.json').exists())

    def test_scores_are_calculated_without_inferring_business_verdict(self):
        payload = self.payload()
        payload['score'] = 100
        payload['goal_score'] = {'completed': 100, 'total': 1, 'percent': 100}
        output, _ = self.record(payload, name='handwritten-score')
        self.assertEqual(self.score(output)['goal_score']['percent'], 50)
        for goal in payload['goal_results']:
            goal['status'] = 'passed'
        output, _ = self.record(payload, name='all-goals-pass')
        record = self.score(output)
        self.assertEqual(record['goal_score']['percent'], 100)
        self.assertEqual(record['verdict'], 'REJECTED')
        for goal in payload['goal_results']:
            goal['status'] = 'failed'
        payload['verdict'] = 'APPROVED'
        payload['blockers'] = []
        output, _ = self.record(payload, name='business-verdict-preserved')
        self.assertEqual(self.score(output)['goal_score']['percent'], 0)
        self.assertEqual(self.score(output)['verdict'], 'APPROVED')

    def test_first_score_is_idempotent_and_cannot_be_overwritten(self):
        payload = self.payload()
        output, _ = self.record(payload)
        first = (output / 'qa-score.json').read_bytes()
        self.record(copy.deepcopy(payload))
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        changed = copy.deepcopy(payload)
        changed['goal_results'][1]['status'] = 'passed'
        self.record(changed, success=False)
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        changed['review'] = 'retest'
        self.record(changed)
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        retests = list(output.glob('qa-score-retest-*.json'))
        self.assertEqual(len(retests), 1)
        self.assertEqual(json.loads(retests[0].read_text())['goal_score']['percent'], 100)
        repeat = retests[0].read_bytes()
        self.record(copy.deepcopy(changed))
        self.assertEqual(list(output.glob('qa-score-retest-*.json')), retests)
        self.assertEqual(retests[0].read_bytes(), repeat)
        subset = copy.deepcopy(changed)
        subset['goal_results'] = subset['goal_results'][:1]
        self.record(subset)
        self.assertEqual((output / 'qa-score.json').read_bytes(), first)
        retests = list(output.glob('qa-score-retest-*.json'))
        self.assertEqual(len(retests), 2)
        self.assertEqual({json.loads(path.read_text())['goal_score']['percent'] for path in retests},
                         {50, 100})

    def test_fix_is_one_goal_and_does_not_require_a_plan_or_state(self):
        title = self.fix.read_text().splitlines()[0][2:]
        self.fix.write_text(self.fix.read_text() + '\n```python\n# 证据代码中的注释不是修复标题\namount = 10.05 * 0.9\n```\n')
        for status, percent in [('passed', 100), ('failed', 0)]:
            with self.subTest(status=status):
                payload = self.payload()
                payload['goal_results'] = [{'id': 'bug', 'status': status,
                                            'evidence': ['折扣结果验证']}]
                output, _ = self.record(payload, name='fix-' + status, scope='fix')
                record = self.score(output)
                self.assertEqual(record['goal_score']['total'], 1)
                self.assertEqual(record['goal_score']['percent'], percent)
                self.assertEqual(record['source']['kind'], 'fix')
                self.assertEqual(record['source']['catalog'], [{'id': 'bug', 'target': title}])
                self.assertIn('原场景仍待现场复验', record['limitations'])
                self.assertFalse((output / 'state.json').exists())

    def test_invalid_business_data_or_empty_plan_does_not_produce_score(self):
        for key, value in [('schema_version', 999), ('review', 'later'),
                           ('verdict', 'MAYBE'), ('blockers', '错误格式'), ('checks', '错误格式')]:
            with self.subTest(key=key):
                payload = self.payload()
                payload[key] = value
                output, _ = self.record(payload, name='invalid-format', success=False)
                self.assertFalse((output / 'qa-score.json').exists())
        self.plan.write_text('# 没有功能目标\n\n## 功能目标\n')
        output, _ = self.record(self.payload(), name='empty-plan', success=False)
        self.assertFalse((output / 'qa-score.json').exists())

    def test_invalid_check_results_are_rejected_before_saving(self):
        for item in ({'name': '检查', 'status': 'passed'},
                     {'name': '检查', 'status': 'failed', 'evidence': []},
                     {'name': '检查', 'status': 'unverified'},
                     {'name': '检查', 'status': 'unknown', 'evidence': ['记录']},
                     {'name': '检查', 'status': 'passed', 'evidence': {'record': '不支持的格式'}}):
            with self.subTest(item=item):
                payload = self.payload()
                payload['checks'] = [{'name': '本次检查', 'items': [item]}]
                output, _ = self.record(payload, name='invalid-check', success=False)
                self.assertFalse((output / 'qa-score.json').exists())

    def test_history_filters_initial_retest_builder_and_goal_kind(self):
        initial = self.payload()
        self.record(initial, name='history-a')
        passed = copy.deepcopy(initial)
        for item in passed['goal_results']:
            item['status'] = 'passed'
        self.record(passed, name='history-a-again')
        other = copy.deepcopy(initial)
        other['builder'] = 'Builder B'
        for item in other['goal_results']:
            item['status'] = 'failed'
        self.record(other, name='history-b')
        fixed = copy.deepcopy(initial)
        fixed['goal_results'] = [{'id': 'bug', 'status': 'passed', 'evidence': ['修复验证']}]
        self.record(fixed, name='history-fix', scope='fix')
        passed['review'] = 'retest'
        self.record(passed, name='history-a')
        history = self.history()
        self.assertEqual(len(history['records']), 4)
        self.assertTrue(all(record['review'] == 'initial' for record in history['records']))
        groups = {(group['kind'], group['builder'], group['review']): group
                  for group in history['summary']}
        self.assertEqual(set(groups), {('plan', 'Builder A', 'initial'),
                                      ('plan', 'Builder B', 'initial'),
                                      ('fix', 'Builder A', 'initial')})
        self.assertEqual(groups['plan', 'Builder A', 'initial']['percent'], 75)
        self.assertEqual(groups['plan', 'Builder A', 'initial']['total'], 4)
        self.assertEqual(groups['fix', 'Builder A', 'initial']['percent'], 100)
        filtered = self.history(None, '--builder', 'Builder A', '--include-retests')
        self.assertEqual(len(filtered['records']), 4)
        self.assertTrue(all(record['builder'] == 'Builder A' for record in filtered['records']))
        self.assertEqual({group['review'] for group in filtered['summary']}, {'initial', 'retest'})
        recent = self.history(None, '--last', 1, '--include-retests')
        self.assertEqual(len(recent['records']), 1)
        self.assertEqual(recent['records'][0]['review'], 'retest')
        explicit = copy.deepcopy(initial)
        explicit['project'] = '另一业务项目'
        for item in explicit['goal_results']:
            item['status'] = 'failed'
        self.record(explicit, name='history-explicit-project')
        automatic = copy.deepcopy(initial)
        for item in automatic['goal_results']:
            item['status'] = 'passed'
        auto_project = self.project / 'auto-project'
        auto_output = auto_project / '.keel/iterations/test/run-1'
        self.record(automatic, name=str(auto_output))
        self.assertEqual(self.score(auto_output)['project'], str(auto_project))
        separated = self.history(None, '--last', 100)
        project_groups = {(group['project'], group['kind'], group['builder'], group['review']): group
                          for group in separated['summary']}
        self.assertEqual(project_groups[None, 'plan', 'Builder A', 'initial']['percent'], 75)
        self.assertEqual(project_groups['另一业务项目', 'plan', 'Builder A', 'initial']['percent'], 0)
        self.assertEqual(project_groups[str(auto_project), 'plan', 'Builder A', 'initial']['percent'], 100)
        self.assertEqual(project_groups['另一业务项目', 'plan', 'Builder A', 'initial']['total'], 2)
        self.assertEqual(project_groups[str(auto_project), 'plan', 'Builder A', 'initial']['total'], 2)

    def test_history_exposes_tampered_scores_instead_of_counting_them(self):
        output, _ = self.record(self.payload())
        path = output / 'qa-score.json'
        record = self.score(output)
        record['goal_score']['percent'] = 100
        path.write_text(json.dumps(record))
        history = self.history()
        self.assertEqual(history['records'], [])
        self.assertEqual(history['summary'], [])
        self.assertEqual(len(history['errors']), 1)
        self.assertEqual(history['errors'][0]['path'], str(path))

    def test_record_and_history_do_not_read_or_modify_runtime_state(self):
        output = self.project / '.keel/iterations/test/run-1'
        output.mkdir(parents=True)
        state = output / 'state.json'
        profile = output / 'profile.json'
        state.write_bytes(b'invalid state must not be parsed\xff')
        profile.write_bytes(b'invalid profile must not be parsed\xff')
        originals = {path: path.read_bytes() for path in (state, profile)}
        self.record(self.payload(), name=str(output))
        self.assertEqual(len(self.history()['records']), 1)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.plan.unlink()
        self.assertEqual(len(self.history()['records']), 1)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_unscored_legacy_reports_are_not_assigned_zero_or_full_score(self):
        legacy = self.project / 'legacy-run'
        legacy.mkdir()
        (legacy / 'qa-feedback.md').write_text('APPROVED\n已有验收报告，没有评分记录。')
        (legacy / 'state.json').write_text('invalid state')
        history = self.history(legacy)
        self.assertEqual(history['records'], [])
        self.assertEqual(history['summary'], [])
        self.assertEqual(history['errors'], [])
        text = self.cli('history', legacy).stdout
        self.assertIn('未评分', text)
        self.assertNotIn('0.00 分', text)
        self.assertNotIn('100.00 分', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
