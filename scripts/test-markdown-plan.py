#!/usr/bin/env python3
"""Behavior checks for Markdown input, local diagrams, and atomic offline HTML."""
import base64
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("keel_plan", ROOT / "common/scripts/keel-plan.py")
plan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan_module)
TEMPLATE = ROOT / "keel-plan/skills/keel-plan/assets/plan-template.md"
HTML_TEMPLATE = ROOT / "keel-plan/skills/keel-plan/assets/plan-view-template.html"
RENDER = ROOT / "keel-plan/skills/keel-plan/scripts/render-plan-html.sh"
EXAMPLE = TEMPLATE.read_text()


def plain_plan():
    source = re.sub(r"```plantuml\n.*?\n```", "本节无业务状态机。", EXAMPLE, flags=re.S)
    start, end = source.index("## 功能时序图"), source.index("## 状态机调整")
    source = source[:start] + "## 功能时序图\n\n用户选择不生成时序图。\n\n" + source[end:]
    return source.replace("- 时序图：生成", "- 时序图：不生成").split("## 风险与恢复")[0]


class MarkdownPlanTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="keel-plan-test-")
        self.root = Path(self.work.name)
        self.directory = self.root / ".keel/plans"
        self.directory.mkdir(parents=True)
        self.plan = self.directory / "example.md"
        self.output = self.plan.with_suffix(".html")
        self.plan.write_text(plain_plan())

    def tearDown(self):
        self.work.cleanup()

    def run_render(self, success=True, env=None):
        result = subprocess.run(["bash", str(RENDER), str(self.plan), str(self.output)],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_example_contract(self):
        _, parts, _, choices = plan_module.validate(TEMPLATE)
        self.assertEqual(choices, {"cancel-order": "生成", "confirm-refund": "不生成"})
        self.assertEqual(sum(lang == "plantuml" for lang, _ in parts), 4)

    def test_plain_offline_html_and_exact_source(self):
        source = plain_plan() + '\n<script>alert("x")</script> **重点** `x < y` [来源](https://example.com)\n'
        self.plan.write_text(source)
        with patch.object(plan_module, "diagram_svg", side_effect=AssertionError("无图不应调用渲染器")):
            plan_module.render(self.plan, self.output, HTML_TEMPLATE)
        page = self.output.read_text()
        self.assertIn("<table>", page)
        self.assertIn("<strong>重点</strong>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertNotRegex(page, r'<(?:script|img)[^>]+src="https?://')
        encoded = re.search(r"data:text/markdown;charset=utf-8;base64,([^\"]+)", page)[1]
        self.assertEqual(base64.b64decode(encoded).decode(), source)
        self.assertNotIn("__KEEL_", page)

    def test_reject_incomplete_or_old_plans_without_overwrite(self):
        invalid = [
            "", "<plan><features /></plan>",
            plain_plan().replace("## 验证方案", "## 其他"),
            plain_plan().replace("- 验收标准：", "- 观察：", 1),
            plain_plan().replace("- 时序图：不生成", "- 时序图：生成", 1),
            plain_plan().replace("### confirm-refund", "### cancel-order"),
            plain_plan() + "\n```java\nunfinished",
            plain_plan() + "\nTBD\n",
            plain_plan().replace("## 验证方案", "```\n## 验证方案\n```"),
        ]
        for source in invalid:
            with self.subTest(source=source[:50]):
                self.plan.write_text(source)
                self.output.write_text("sentinel")
                self.run_render(success=False)
                self.assertEqual(self.output.read_text(), "sentinel")
                self.assertEqual(list(self.directory.glob(".keel-plan-html.*")), [])

    def test_unselected_and_missing_diagrams_rejected(self):
        for source in [
            EXAMPLE.replace("### cancel-order — 发起取消\n\n```", "### confirm-refund — 确认退款\n\n```"),
            EXAMPLE.replace("participant 退款网关 as Gateway", "!include /etc/passwd"),
            EXAMPLE.replace("@startuml", "@startuml\n!includeurl https://example.com", 1),
            EXAMPLE.replace("@startuml", "@startuml\n%getenv(\"HOME\")", 1),
        ]:
            self.plan.write_text(source)
            with self.assertRaises(ValueError):
                plan_module.validate(self.plan)

    def test_render_failures_keep_old_html(self):
        self.plan.write_text(EXAMPLE)
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

    def test_full_fast_initialization_single_plan(self):
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
        import json
        for mode in ("full", "fast"):
            state = json.loads((self.root / mode / "state.json").read_text())
            self.assertEqual(state["plan_path"], str(self.plan))
            self.assertNotIn("implementation_plan_path", state)
            self.assertEqual(set(state["review"]), {"qa"})
        self.assertFalse((self.root / "invalid").exists())

    @unittest.skipUnless(os.environ.get("KEEL_PLANTUML_JAR"), "set KEEL_PLANTUML_JAR for real diagram integration")
    def test_real_plantuml_and_syntax_failure(self):
        self.plan.write_text(EXAMPLE)
        self.run_render()
        page = self.output.read_text()
        images = re.findall(r'<img src="data:image/svg\+xml;base64,([^\"]+)"', page)
        self.assertEqual(len(images), 4)
        decoded = [base64.b64decode(data).decode() for data in images]
        self.assertTrue(all("<svg" in svg for svg in decoded))
        self.assertIn("REFUND_PENDING", "\n".join(decoded))
        for color in ("#DCFCE7", "#FEF3C7", "#FEE2E2"):
            self.assertIn(color, decoded[-1])
        self.assertNotIn("CANCELLING", decoded[2])
        self.plan.write_text(EXAMPLE.replace("actor 用户", "this is not valid PlantUML syntax !!!!"))
        self.run_render(success=False)
        self.assertEqual(self.output.read_text(), page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
