#!/usr/bin/env python3
"""Render a local bug review and record the user's approval for a fix run."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
COMMON = ROOT / 'common/scripts/keel-plan.py'
VIEW = ROOT / 'keel-plan/skills/keel-plan/assets/plan-view-template.html'
if Path(__file__).resolve().parents[3].name == '.agents':
    COMMON = ROOT / '.codex/common/scripts/keel-plan.py'
    VIEW = ROOT / '.agents/skills/keel-plan/assets/plan-view-template.html'
spec = importlib.util.spec_from_file_location('keel_review_markdown', COMMON)
markdown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(markdown)

SECTIONS = ('问题', '原因', '改造点', '影响点', '建议验证点')
LEGACY_SECTIONS = ('问题与根因', '修复方案', '影响与验证')
BOUNDARIES = ('业务状态调整', '业务流程调整', '接口契约调整', '数据模型或迁移', '高风险设计')


def atomic_write(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('不能覆盖符号链接: ' + str(path))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def field(content, label, multiple=False):
    values = re.findall(r'^- ' + re.escape(label) + r'：(.+)$', content, re.M)
    if not values or any(not value.strip() for value in values) or (not multiple and len(values) != 1):
        raise ValueError('缺少或重复字段: ' + label)
    return values if multiple else values[0]


def qualification(content):
    values = {label: field(content, label) for label in ('定位结论', '事项分类', '处理路径', *BOUNDARIES)}
    if (values['定位结论'] not in {'已定位', '候选原因', '暂未定位'} or
            values['事项分类'] not in {'缺陷', '需求变更', '待判断'} or
            values['处理路径'] not in {'fix', 'plan', '待判断', '待补证据'}):
        raise ValueError('定位结论、事项分类或处理路径无效')
    if any(values[label] not in {'无', '有', '待确认'} for label in BOUNDARIES):
        raise ValueError('影响边界只能填写无、有或待确认')
    eligible = (values['定位结论'] == '已定位' and values['事项分类'] == '缺陷' and
                values['处理路径'] == 'fix' and all(values[label] == '无' for label in BOUNDARIES))
    return values, eligible


def investigation(source):
    path = source.parent / 'investigation.md'
    if path.is_symlink():
        raise ValueError('调查资料不能使用符号链接')
    raw = path.read_bytes()
    parts = markdown.blocks(raw.decode('utf-8'))
    prose = markdown.prose(parts)
    if len(re.findall(r'^## 修复资格$', prose, re.M)) != 1:
        raise ValueError('investigation.md 需要唯一的修复资格章节')
    content = markdown.prose(markdown.section_blocks(parts)['修复资格'])
    if re.search(r'\b(?:TBD|TODO|FIXME)\b', content, re.I):
        raise ValueError('修复资格仍有未决占位符')
    for label in ('预期依据', '分流依据'):
        field(content, label)
    _, eligible = qualification(content)
    return {'raw': raw, 'eligible': eligible}


def validate(path):
    path = Path(path)
    if path.is_symlink() or path.suffix != '.md':
        raise ValueError('需要普通 Markdown 文件')
    raw = path.read_bytes()
    source = raw.decode('utf-8')
    parts = markdown.blocks(source)
    prose = '\n'.join(body for lang, body in parts if lang is None)
    titles = re.findall(r'^# (.+)$', prose, re.M)
    if not source.startswith('# ') or len(titles) != 1:
        raise ValueError('需要唯一的一级标题')
    headings = re.findall(r'^## (.+)$', prose, re.M)
    legacy = headings == list(LEGACY_SECTIONS)
    if headings != list(SECTIONS) and not legacy:
        raise ValueError('修复说明须依次包含：' + '、'.join(SECTIONS))
    if re.search(r'\b(?:TBD|TODO|FIXME)\b', prose, re.I):
        raise ValueError('修复说明仍有未决占位符')
    sections = markdown.section_blocks(parts)
    text = {name: markdown.prose(content) for name, content in sections.items()}
    details = None
    if legacy:
        problem, changes, impact = (text[name] for name in LEGACY_SECTIONS)
        for label in ('当前现象', '预期行为', '预期依据', '根因', '分流依据'):
            field(problem, label)
        for label in ('定位结论', '事项分类', '处理路径'):
            field(problem, label)
        field(changes, '修复目标')
        for label in BOUNDARIES:
            field(changes, label)
        for label in ('影响范围', '现场待验证'):
            field(impact, label)
        _, eligible = qualification(problem + '\n' + changes)
        summary = {
            '问题': field(problem, '当前现象') + '\n\n预期：' + field(problem, '预期行为'),
            '原因': field(problem, '根因'),
            '改造点': '\n'.join('- ' + value for value in field(changes, '代码改造点', multiple=True)),
            '影响点': field(impact, '影响范围'),
            '建议验证点': '\n'.join('- ' + value for value in field(impact, '回归验证', multiple=True)) +
                         '\n- ' + field(impact, '现场待验证'),
        }
    else:
        if any(lang is not None for lang, _ in parts):
            raise ValueError('简要修复说明不包含代码块，调查详情保留在 investigation.md')
        if any(not text[name].strip() for name in SECTIONS):
            raise ValueError('修复说明各章须有简要内容')
        if not re.search(r'^- .*`[^`]+`.*[：:].+', text['改造点'], re.M):
            raise ValueError('改造点须列真实类或模块，并用一句话说明改动')
        details = investigation(path)
        eligible = details['eligible']
        summary = {name: text[name].strip() for name in SECTIONS}
    return {'raw': raw, 'source': source, 'title': titles[0], 'parts': parts, 'summary': summary,
            'eligible': eligible, 'investigation': details}


def require_fix(document):
    if not document['eligible']:
        raise ValueError('只有已定位且不涉及设计变化的局部缺陷可进入 fix；其余继续定位或提示用户走 keel-plan')


def render(source):
    source = Path(source).absolute()
    document = validate(source)
    template = VIEW.read_text()
    styles = re.findall(r'<style>(.*?)</style>', template, re.S)
    scripts = re.findall(r'<script>(.*?)</script>', template, re.S)
    if len(styles) != 1 or len(scripts) != 1:
        raise ValueError('共享审阅样式或主题脚本不完整')
    script = scripts[0]
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    sections, content = [], []
    for name in SECTIONS:
        content.append(markdown.prose_html('## ' + name + '\n\n' + document['summary'][name], sections))
    nav = ''.join(f'<a href="#section-{i}">{html.escape(name)}</a>' for i, name in enumerate(sections, 1))
    title = html.escape(document['title'])
    status = '待用户确认修复方案' if document['eligible'] else '定位或范围未满足，不能进入修复'
    source64 = base64.b64encode(document['raw']).decode()
    page = f'''<!doctype html>
<html lang="zh-CN" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>{title} · Keel Fix</title><style>{styles[0]}</style><script>{script}</script></head>
<body><header class="topbar"><span class="brand">KEEL / FIX</span><div class="topbar-actions">
<span class="status">{status}</span><button class="theme-toggle" id="theme-toggle" type="button" hidden>切换浅色</button></div></header>
<div class="layout"><aside><div class="nav-label">修复说明</div><nav aria-label="修复章节">{nav}</nav></aside>
<main><div class="eyebrow">BUG 修复审阅</div><h1>{title}</h1>
<p class="lead">查看问题、修复方式和业务影响，再在会话中确认或提出修改。</p>
<article id="fix-content">{''.join(content)}</article>
<details class="source"><summary>下载修复说明</summary>
<a download="{html.escape(source.name, quote=True)}" href="data:text/markdown;charset=utf-8;base64,{source64}">下载 Markdown</a>
</details>
<footer>确认修复说明后开始修复与验收。</footer>
</main></div></body></html>'''
    output = source.with_suffix('.html')
    atomic_write(output, page.encode())
    return output


def check(state_path):
    state_path = Path(state_path).absolute()
    state = json.loads(state_path.read_text())
    if state.get('mode') != 'fix':
        raise ValueError('不是独立 fix 运行记录')
    approval = state.get('approval')
    if (not isinstance(approval, dict) or not isinstance(approval.get('decision'), str) or
            not approval['decision'].strip() or not isinstance(approval.get('confirmed_at'), str) or
            not approval['confirmed_at'].strip()):
        raise ValueError('fix 运行记录缺少用户确认原文或批准时间')
    bug_path = state.get('bug_path')
    if not isinstance(bug_path, str) or not bug_path.strip():
        raise ValueError('fix 运行记录缺少 bug.md 来源路径')
    source = Path(bug_path)
    if not source.is_absolute() or source.name != 'bug.md' or source.is_symlink() or not source.is_file():
        raise ValueError('fix 执行输入 bug.md 缺失或路径无效')
    # Old runs may still name approval snapshots; always use the current source files.
    state['fix_path'] = str(source)
    if 'investigation_path' in state:
        investigation_path = source.with_name('investigation.md')
        if investigation_path.is_symlink() or not investigation_path.is_file():
            raise ValueError('fix 执行输入 investigation.md 缺失或路径无效')
        state['investigation_path'] = str(investigation_path)
    return state


def approve(source, decision):
    source = Path(source).absolute()
    if not decision.strip():
        raise ValueError('必须记录用户对当前方案的明确确认原文')
    if source.name != 'bug.md' or source.parent.parent.name != 'bugs' or source.parent.parent.parent.name != '.keel':
        raise ValueError('确认来源须为 <project>/.keel/bugs/<id>/bug.md')
    if any(path.is_symlink() for path in (source, source.parent, source.parent.parent, source.parent.parent.parent)):
        raise ValueError('BUG 路径不能使用符号链接')
    runs = source.parent / 'runs'
    if runs.is_symlink():
        raise ValueError('运行目录不能使用符号链接')
    existing = sorted((path for path in runs.glob('run-*') if re.fullmatch(r'run-\d+', path.name)), key=lambda path: int(path.name[4:]))
    if existing:
        latest = existing[-1] / 'state.json'
        previous = check(latest)
        if previous.get('bug_path') != str(source):
            raise ValueError('已有 fix 运行记录不属于当前 BUG')
        return latest  # Repeating approval must not reset the repair limit or run state.
    document = validate(source)
    require_fix(document)
    page = source.with_suffix('.html')
    if page.is_symlink():
        raise ValueError('HTML 不能使用符号链接')
    page.read_bytes()
    details = document['investigation']
    runs.mkdir(exist_ok=True)
    run = runs / 'run-1'
    run.mkdir()
    state = {'mode': 'fix', 'project_dir': str(source.parents[3]), 'output_dir': str(run),
             'bug_path': str(source), 'fix_path': str(source), 'phase': 'PREFLIGHT',
             'approval': {'decision': decision, 'confirmed_at': datetime.now(timezone.utc).isoformat()},
             'artifacts': {'qa_feedback': str(run / 'qa-feedback.md'), 'fix_brief': str(run / 'fix-brief.md')},
             'limits': {'fix_rounds': 3, 'stage_recoveries': 2}, 'fix_round': 0, 'retries': {},
             'thresholds': {'short_stage_no_progress_seconds': 300, 'long_stage_no_progress_seconds': 900},
             'build': {'commits': []}, 'review': {'qa': {'status': 'pending'}},
             'preflight': {'main_compile': {'status': 'pending', 'summary': []},
                           'test_compile': {'status': 'pending', 'summary': [], 'user_decision': None}}}
    if details:
        state['investigation_path'] = str(source.with_name('investigation.md'))
    write_json(run / 'state.json', state)
    return run / 'state.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'render', 'approve', 'check'))
    parser.add_argument('path', type=Path)
    parser.add_argument('--decision', default='')
    args = parser.parse_args()
    try:
        if args.command == 'render':
            print(render(args.path))
        elif args.command == 'approve':
            print(approve(args.path, args.decision))
        elif args.command == 'check':
            print(check(args.path)['fix_path'])
        else:
            document = validate(args.path)
            print('可审阅的局部缺陷' if document['eligible'] else '继续定位或提示转 Plan，不可进入 fix')
    except (OSError, ValueError, KeyError) as error:
        print('错误: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
