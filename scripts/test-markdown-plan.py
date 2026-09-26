#!/usr/bin/env python3
"""Behavior checks for split execution input, portable snapshots and offline review."""
import base64
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("keel_plan", ROOT / "common/scripts/keel-plan.py")
plan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan_module)
ASSETS = ROOT / "keel-plan/skills/keel-plan/assets"
HTML_TEMPLATE = ASSETS / "plan-view-template.html"
RENDER = ROOT / "keel-plan/skills/keel-plan/scripts/render-plan-html.sh"
EXAMPLE = (ASSETS / "plan-template.md").read_text().replace("plan-template.features/", "example.features/")
REVIEW = (ASSETS / "plan-review-template.md").read_text()
FEATURES = {p.stem: p.read_text() for p in (ASSETS / "plan-template.features").glob("*.md")}
SVG = "data:image/svg+xml;base64," + base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>').decode()


def replace_section(source, name, content):
    return re.sub(rf"(^## {name}\n).*?(?=^## |\Z)", lambda m: m[1] + "\n" + content.strip() + "\n\n", source, flags=re.M | re.S)


def section(source, name):
    return re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", source, re.M | re.S)[1].strip()


class ContentReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = None
        self.headings = []
        self.items = []
        self.item = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self.heading = ""
        if tag == "li":
            self.item = ""

    def handle_data(self, data):
        if self.heading is not None:
            self.heading += data
        if self.item is not None:
            self.item += data

    def handle_endtag(self, tag):
        if tag == "h2":
            self.headings.append(self.heading)
            self.heading = None
        if tag == "li":
            self.items.append(self.item)
            self.item = None


class MarkdownPlanTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="keel-plan-test-")
        self.root = Path(self.work.name).resolve()
        self.directory = self.root / ".keel/plans"
        self.directory.mkdir(parents=True)
        self.plan = self.directory / "example.md"
        self.review = self.plan.with_suffix(".review.md")
        self.output = self.plan.with_suffix(".html")
        self.plan.write_text(EXAMPLE)
        self.review.write_text(REVIEW)
        self.features = self.directory / "example.features"
        self.features.mkdir()
        for slug, source in FEATURES.items():
            self.feature(slug).write_text(source)

    def tearDown(self):
        self.work.cleanup()

    def feature(self, slug="cancel-order"):
        return self.features / (slug + ".md")

    def render(self):
        with patch.object(plan_module, "diagram_svg", return_value=SVG) as diagram:
            plan_module.render(self.plan, self.output, HTML_TEMPLATE)
        return self.output.read_text(), diagram.call_count

    def assert_rejected(self):
        self.output.write_text("sentinel")
        with patch.object(plan_module, "diagram_svg", return_value=SVG), self.assertRaises(ValueError):
            plan_module.render(self.plan, self.output, HTML_TEMPLATE)
        self.assertEqual(self.output.read_text(), "sentinel")
        self.assertEqual(list(self.directory.glob(".keel-plan-html.*")), [])

    def make_plain(self):
        for slug, original in FEATURES.items():
            source = replace_section(original, "数据模型", "- 结构变更：无")
            source = replace_section(source, "功能时序图", "- 时序图：不生成")
            source = replace_section(source, "接口设计", "本功能无接口变更。")
            self.feature(slug).write_text(source)
        self.review.write_text(REVIEW.split("## 状态机")[0])

    def test_index_routes_to_independent_four_part_features_without_review(self):
        self.review.unlink()
        bundle = plan_module.validate(self.plan)
        self.assertEqual(list(plan_module.section_blocks(plan_module.blocks(EXAMPLE))), ["功能目标"])
        self.assertNotIn("```", EXAMPLE)
        self.assertNotIn("POST", EXAMPLE)
        self.assertEqual(set(bundle["features"]), {"cancel-order", "confirm-refund"})
        for slug, item in bundle["features"].items():
            self.assertEqual(list(item["sections"]), ["数据模型", "功能时序图", "接口设计", "代码改造点"])
            self.assertNotIn("验收标准", item["source"])
            self.assertNotIn("## 功能目标", item["source"])
        self.assertNotIn("/refunds/callback", FEATURES["cancel-order"])
        self.assertNotIn("/orders/{id}/cancel", FEATURES["confirm-refund"])
        self.assertIn("POST `/refunds/callback`", section(FEATURES["confirm-refund"], "接口设计"))
        self.assertNotIn("```plantuml", section(FEATURES["confirm-refund"], "功能时序图"))
        self.assertEqual(bundle["features"]["confirm-refund"]["references"]["数据模型"], ["cancel-order"])

    def test_combined_review_preserves_approved_sections_and_lists(self):
        page, count = self.render()
        reader = ContentReader()
        reader.feed(page)
        self.assertEqual(reader.headings, ["背景", "功能目标", "业务流程总览", "状态机", "数据模型设计", "功能时序图", "接口设计", "代码改造点"])
        self.assertEqual(count, 4)
        self.assertIn("重复成功回调不重复更新订单或发送通知。", reader.items)
        article = page.split('<article id="plan-content">')[1].split("</article>")[0]
        background = article.split("<h2>背景</h2>")[1].split("</section>")[0]
        goals = article.split("<h2>功能目标</h2>")[1].split("</section>")[0]
        self.assertIn("作为购买者", background)
        for unwanted in ("<h3>", "cancel-order", "验收标准", "目标："):
            self.assertNotIn(unwanted, background)
        self.assertIn("验收标准", goals)
        for detail in ("User Story", "HTTP", "POST", "Idempotency-Key", "事务", "403", "401", "文档：", "依赖：", ".md"):
            self.assertNotIn(detail, goals)
        interfaces = article.split("<h2>接口设计</h2>")[1].split("</section>")[0]
        self.assertIn("<h3>POST <code>/orders/{id}/cancel</code></h3>", interfaces)
        self.assertIn("/refunds/callback", interfaces)
        for feature_label in ("cancel-order", "confirm-refund", "发起取消", "确认退款"):
            self.assertNotIn(feature_label, interfaces)
        sequences = article.split("<h2>功能时序图</h2>")[1].split("</section>")[0]
        self.assertNotIn("confirm-refund", sequences)
        self.assertNotIn("执行说明（不生成时序图）", sequences)
        self.assertEqual(article.count("ALTER TABLE orders"), 1)
        for unwanted in ("时序图：生成", "结构变更：", "引用：", "其他必要说明", "__KEEL_"):
            self.assertNotIn(unwanted, article)
        for anchor in re.findall(r'href="#([^\"]+)"', page):
            self.assertIn(f'id="{anchor}"', page)

    def test_download_contains_exact_portable_index_and_all_feature_sources(self):
        page, _ = self.render()
        encoded = re.search(r'data:application/zip;base64,([^\"]+)', page)[1]
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as archive:
            expected = {"example.md": EXAMPLE, **{f"example.features/{slug}.md": source for slug, source in FEATURES.items()}}
            self.assertEqual(set(archive.namelist()), set(expected))
            for path, source in expected.items():
                self.assertEqual(archive.read(path).decode(), source)
            archive.extractall(self.root / "download")
        plan_module.validate(self.root / "download/example.md")
        self.assertNotIn("data:text/markdown", page)

    def test_goal_and_interface_edits_propagate_without_editing_review(self):
        self.plan.write_text(EXAMPLE.replace("首次取消由 PAID", "新的验收结果：首次取消由 PAID"))
        self.feature().write_text(FEATURES["cancel-order"].replace("退款请求 ID |", "可追踪的退款编号 |"))
        page, _ = self.render()
        article = page.split("</article>")[0]
        self.assertEqual(article.count("新的验收结果"), 1)
        self.assertEqual(article.count("可追踪的退款编号"), 1)
        self.assertEqual(self.review.read_text(), REVIEW)
        self.assertNotIn("## 接口设计", REVIEW)

    def test_optional_sections_hidden_and_stories_need_not_match_feature_count(self):
        self.make_plain()
        source = self.review.read_text()
        source = re.sub(r"- User Story：.*\n", "", source, count=1)
        self.review.write_text(source)
        page, count = self.render()
        reader = ContentReader()
        reader.feed(page)
        self.assertEqual(reader.headings, ["背景", "功能目标", "业务流程总览", "代码改造点"])
        self.assertEqual(count, 1)

    def test_other_sql_is_retained_without_model_review(self):
        self.make_plain()
        model = "- 结构变更：其他调整\n\n```sql\nCREATE INDEX idx_order_status ON orders(status);\n```"
        self.feature().write_text(replace_section(self.feature().read_text(), "数据模型", model))
        page, _ = self.render()
        self.assertNotIn("数据模型设计", page)
        self.assertNotIn("CREATE INDEX", page.split("</article>")[0])
        self.assertIn("CREATE INDEX", self.feature().read_text())

    def test_new_table_or_field_displays_model(self):
        for kind in ("新增表", "新增字段", "新增表、新增字段"):
            with self.subTest(kind=kind):
                self.feature().write_text(FEATURES["cancel-order"].replace("结构变更：新增字段", "结构变更：" + kind))
                page, count = self.render()
                self.assertIn("<h2>数据模型设计</h2>", page)
                self.assertEqual(count, 4)

    def test_incomplete_model_rejected(self):
        source = FEATURES["cancel-order"]
        model = section(source, "数据模型")
        for bad in (model.replace("新增字段", "未知类型", 1),
                    re.sub(r"```plantuml\n.*?```", "", model, flags=re.S),
                    re.sub(r"```sql\n.*?```", "", model, flags=re.S),
                    model.replace("- 结构变更：新增字段", ""),
                    model.replace("- 结构变更：新增字段", "- 结构变更：无")):
            with self.subTest(model=bad[:60]):
                self.feature().write_text(replace_section(source, "数据模型", bad))
                self.assert_rejected()

    def test_html_escapes_all_sources(self):
        self.feature().write_text(FEATURES["cancel-order"] + '\n<script>alert("x")</script> **重点** `x < y` [来源](https://example.com)\n')
        self.review.write_text(REVIEW.replace("作为购买者", '<img src="https://example.com/x">作为购买者', 1))
        page, _ = self.render()
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img", page)
        self.assertIn("<strong>重点</strong>", page)
        self.assertNotRegex(page, r'<(?:script|img)[^>]+src="https?://')
        self.assertNotIn('<script>alert("x")</script>', page)

    def test_rpc_and_shared_interface_single_definition(self):
        rpc = '### RPC `OrderService.cancel(CancelRequest)`\n\n入参新增 reason，String，选填。\n\n```json\n{"reason":"用户取消"}\n```'
        self.feature().write_text(replace_section(FEATURES["cancel-order"], "接口设计", rpc))
        self.feature("confirm-refund").write_text(replace_section(FEATURES["confirm-refund"], "接口设计", rpc))
        self.assert_rejected()
        self.feature("confirm-refund").write_text(replace_section(FEATURES["confirm-refund"], "接口设计", "- 引用：[cancel-order](cancel-order.md#接口设计)"))
        page, _ = self.render()
        interface = page.split("<h2>接口设计</h2>")[1].split("</section>")[0]
        self.assertEqual(interface.count("<h3>RPC <code>OrderService.cancel(CancelRequest)</code></h3>"), 1)
        self.assertNotIn("<table>", interface)

    def test_shared_reference_after_endpoint_is_hidden_in_html(self):
        source = FEATURES["cancel-order"]
        api = section(source, "接口设计") + "\n\n- 引用：[confirm-refund](confirm-refund.md#接口设计)"
        self.feature().write_text(replace_section(source, "接口设计", api))
        page, _ = self.render()
        interface = page.split("<h2>接口设计</h2>")[1].split("</section>")[0]
        self.assertNotIn("引用：", interface)
        self.assertNotIn("confirm-refund", interface)
        self.assertIn("/refunds/callback", interface)

    def test_reject_incomplete_old_or_ambiguous_index(self):
        invalid = ["", "<plan><features /></plan>",
                   EXAMPLE.replace("## 功能目标", "## 本次功能目标"),
                   EXAMPLE.replace("验收标准：", "观察：", 1),
                   EXAMPLE.replace("验收标准：\n\n- ", "验收标准：", 1),
                   EXAMPLE.replace("### confirm-refund", "### cancel-order"),
                   EXAMPLE.replace("- 目标：", "- 想法：", 1),
                   EXAMPLE.replace("- 文档：", "- 文件：", 1),
                   EXAMPLE.replace("- 依赖：无", "- 依赖：unknown"),
                   EXAMPLE.replace("- 依赖：无", "- 依赖：cancel-order"),
                   EXAMPLE.replace("- 依赖：无", "- 依赖：confirm-refund"),
                   EXAMPLE + "\n## 数据模型\n旧的整份计划\n",
                   EXAMPLE + "\n```java\nunfinished", EXAMPLE + "\nTBD\n"]
        for bad in invalid:
            with self.subTest(source=bad[:70]):
                self.plan.write_text(bad)
                self.assert_rejected()

    def test_feature_file_missing_wrong_title_or_incomplete_section(self):
        self.feature().unlink()
        self.assert_rejected()
        source = FEATURES["cancel-order"]
        for bad in (source.replace("# cancel-order — 发起取消", "# wrong — 其他功能", 1),
                    source.replace("## 接口设计", "## 功能目标"),
                    source.replace("- 时序图：生成", "- 时序图：不生成"),
                    source.replace("### POST `/orders/{id}/cancel`", "### cancel-order — 发起取消"),
                    replace_section(source, "接口设计", ""),
                    replace_section(source, "代码改造点", "改代码")):
            with self.subTest(source=bad[:80]):
                self.feature().write_text(bad)
                self.assert_rejected()

    def test_paths_and_shared_references_must_resolve_within_bundle(self):
        for path in ("../cancel-order.md", "/tmp/cancel-order.md", "https://example.com/cancel-order.md", "example.features/../cancel-order.md"):
            with self.subTest(path=path):
                self.plan.write_text(EXAMPLE.replace("example.features/cancel-order.md", path))
                self.assert_rejected()
        self.plan.write_text(EXAMPLE)
        source = FEATURES["confirm-refund"]
        for bad in (source.replace("cancel-order.md#数据模型", "cancel-order.md#接口设计"),
                    source.replace("[cancel-order](cancel-order.md", "[missing](missing.md"),
                    source.replace("[cancel-order](cancel-order.md", "[confirm-refund](confirm-refund.md")):
            self.feature("confirm-refund").write_text(bad)
            self.assert_rejected()
        self.feature("confirm-refund").write_text(source)
        self.feature().write_text(replace_section(FEATURES["cancel-order"], "数据模型", "- 结构变更：无"))
        self.assert_rejected()
        self.feature().write_text(replace_section(FEATURES["cancel-order"], "数据模型", "- 结构变更：无\n- 引用：[confirm-refund](confirm-refund.md#数据模型)"))
        self.assert_rejected()
        self.feature().unlink()
        self.feature().symlink_to(ASSETS / "plan-template.features/cancel-order.md")
        self.assert_rejected()

    def test_missing_or_inconsistent_review_rejected(self):
        self.review.unlink()
        self.assert_rejected()
        for bad in (REVIEW.replace("# 订单取消支持退款确认", "# 其他需求", 1),
                    REVIEW.replace("- User Story：", "- 引用：", 1),
                    REVIEW.replace("## 业务流程总览", "## 其他说明"),
                    REVIEW.replace("## 背景\n", "## 背景\n\n### cancel-order — 发起取消\n", 1),
                    REVIEW + "\nTODO\n", REVIEW + "\n## 接口设计\n旧的重复契约\n",
                    re.sub(r"(## 业务流程总览.*?)```plantuml\n.*?```", r"\1", REVIEW, count=1, flags=re.S),
                    re.sub(r"(## 状态机.*?)```plantuml\n.*?```", r"\1", REVIEW, count=1, flags=re.S)):
            self.review.write_text(bad)
            self.assert_rejected()

    def test_external_diagram_resources_rejected_in_any_source(self):
        for resource in ('!include /etc/passwd', '!includeurl https://example.com', '%getenv("HOME")', '<img:https://example.com/x>'):
            for target, original in ((self.feature(), FEATURES["cancel-order"]), (self.review, REVIEW)):
                with self.subTest(resource=resource, target=target.name):
                    self.feature().write_text(FEATURES["cancel-order"])
                    self.review.write_text(REVIEW)
                    target.write_text(original.replace("@startuml", "@startuml\n" + resource, 1))
                    self.assert_rejected()

    def test_render_failures_keep_old_html(self):
        self.output.write_text("sentinel")
        with patch.dict(os.environ, {}, clear=True), patch.object(plan_module.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "需要本地"):
                plan_module.render(self.plan, self.output, HTML_TEMPLATE)
        with patch.object(plan_module, "diagram_svg", side_effect=ValueError("图语法错误")):
            with self.assertRaisesRegex(ValueError, "图语法错误"):
                plan_module.render(self.plan, self.output, HTML_TEMPLATE)
        self.assertEqual(self.output.read_text(), "sentinel")
        self.assertEqual(list(self.directory.glob(".keel-plan-html.*")), [])

    def test_wrong_output_path(self):
        with self.assertRaisesRegex(ValueError, "同目录且同名"):
            plan_module.render(self.plan, self.directory / "wrong.html", HTML_TEMPLATE)

    def test_full_fast_initialization_snapshots_only_execution_files(self):
        self.review.unlink()
        env = dict(os.environ, PROJECT_DIR=str(self.root))
        command = '''
set -euo pipefail
source "$1/common/scripts/keel-init.sh"
init_keel_run "$PROJECT_DIR/full" "$PROJECT_DIR/.keel/plans/example.md" >/dev/null
init_keel_fast_run "$PROJECT_DIR/fast" "$PROJECT_DIR/.keel/plans/example.md" >/dev/null
if init_keel_run "$PROJECT_DIR/invalid" "$PROJECT_DIR/missing.md"; then exit 1; fi
if init_keel_run "$PROJECT_DIR/invalid" "$PROJECT_DIR/.keel/plans/example.md" extra.md; then exit 1; fi
'''
        result = subprocess.run(["bash", "-c", command, "test", str(ROOT)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Delete the original bundle: both runs must remain self-contained.
        shutil.rmtree(self.directory)
        for mode in ("full", "fast"):
            run = self.root / mode
            state = json.loads((run / "state.json").read_text())
            self.assertEqual(state["plan_path"], str(run / "plan.md"))
            self.assertNotIn("implementation_plan_path", state)
            self.assertEqual(set(state["review"]), {"qa"})
            self.assertEqual((run / "plan.md").read_text(), EXAMPLE)
            plan_module.validate(run / "plan.md")
            for slug, source in FEATURES.items():
                self.assertEqual((run / "example.features" / (slug + ".md")).read_text(), source)
            self.assertFalse(list(run.rglob("*.review.md")))
        self.assertFalse((self.root / "invalid").exists())

    def test_snapshot_rejects_missing_input_and_existing_snapshot(self):
        output = self.root / "run"
        self.feature().unlink()
        with self.assertRaises(ValueError):
            plan_module.snapshot(self.plan, output)
        self.assertFalse(output.exists())
        self.feature().write_text(FEATURES["cancel-order"])
        plan_module.snapshot(self.plan, output)
        before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*.md")}
        self.plan.write_text(EXAMPLE.replace("支持已支付", "新版本支持已支付"))
        with self.assertRaisesRegex(ValueError, "不能覆盖"):
            plan_module.snapshot(self.plan, output)
        self.assertEqual(before, {p.relative_to(output): p.read_bytes() for p in output.rglob("*.md")})

    def test_review_or_feature_is_not_an_index(self):
        for path in (self.review, self.feature()):
            result = subprocess.run([sys.executable, str(ROOT / "common/scripts/keel-plan.py"), "validate", str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("章节", result.stderr)

    @unittest.skipUnless(os.environ.get("KEEL_PLANTUML_JAR") or shutil.which("plantuml"), "local PlantUML required for real diagram integration")
    def test_real_diagrams_and_syntax_failure(self):
        result = subprocess.run(["bash", str(RENDER), str(self.plan), str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.output.read_text()
        images = re.findall(r'<img src="data:image/svg\+xml;base64,([^\"]+)"', page)
        self.assertEqual(len(images), 4)
        decoded = [base64.b64decode(data).decode() for data in images]
        self.assertTrue(all("<svg" in svg for svg in decoded))
        self.assertIn("refund_requested_at", decoded[2])
        self.assertIn("refund_tasks", decoded[2])
        for color in ("#DCFCE7", "#DBEAFE", "#FEE2E2"):
            self.assertIn(color, decoded[1])
        self.assertIn("本期删除", decoded[1])
        self.review.write_text(REVIEW.replace("start\n", "this is not valid PlantUML syntax !!!!\n", 1))
        result = subprocess.run(["bash", str(RENDER), str(self.plan), str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
