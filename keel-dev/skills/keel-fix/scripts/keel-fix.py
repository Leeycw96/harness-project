#!/usr/bin/env python3
"""Render a local bug review and bind a user's approval to its immutable snapshot."""
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

SECTIONS = ('问题与根因', '修复方案', '影响与验证')
BOUNDARIES = ('业务状态调整', '业务流程调整', '接口契约调整', '数据模型或迁移', '高风险设计')


def digest(data):
    return hashlib.sha256(data).hexdigest()


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
    if re.findall(r'^## (.+)$', prose, re.M) != list(SECTIONS):
        raise ValueError('修复说明须依次包含：' + '、'.join(SECTIONS))
    if re.search(r'\b(?:TBD|TODO|FIXME)\b', prose, re.I):
        raise ValueError('修复说明仍有未决占位符')
    sections = markdown.section_blocks(parts)
    text = {name: markdown.prose(content) for name, content in sections.items()}
    for label in ('当前现象', '预期行为', '预期依据', '根因', '证据', '分流依据'):
        field(text['问题与根因'], label)
    conclusion = field(text['问题与根因'], '定位结论')
    category = field(text['问题与根因'], '事项分类')
    route = field(text['问题与根因'], '处理路径')
    if conclusion not in {'已定位', '候选原因', '暂未定位'} or category not in {'缺陷', '需求变更', '待判断'} or route not in {'fix', 'plan', '待补证据'}:
        raise ValueError('定位结论、事项分类或处理路径无效')
    field(text['修复方案'], '修复目标')
    field(text['修复方案'], '代码改造点', multiple=True)
    boundaries = {label: field(text['修复方案'], label) for label in BOUNDARIES}
    if any(value not in {'无', '有', '待确认'} for value in boundaries.values()):
        raise ValueError('影响边界只能填写无、有或待确认')
    for label in ('影响范围', '现场待验证'):
        field(text['影响与验证'], label)
    field(text['影响与验证'], '回归验证', multiple=True)
    eligible = conclusion == '已定位' and category == '缺陷' and route == 'fix' and all(value == '无' for value in boundaries.values())
    return {'raw': raw, 'source': source, 'title': titles[0], 'parts': parts,
            'eligible': eligible, 'sha256': digest(raw)}


def require_fix(document):
    if not document['eligible']:
        raise ValueError('只有已定位且不涉及设计变化的局部缺陷可进入 fix；其余继续取证或提示用户走 keel-plan')


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
    for lang, body in document['parts']:
        if lang is None:
            body = re.sub(r'^- 处理路径：fix$', '- 处理建议：局部缺陷修复', body, flags=re.M)
            body = re.sub(r'^- 处理路径：plan$', '- 处理建议：进入方案评审', body, flags=re.M)
            if document['eligible']:
                for label in BOUNDARIES:
                    summary = '- 设计影响：现有业务状态、业务流程、接口契约及数据模型保持不变，不涉及高风险设计调整。' if label == BOUNDARIES[0] else ''
                    body = re.sub(r'^- ' + re.escape(label) + r'：无$', summary, body, flags=re.M)
            content.append(markdown.prose_html(body, sections))
        else:
            content.append('<pre><code>' + html.escape(body) + '</code></pre>')
    nav = ''.join(f'<a href="#section-{i}">{html.escape(name)}</a>' for i, name in enumerate(sections, 1))
    title = html.escape(document['title'])
    status = '待用户确认修复方案' if document['eligible'] else '证据或范围未满足，不能进入修复'
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
<p class="lead">核对问题证据、修复方式和影响范围，再在会话中确认或提出修改。</p>
<article id="fix-content">{''.join(content)}</article>
<details class="source"><summary>查看或下载修复说明</summary>
<a download="{html.escape(source.name, quote=True)}" href="data:text/markdown;charset=utf-8;base64,{source64}">下载 Markdown</a>
<pre><code>{html.escape(document['source'])}</code></pre></details>
<footer>HTML 与执行说明来自同一份 Markdown · 用户确认后交由 Builder 与 QA 执行</footer>
</main></div></body></html>'''
    output = source.with_suffix('.html')
    atomic_write(output, page.encode())
    write_json(source.with_suffix('.review.json'), {'source_sha256': document['sha256'], 'html_sha256': digest(page.encode())})
    return output


def check(state_path):
    state_path = Path(state_path).absolute()
    state = json.loads(state_path.read_text())
    if state.get('mode') != 'fix':
        raise ValueError('不是独立 fix 运行记录')
    source = Path(state['bug_path'])
    document = validate(source)
    require_fix(document)
    approval = state['approval']
    snapshot = state_path.parent / 'approved.md'
    if (document['sha256'] != approval['source_sha256'] or
            digest(snapshot.read_bytes()) != approval['source_sha256'] or
            state['fix_path'] != str(snapshot) or not approval['decision'].strip()):
        raise ValueError('方案已变化或确认快照不一致，必须重新审阅确认')
    if digest(source.with_suffix('.html').read_bytes()) != approval['html_sha256']:
        raise ValueError('HTML 已变化或缺失，必须重新审阅确认')
    return state


def approve(source, decision):
    source = Path(source).absolute()
    if not decision.strip():
        raise ValueError('必须记录用户对当前方案的明确确认原文')
    if source.name != 'bug.md' or source.parent.parent.name != 'bugs' or source.parent.parent.parent.name != '.keel':
        raise ValueError('确认来源须为 <project>/.keel/bugs/<id>/bug.md')
    if any(path.is_symlink() for path in (source, source.parent, source.parent.parent, source.parent.parent.parent)):
        raise ValueError('BUG 路径不能使用符号链接')
    document = validate(source)
    require_fix(document)
    review = json.loads(source.with_suffix('.review.json').read_text())
    if review.get('source_sha256') != document['sha256'] or review.get('html_sha256') != digest(source.with_suffix('.html').read_bytes()):
        raise ValueError('HTML 与当前 Markdown 不一致，须重新渲染并请用户确认')
    runs = source.parent / 'runs'
    if runs.is_symlink():
        raise ValueError('运行目录不能使用符号链接')
    runs.mkdir(exist_ok=True)
    existing = sorted((path for path in runs.glob('run-*') if re.fullmatch(r'run-\d+', path.name)), key=lambda path: int(path.name[4:]))
    if existing:
        latest = existing[-1] / 'state.json'
        previous = json.loads(latest.read_text())
        if (previous.get('approval', {}).get('source_sha256') == document['sha256'] and
                previous.get('approval', {}).get('html_sha256') == review['html_sha256']):
            check(latest)
            return latest  # Repeating approval must not reset the repair limit or progress.
    run = runs / f'run-{int(existing[-1].name[4:]) + 1 if existing else 1}'
    run.mkdir()
    atomic_write(run / 'approved.md', document['raw'])
    state = {'mode': 'fix', 'project_dir': str(source.parents[3]), 'output_dir': str(run),
             'bug_path': str(source), 'fix_path': str(run / 'approved.md'), 'phase': 'PREFLIGHT',
             'approval': {**review, 'decision': decision, 'confirmed_at': datetime.now(timezone.utc).isoformat()},
             'artifacts': {'qa_feedback': str(run / 'qa-feedback.md'), 'fix_brief': str(run / 'fix-brief.md')},
             'limits': {'fix_rounds': 3, 'stage_recoveries': 2}, 'fix_round': 0, 'retries': {},
             'thresholds': {'short_stage_no_progress_seconds': 300, 'long_stage_no_progress_seconds': 900},
             'build': {'commits': []}, 'review': {'qa': {'status': 'pending'}},
             'preflight': {'main_compile': {'status': 'pending', 'summary': []},
                           'test_compile': {'status': 'pending', 'summary': [], 'user_decision': None}}}
    write_json(run / 'state.json', state)
    atomic_write(run / 'progress.tsv', b'')
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
            print('可审阅的局部缺陷' if document['eligible'] else '继续取证或提示转 Plan，不可进入 fix')
    except (OSError, ValueError, KeyError) as error:
        print('错误: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
