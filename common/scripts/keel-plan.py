#!/usr/bin/env python3
"""Validate/snapshot a feature plan bundle and compose its offline HTML review."""
import argparse
import base64
import hashlib
import html
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

SECTIONS = ("合约设计", "数据模型", "功能时序图", "接口设计", "代码改造点")
OPTIONAL_SECTIONS = {"合约设计"}
REVIEW_SECTIONS = ("背景", "业务流程总览", "状态机")
SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
NO_MODEL_CHANGE = "本期不涉及数据模型变更，沿用现有实现。"
NO_INTERFACE_CHANGE = "本期不涉及接口变更，沿用现有实现。"
NO_INTERFACE_CHANGE_MARKERS = {NO_INTERFACE_CHANGE, "本功能无接口变更。"}


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


def section_blocks(parts):
    """Group complete prose and code blocks under their real level-two heading."""
    sections = {}
    active = None
    for lang, body in parts:
        if lang is not None:
            if active is not None:
                sections[active].append((lang, body))
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
    return sections


def read_document(path, order, optional):
    if path.suffix != ".md" or not path.is_file():
        raise ValueError(f"需要存在的 Markdown 计划: {path}")
    source = path.read_text(encoding="utf-8")
    if not source.strip() or source.lstrip().startswith("<"):
        raise ValueError("需要完整 Markdown 内容；旧格式输入请重新运行 /keel-plan")
    parts = blocks(source)
    prose = "\n".join(body for lang, body in parts if lang is None)
    titles = re.findall(r"^# (.+)$", prose, re.M)
    if len(titles) != 1 or not source.startswith("# "):
        raise ValueError("Markdown 必须以唯一一级标题开头")
    if re.search(r"\b(?:TBD|TODO|FIXME)\b|^\s*- 决策：(?:待确认|待选择|待定)\s*$", prose, re.I | re.M):
        raise ValueError("计划仍含未决标记，请完成决策后再进入审阅/开发")
    headings = re.findall(r"^## (.+)$", prose, re.M)
    expected = [name for name in order if name not in optional or name in headings]
    if headings != expected:
        raise ValueError("计划章节缺失、重复或顺序错误；顺序：" + "、".join(order))
    sections = section_blocks(parts)
    for lang, body in parts:
        if lang is not None and lang.lower() == "plantuml":
            validate_diagram(body)
    for name, content in sections.items():
        if not any(body.strip() for _, body in content):
            raise ValueError(f"计划章节为空: {name}")

    return source, parts, titles[0], sections


def prose(content):
    return "\n".join(body for lang, body in content if lang is None)


def feature_blocks(content, pattern=rf"({SLUG}) — (.+)"):
    """Keep code fences attached to each titled entry, keyed by the first capture."""
    intro, entries, active = [], {}, None
    for lang, body in content:
        if lang is not None:
            (entries[active][1] if active else intro).append((lang, body))
            continue
        chunk = []
        for line in body.splitlines():
            if line.startswith("### "):
                (entries[active][1] if active else intro).append((None, "\n".join(chunk)))
                title = line[4:]
                match = re.fullmatch(pattern, title)
                if not match or match[1] in entries:
                    raise ValueError(f"三级标题重复或不合法: {title}")
                active = match[1]
                entries[active] = (title, [])
                chunk = []
            else:
                chunk.append(line)
        (entries[active][1] if active else intro).append((None, "\n".join(chunk)))
    return intro, entries


def model_in_review(content):
    if not content:
        return False
    changes = re.findall(r"^- 结构变更：(.+)$", prose(content), re.M)
    if len(changes) != 1:
        raise ValueError("数据模型须记录一条结构变更：新增表、新增字段、其他调整或无")
    if changes[0] == "无":
        if any(lang and lang.lower() in {"sql", "plantuml"} for lang, _ in content):
            raise ValueError("无结构变更时不能定义 SQL 或模型图；共享模型请引用所属功能")
        return False
    kinds = changes[0].split("、")
    if len(kinds) != len(set(kinds)) or not set(kinds) <= {"新增表", "新增字段", "其他调整"}:
        raise ValueError("数据模型结构变更类型不合法")
    visible = bool(set(kinds) & {"新增表", "新增字段"})
    diagrams = [body for lang, body in content if lang and lang.lower() == "plantuml"]
    if visible and not any(re.search(r'^\s*entity\s+', body, re.M) for body in diagrams):
        raise ValueError("新增表或字段的数据模型必须包含 PlantUML 实体关系图")
    if not any(lang and lang.lower() == "sql" and body.strip() for lang, body in content):
        raise ValueError("数据模型必须包含本次调整的 SQL")
    return visible


def contract_names(content):
    """Check the declared artifact, not whether the project's work requires it."""
    if not content:
        return []
    text = prose(content).strip()
    if all(line.startswith("- 引用：") for line in text.splitlines() if line.strip()) and not any(
            lang is not None for lang, _ in content):
        return []  # References are resolved against the complete bundle below.
    _, sections = feature_blocks(content, r"(合约清单|合约关系)")
    if list(sections) != ["合约清单", "合约关系"]:
        raise ValueError("合约设计须先列合约清单，再给出合约关系；共享设计可直接引用")
    inventory = sections["合约清单"][1]
    if any(lang is not None for lang, _ in inventory):
        raise ValueError("合约清单须使用表格，关系图放在清单之后")
    lines = prose(inventory).splitlines()
    headers = [i for i, line in enumerate(lines) if cells(line) == ["合约", "简要说明", "本期变化"]]
    if len(headers) != 1:
        raise ValueError("合约清单须包含唯一的合约、简要说明、本期变化三列表格")
    index = headers[0] + 1
    if index >= len(lines) or len(cells(lines[index])) != 3 or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in cells(lines[index])):
        raise ValueError("合约清单表格缺少合法分隔行")
    names = []
    for line in lines[index + 1:]:
        if not line.strip() or "|" not in line:
            break
        row = cells(line)
        if len(row) != 3 or not all(row) or row[2] not in {"新增", "修改", "沿用", "删除"}:
            raise ValueError("合约清单每行须有名称、简要说明和合法的本期变化")
        name = row[0].strip("`").strip()
        if not name or name in names:
            raise ValueError("合约清单名称不能为空或重复")
        names.append(name)
    if not names:
        raise ValueError("合约清单不能为空")
    diagrams = [body for lang, body in sections["合约关系"][1] if lang and lang.lower() == "plantuml"]
    if not diagrams:
        raise ValueError("合约关系须包含 PlantUML 图，单合约也保留节点")
    nodes = set()
    for diagram in diagrams:
        for quoted, plain in re.findall(
                r'^\s*class\s+(?:"([^"]+)"|([A-Za-z_$][\w$]*))(?:\s+as\s+[A-Za-z_]\w*)?\s+<<contract>>', diagram, re.M):
            nodes.add(quoted or plain)
    if nodes != set(names):
        raise ValueError("合约关系图须用 class 和 <<contract>> 声明与清单一致的合约节点")
    return names


def one_field(content, label):
    values = re.findall(rf"^- {label}：(.+)$", prose(content), re.M)
    if len(values) != 1:
        raise ValueError(f"必须记录唯一的{label}")
    return values[0]


def local_feature_path(plan, relative, slug):
    # Feature documents live in one child directory, so snapshots remain portable.
    if not re.fullmatch(rf"[a-zA-Z0-9_.-]+/{re.escape(slug)}\.md", relative) or relative.split("/")[0] in {".", ".."}:
        raise ValueError(f"功能文档须为计划目录下的相对路径 <目录>/{slug}.md")
    path = plan.parent / relative
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("功能文档不能使用符号链接")
    return path


def validate(path):
    source, parts, title, sections = read_document(path, ("功能目标",), set())
    intro, goals = feature_blocks(sections["功能目标"])
    if not goals or any(body.strip() for _, body in intro):
        raise ValueError("功能目标必须按 ### slug — 功能名 列出")
    features = {}
    for slug, (heading, content) in goals.items():
        if any(lang is not None for lang, _ in content):
            raise ValueError("索引只保留功能目标、验收和文档路由，不放图表或实现")
        one_field(content, "目标")
        acceptance = re.findall(r"^验收标准：\s*\n((?:\s*\n)*- [^\n]+(?:\n- [^\n]+)*)", prose(content), re.M)
        if len(acceptance) != 1:
            raise ValueError(f"功能 {slug} 的验收标准必须逐条列出")
        link = re.fullmatch(rf"\[{slug}\]\(([^)]+)\)", one_field(content, "文档"))
        if not link:
            raise ValueError(f"功能 {slug} 缺少文档链接")
        relative = link[1]
        feature_path = local_feature_path(path, relative, slug)
        feature_source, feature_parts, feature_title, detail = read_document(feature_path, SECTIONS, OPTIONAL_SECTIONS)
        if feature_title != heading:
            raise ValueError(f"功能文档标题必须与索引一致: {slug}")
        dependency = one_field(content, "依赖")
        dependencies = [] if dependency == "无" else dependency.split("、")
        if len(set(dependencies)) != len(dependencies) or slug in dependencies or any(item not in goals for item in dependencies):
            raise ValueError(f"功能依赖无效: {slug}")
        contracts = contract_names(detail.get("合约设计", []))
        visible = model_in_review(detail["数据模型"])
        choice = one_field(detail["功能时序图"], "时序图")
        has_diagram = any(lang and lang.lower() == "plantuml" for lang, _ in detail["功能时序图"])
        if choice not in {"生成", "不生成"} or (choice == "生成") != has_diagram:
            raise ValueError(f"时序图与选择不一致: {slug}")
        _, interfaces = feature_blocks(detail["接口设计"], r"([A-Z]+ `/[^`\s]*`|RPC `[^`\n]+`)")
        for api_heading, api_content in interfaces.values():
            if not any(body.strip() for _, body in api_content):
                raise ValueError(f"接口设计缺少内容: {api_heading}")
        references = {}
        for section in ("合约设计", "数据模型", "接口设计"):
            refs = []
            for line in prose(detail.get(section, [])).splitlines():
                if line.startswith("- 引用："):
                    match = re.fullmatch(rf"- 引用：\[({SLUG})\]\(({SLUG})\.md#{section}\)", line)
                    if not match or match[1] != match[2] or match[1] == slug or match[1] not in goals or match[1] in refs:
                        raise ValueError(f"{slug} 的{section}引用无效")
                    refs.append(match[1])
            references[section] = refs
        interface_text = prose(detail["接口设计"]).strip()
        no_interface_change = any(line.strip() in NO_INTERFACE_CHANGE_MARKERS for line in interface_text.splitlines())
        if no_interface_change and (interfaces or references["接口设计"] or
                                    any(lang is not None for lang, _ in detail["接口设计"]) or
                                    interface_text not in NO_INTERFACE_CHANGE_MARKERS):
            raise ValueError("接口不涉及变更的标记不能与接口定义、引用或变更说明混用")
        if not interfaces and not references["接口设计"] and interface_text not in NO_INTERFACE_CHANGE_MARKERS:
            raise ValueError("接口设计须以 HTTP 方法与路径或 RPC 签名为三级标题；无变更时明确说明")
        if any(line.strip() == NO_MODEL_CHANGE for line in prose(detail["数据模型"]).splitlines()) and (
                one_field(detail["数据模型"], "结构变更") != "无" or references["数据模型"]):
            raise ValueError("模型不涉及变更的标记不能与实际变更或共享设计引用混用")
        if not re.search(r"^- .*`[^`]+`.*[：:].+", prose(detail["代码改造点"]), re.M):
            raise ValueError(f"功能 {slug} 的改造点须定位代码并简述改动")
        if re.search(r"^### ", prose(detail["代码改造点"]), re.M):
            raise ValueError("功能文档的代码改造点直接列文件，不重复功能分类")
        features[slug] = dict(heading=heading, goal=content, path=relative, source=feature_source,
                              parts=feature_parts, sections=detail, dependencies=dependencies,
                              choice=choice, model_visible=visible, contracts=contracts, interfaces=interfaces, references=references)

    visited, visiting = set(), set()

    def visit(slug):
        if slug in visiting:
            raise ValueError("功能依赖不能成环")
        if slug in visited:
            return
        visiting.add(slug)
        for dependency in features[slug]["dependencies"]:
            visit(dependency)
        visiting.remove(slug)
        visited.add(slug)

    api_owners, contract_owners = {}, {}
    for slug, feature in features.items():
        visit(slug)
        for section, refs in feature["references"].items():
            for ref in refs:
                owner = features[ref]
                if Path(owner["path"]).parent != Path(feature["path"]).parent:
                    raise ValueError("引用必须指向同目录下的功能文档")
                if owner["references"][section]:
                    raise ValueError("共享设计须直接引用定义所属功能，不能链式引用")
                if section == "合约设计" and not owner["contracts"]:
                    raise ValueError("合约设计引用必须指向实际定义")
                if section == "数据模型" and one_field(owner["sections"][section], "结构变更") == "无":
                    raise ValueError("数据模型引用必须指向实际模型定义")
                if section == "接口设计" and not owner["interfaces"]:
                    raise ValueError("接口引用必须指向实际接口定义")
        for endpoint in feature["interfaces"]:
            if endpoint in api_owners:
                raise ValueError(f"接口 {endpoint} 重复定义；请引用所属功能")
            api_owners[endpoint] = slug
        for name in feature["contracts"]:
            if name in contract_owners:
                raise ValueError(f"合约 {name} 重复定义；请引用所属功能；不同合约同名时使用模块限定名")
            contract_owners[name] = slug
    return dict(source=source, title=title, features=features)


def execution_files(plan, bundle):
    return {plan.name: bundle["source"], **{item["path"]: item["source"] for item in bundle["features"].values()}}


def snapshot(plan, output):
    """Capture the validated index and feature sources, without review material."""
    bundle = validate(plan)
    files = execution_files(Path("plan.md"), bundle)
    output = output.resolve()
    if (output / "state.json").exists():
        raise ValueError("run 已有状态，不能覆盖；恢复时使用现有快照")
    for relative in files:
        target = output / relative
        if target.exists() or target.is_symlink() or target.parent.is_symlink():
            raise ValueError(f"run 已有计划文件，不能覆盖: {target}")
    output.mkdir(parents=True, exist_ok=True)
    for relative, source in files.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    print(output / "plan.md")


def review_sections(plan, bundle):
    """Aggregate feature documents without exposing routing or duplicating contracts."""
    _, review_parts, review_title, review = read_document(plan.with_suffix(".review.md"), REVIEW_SECTIONS, {"业务流程总览", "状态机"})
    if review_title != bundle["title"]:
        raise ValueError("审阅素材与执行计划标题必须一致")
    header = re.split(r"^## ", prose(review_parts), maxsplit=1, flags=re.M)[0]
    changes = re.findall(r"^- 业务流程变化：(.*)$", header, re.M)
    reasons = re.findall(r"^- 判定依据：(.*)$", header, re.M)
    if changes or reasons:
        if len(changes) != 1 or changes[0].strip() not in {"有", "无"} or len(reasons) != 1 or not reasons[0].strip():
            raise ValueError("审阅素材须记录唯一的业务流程变化判定（有/无）及非空判定依据")
        if changes[0].strip() == "有" and "业务流程总览" not in review:
            raise ValueError("业务流程有变化时必须提供业务流程总览")
    elif "业务流程总览" not in review:
        raise ValueError("省略业务流程总览前须明确记录业务流程无变化及判定依据")
    stories = [line.strip() for line in prose(review["背景"]).splitlines() if line.strip()]
    if (not stories or any(lang is not None for lang, _ in review["背景"])
            or any(not re.fullmatch(r"- User Story：\S.+", line) for line in stories)):
        raise ValueError("背景仅保留 User Story 列表，不按功能分类或重复目标与验收标准")
    for name in ("业务流程总览", "状态机"):
        if name in review and not any(lang and lang.lower() == "plantuml" for lang, _ in review[name]):
            raise ValueError(f"{name}必须包含 PlantUML 图")
    goals, contracts, models, sequences, interfaces, changes = [], [], [], [], [], []
    for item in bundle["features"].values():
        heading = (None, "### " + item["heading"])
        goals.extend([heading, *[(lang, re.sub(r"^- (?:文档|依赖)：.*$", "", body, flags=re.M)) for lang, body in item["goal"]]])
        detail = item["sections"]
        if item["contracts"]:
            contracts.extend(detail["合约设计"])
        if item["model_visible"]:
            models.extend(detail["数据模型"])
        if item["choice"] == "生成":
            sequences.extend([heading, *detail["功能时序图"]])
        for api_heading, api_content in item["interfaces"].values():
            interfaces.extend([(None, "### " + api_heading), *api_content])
        changes.extend([heading, *detail["代码改造点"]])
    result = {"背景": review["背景"], "功能目标": goals}
    if "业务流程总览" in review:
        result["业务流程总览"] = review["业务流程总览"]
    if "状态机" in review:
        result["状态机"] = review["状态机"]
    for name, content in (("合约设计", contracts), ("数据模型设计", models), ("功能时序图", sequences), ("接口设计", interfaces), ("代码改造点", changes)):
        if content:
            result[name] = content
    return result


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
    bundle = validate(plan)
    source, title = bundle["source"], bundle["title"]
    plan, output = plan.resolve(), output.resolve()
    if plan.parent.name != "plans" or plan.parent.parent.name != ".keel":
        raise ValueError("HTML 源计划必须位于 <project>/.keel/plans/")
    if output != plan.with_suffix(".html"):
        raise ValueError("HTML 必须与 Markdown 位于同目录且同名")
    sections, rendered, diagram_count = [], [], 0
    for name, content in review_sections(plan, bundle).items():
        sections.append(name)
        anchor = f'section-{len(sections)}'
        rendered.append(f'<section id="{anchor}"><h2>{html.escape(name)}</h2>')
        for lang, body in content:
            if lang is None:
                if name == "功能时序图":
                    body = re.sub(r"^- 时序图：(生成|不生成)\s*$", "", body, flags=re.M)
                if name in {"合约设计", "数据模型设计", "接口设计"}:
                    body = re.sub(r"^- (?:结构变更|引用)：.+$", "", body, flags=re.M)
                rendered.append(prose_html(body, []))
            elif lang.lower() == "plantuml":
                diagram_count += 1
                src = diagram_svg(body)
                rendered.append(f'<figure><div class="diagram"><img src="{src}" alt="{html.escape(name)} {diagram_count}" /></div>'
                                f'<details><summary>查看图表源码</summary>'
                                f'<pre><code>{html.escape(body)}</code></pre></details></figure>')
            else:
                rendered.append("<pre><code>" + html.escape(body) + "</code></pre>")
        rendered.append("</section>")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for relative, document in execution_files(plan, bundle).items():
            zipped.writestr(relative, document)
    page = template.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    if len(scripts) != 1:
        raise ValueError("HTML 模板必须包含唯一的主题切换脚本")
    replacements = {
        "TITLE": html.escape(title),
        "NAV": "\n".join(f'<a href="#section-{index}">{html.escape(name)}</a>' for index, name in enumerate(sections, 1)),
        "CONTENT": "\n".join(rendered),
        "SOURCE": html.escape(source),
        "SOURCE_BASE64": base64.b64encode(archive.getvalue()).decode("ascii"),
        "FILE_NAME": html.escape(plan.with_suffix(".zip").name, quote=True),
        "SCRIPT_HASH": base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii"),
    }
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
    capture = commands.add_parser("snapshot")
    capture.add_argument("plan", type=Path)
    capture.add_argument("output", type=Path)
    view = commands.add_parser("render")
    view.add_argument("plan", type=Path)
    view.add_argument("output", type=Path)
    view.add_argument("template", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate(args.plan)
        elif args.command == "snapshot":
            snapshot(args.plan, args.output)
        else:
            render(args.plan, args.output, args.template)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
