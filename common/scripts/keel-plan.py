#!/usr/bin/env python3
"""Validate the Codex Markdown plan and render its offline HTML review."""
import argparse
import base64
import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

SECTIONS = (
    "背景与范围", "现有业务流程与状态机", "本次功能目标", "功能时序图", "状态机调整",
    "接口设计", "代码改造点", "技术决策与约束", "实施顺序", "验证方案",
)
SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"


def blocks(source):
    """Split fenced code from prose so headings in examples cannot satisfy the contract."""
    result, prose, code = [], [], None
    fence = language = ""
    for line in source.splitlines():
        if code is not None:
            if re.fullmatch(re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                result.append((language, "\n".join(code)))
                code = None
            else:
                code.append(line)
        else:
            match = re.fullmatch(r"(`{3,}|~{3,})([\w+-]*)\s*", line)
            if match:
                if prose:
                    result.append((None, "\n".join(prose)))
                    prose = []
                fence, language = match.groups()
                code = []
            else:
                prose.append(line)
    if code is not None:
        raise ValueError("Markdown 代码围栏未闭合")
    if prose:
        result.append((None, "\n".join(prose)))
    return result


def validate(path):
    if path.suffix != ".md" or not path.is_file():
        raise ValueError(f"需要存在的 Markdown 计划: {path}")
    source = path.read_text(encoding="utf-8")
    if not source.strip() or source.lstrip().startswith("<"):
        raise ValueError("需要完整 Markdown 计划；旧 XML 输入请重新运行 /keel-plan")
    parts = blocks(source)
    prose = "\n".join(body for lang, body in parts if lang is None)
    titles = re.findall(r"^# (.+)$", prose, re.M)
    if len(titles) != 1 or not source.startswith("# "):
        raise ValueError("Markdown 必须以唯一一级标题开头")
    if re.search(r"\b(?:TBD|TODO|FIXME)\b|^\s*- 决策：(?:待确认|待选择|待定)\s*$", prose, re.I | re.M):
        raise ValueError("计划仍含未决标记，请完成决策后再进入审阅/开发")
    headings = re.findall(r"^## (.+)$", prose, re.M)
    if headings not in [list(SECTIONS), [*SECTIONS, "风险与恢复"]]:
        raise ValueError("计划章节缺失、重复或顺序错误；必须依次包含：" + "、".join(SECTIONS) + "；风险与恢复可选")

    sections = {}
    active = None
    for lang, body in parts:
        if lang is not None:
            if active is not None:
                sections[active].append((lang, body))
            if lang.lower() == "plantuml":
                validate_diagram(body)
            continue
        chunk = []
        for line in body.splitlines():
            if line.startswith("## "):
                if active is not None:
                    sections[active].append((None, "\n".join(chunk)))
                active = line[3:]
                sections[active] = []
                chunk = []
            else:
                chunk.append(line)
        if active is not None:
            sections[active].append((None, "\n".join(chunk)))
    for name, content in sections.items():
        if not any(body.strip() for _, body in content):
            raise ValueError(f"计划章节为空: {name}")

    goals = "\n".join(body for lang, body in sections["本次功能目标"] if lang is None)
    entries = re.split(r"^### (.+)$", goals, flags=re.M)
    if len(entries) < 3:
        raise ValueError("本次功能目标必须包含 ### slug — 功能名")
    choices = {}
    for title, body in zip(entries[1::2], entries[2::2]):
        match = re.fullmatch(f"({SLUG}) — (.+)", title)
        if not match or match[1] in choices:
            raise ValueError(f"功能标题或 slug 重复/不合法: {title}")
        choice = re.findall(r"^- 时序图：(生成|不生成)\s*$", body, re.M)
        if len(choice) != 1:
            raise ValueError(f"功能 {match[1]} 必须明确唯一时序图选择")
        for label in ("目标", "目标流程", "验收标准"):
            if not re.search(r"^- " + label + r"：\S.+", body, re.M):
                raise ValueError(f"功能 {match[1]} 缺少{label}")
        choices[match[1]] = choice[0]

    selected = {slug for slug, choice in choices.items() if choice == "生成"}
    diagrams = {}
    current = None
    for lang, body in sections["功能时序图"]:
        if lang is None:
            for title in re.findall(r"^### (.+)$", body, re.M):
                match = re.fullmatch(f"({SLUG}) — (.+)", title)
                if not match or match[1] not in selected or match[1] in diagrams:
                    raise ValueError(f"时序图必须对应已选择且唯一的功能: {title}")
                current = match[1]
                diagrams[current] = 0
        elif lang.lower() == "plantuml":
            if current is None:
                raise ValueError("时序图前缺少功能三级标题")
            diagrams[current] += 1
    if set(diagrams) != selected or any(count < 1 for count in diagrams.values()):
        raise ValueError("时序图与功能选择不一致：每个已选功能都必须有图")
    return source, parts, titles[0], choices


def validate_diagram(source):
    lines = source.strip().splitlines()
    if not lines or lines[0].strip() != "@startuml" or lines[-1].strip() != "@enduml":
        raise ValueError("PlantUML 每个围栏必须以 @startuml 开始、@enduml 结束")
    if len(re.findall(r"^\s*@(?:start|end)\w+", source, re.M)) != 2:
        raise ValueError("每个 PlantUML 围栏只能有一张图")
    # No includes, preprocessing, environment access, or embedded remote/file resources.
    if re.search(r"^\s*!|%\w+\s*\(|<\s*(?:img|image)\b|\[\[|(?:https?|file|ftp)://", source, re.M | re.I):
        raise ValueError("PlantUML 仅允许自包含图，不能读取文件、环境或远程资源")


def diagram_svg(source):
    jar = os.environ.get("KEEL_PLANTUML_JAR")
    if jar:
        if not Path(jar).is_file() or not shutil.which("java"):
            raise ValueError("KEEL_PLANTUML_JAR 必须指向本地 jar，且 Java 必须可用")
        command = ["java", "-Djava.awt.headless=true", "-DPLANTUML_SECURITY_PROFILE=SANDBOX", "-jar", str(Path(jar).resolve())]
    elif shutil.which("plantuml"):
        command = ["plantuml"]
    else:
        raise ValueError("含图计划需要本地 plantuml，或设置 KEEL_PLANTUML_JAR 并安装 Java；不会发送到远程渲染服务")
    env = dict(os.environ, PLANTUML_SECURITY_PROFILE="SANDBOX")
    # Smetana is bundled with PlantUML, so state diagrams do not need Graphviz.
    source = source.replace("@startuml", "@startuml\n!pragma layout smetana", 1)
    with tempfile.TemporaryDirectory(prefix="keel-plantuml-") as work_dir:
        result = subprocess.run(command + ["-tsvg", "-pipe", "-charset", "UTF-8", "-failfast2"],
                                input=source.encode("utf-8"), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60, env=env, cwd=work_dir)
    if result.returncode != 0:
        raise ValueError("PlantUML 渲染失败：" + result.stderr.decode("utf-8", errors="replace")[:1000])
    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError as error:
        raise ValueError("PlantUML 未返回有效 SVG") from error
    if root.tag != "{http://www.w3.org/2000/svg}svg" or b"Syntax Error" in result.stdout:
        raise ValueError("PlantUML 未返回成功图表")
    return "data:image/svg+xml;base64," + base64.b64encode(result.stdout).decode("ascii")


def inline(text):
    # Escape source first; only a small explicit Markdown subset becomes markup.
    pattern = r"(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?://[^\s)]+\))"
    output = []
    for token in re.split(pattern, text):
        if token.startswith("`") and token.endswith("`") and len(token) > 1:
            output.append("<code>" + html.escape(token[1:-1]) + "</code>")
        elif token.startswith("**") and token.endswith("**"):
            output.append("<strong>" + html.escape(token[2:-2]) + "</strong>")
        elif re.fullmatch(r"\[[^\]]+\]\(https?://[^\s)]+\)", token):
            label, url = re.fullmatch(r"\[([^\]]+)\]\((.+)\)", token).groups()
            output.append(f'<a href="{html.escape(url, quote=True)}" rel="noreferrer">{html.escape(label)}</a>')
        else:
            output.append(html.escape(token))
    return "".join(output)


def cells(line):
    # Escaped pipes are data, e.g. an API union type, not extra columns.
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def prose_html(source, sections):
    lines, result, paragraph, list_kind = source.splitlines(), [], [], None

    def flush():
        nonlocal list_kind
        if paragraph:
            result.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
        if list_kind:
            result.append(f"</{list_kind}>")
            list_kind = None

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            flush()
        elif line.startswith("# "):
            flush()  # The page header displays the title.
        elif re.match(r"^#{2,6} ", line):
            flush()
            marks, title = line.split(" ", 1)
            anchor = ""
            if len(marks) == 2:
                anchor = f' id="section-{len(sections) + 1}"'
                sections.append(title)
            result.append(f"<h{len(marks)}{anchor}>{inline(title)}</h{len(marks)}>")
        elif index + 1 < len(lines) and "|" in line and all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in cells(lines[index + 1])):
            flush()
            header = cells(line)
            result.append('<div class="table-wrap"><table><thead><tr>' + "".join("<th>" + inline(cell) + "</th>" for cell in header) + "</tr></thead><tbody>")
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                row = cells(lines[index])
                if len(row) != len(header):
                    raise ValueError("Markdown 表格列数不一致：" + lines[index])
                result.append("<tr>" + "".join("<td>" + inline(cell) + "</td>" for cell in row) + "</tr>")
                index += 1
            result.append("</tbody></table></div>")
            continue
        elif re.match(r"^\s*(?:[-*]|\d+[.)]) ", line):
            match = re.match(r"^\s*([-*]|\d+[.)]) (.*)", line)
            kind = "ul" if match[1] in "-*" else "ol"
            if list_kind != kind:
                flush()
                result.append(f"<{kind}>")
                list_kind = kind
            result.append("<li>" + inline(match[2]) + "</li>")
        elif line.startswith("> "):
            flush()
            result.append("<blockquote>" + inline(line[2:]) + "</blockquote>")
        else:
            if list_kind:
                flush()
            paragraph.append(line.strip())
        index += 1
    flush()
    return "\n".join(result)


def render(plan, output, template):
    source, parts, title, choices = validate(plan)
    plan, output = plan.resolve(), output.resolve()
    if plan.parent.name != "plans" or plan.parent.parent.name != ".keel":
        raise ValueError("HTML 源计划必须位于 <project>/.keel/plans/")
    if output != plan.with_suffix(".html"):
        raise ValueError("HTML 必须与 Markdown 位于同目录且同名")
    sections, rendered, diagram_count = [], [], 0
    for lang, body in parts:
        if lang is None:
            rendered.append(prose_html(body, sections))
        elif lang.lower() == "plantuml":
            diagram_count += 1
            src = diagram_svg(body)
            rendered.append(f'<figure><div class="diagram"><img src="{src}" alt="业务图 {diagram_count}" /></div>'
                            f'<figcaption>业务图 {diagram_count} · PlantUML</figcaption><details><summary>查看图表源码</summary>'
                            f'<pre><code>{html.escape(body)}</code></pre></details></figure>')
        else:
            rendered.append("<pre><code>" + html.escape(body) + "</code></pre>")
    replacements = {
        "TITLE": html.escape(title),
        "NAV": "\n".join(f'<a href="#section-{index}">{html.escape(name)}</a>' for index, name in enumerate(sections, 1)),
        "CONTENT": "\n".join(rendered),
        "FEATURE_COUNT": str(len(choices)),
        "SELECTED_COUNT": str(sum(choice == "生成" for choice in choices.values())),
        "DIAGRAM_COUNT": str(diagram_count),
        "SOURCE": html.escape(source),
        "SOURCE_BASE64": base64.b64encode(source.encode("utf-8")).decode("ascii"),
        "FILE_NAME": html.escape(plan.name, quote=True),
    }
    page = template.read_text(encoding="utf-8")
    required = set(re.findall(r"__KEEL_(\w+)__", page))
    if required != set(replacements):
        raise ValueError("HTML 模板占位符不完整")
    page = re.sub(r"__KEEL_(\w+)__", lambda match: replacements[match[1]], page)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".keel-plan-html.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(page)
        temporary.chmod(0o644)
        temporary.replace(output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate")
    check.add_argument("plan", type=Path)
    view = commands.add_parser("render")
    view.add_argument("plan", type=Path)
    view.add_argument("output", type=Path)
    view.add_argument("template", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate(args.plan)
        else:
            render(args.plan, args.output, args.template)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
