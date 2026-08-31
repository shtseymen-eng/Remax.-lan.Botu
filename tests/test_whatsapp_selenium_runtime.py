from __future__ import annotations

import ast
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from remax_bot import __version__
from remax_bot.whatsapp_selenium import SeleniumWhatsAppBot


ROOT = Path(__file__).resolve().parents[1]


class _NoopThread:
    def __init__(self, *args, **kwargs):
        self.started = False

    def start(self):
        self.started = True


class _GroupDriver:
    def __init__(self):
        self.calls = []
        self.results = [True, True]

    def execute_script(self, script, *args):
        self.calls.append((script, args))
        return self.results.pop(0)


class _MessageDriver:
    def __init__(self):
        self.rows = []

    def execute_script(self, _script, *args):
        return list(self.rows)


class WhatsAppRuntimeTests(unittest.TestCase):
    def test_browser_scripts_normalize_whitespace(self):
        self.assertIn(r"replace(/\s+/g", SeleniumWhatsAppBot.OPEN_GROUP_JS)
        self.assertIn(r"replace(/\s+/g", SeleniumWhatsAppBot.JS_READ)

    def test_start_remembers_group_for_automatic_open(self):
        bot = SeleniumWhatsAppBot(lambda _text: "")
        with patch("remax_bot.whatsapp_selenium.threading.Thread", _NoopThread):
            bot.start("  RE/MAX ÇARŞI  ")
        self.assertEqual(bot.group, "RE/MAX ÇARŞI")

    def test_open_group_searches_and_clicks_the_exact_chat(self):
        bot = SeleniumWhatsAppBot(lambda _text: "")
        bot.driver = _GroupDriver()

        opened = bot._open_group("RE/MAX ÇARŞI", timeout_seconds=0)

        self.assertTrue(opened)
        self.assertEqual([call[1] for call in bot.driver.calls], [("RE/MAX ÇARŞI",), ("RE/MAX ÇARŞI",)])

    def test_start_command_and_query_are_read_and_answered(self):
        bot = SeleniumWhatsAppBot(lambda text: f"Sonuç: {text}")
        bot.driver = _MessageDriver()
        sent = []
        bot._send = sent.append

        bot.driver.rows = [{"id": "1", "text": "#Max başla", "outgoing": True}]
        bot._poll()
        bot.driver.rows = [{"id": "2", "text": "#izmit kiralık 3+1#", "outgoing": False}]
        bot._poll()

        self.assertTrue(bot.active)
        self.assertEqual(sent[0], "Max: Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. Komut listesini görmek için #? yazabilirsiniz.")
        self.assertEqual(sent[1], "Max: Sonuç: #izmit kiralık 3+1#")

    def test_application_wires_the_selenium_engine(self):
        tree = ast.parse((ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "whatsapp_selenium"
            for alias in node.names
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("SeleniumWhatsAppBot", imported)
        self.assertIn("SeleniumWhatsAppBot", calls)

    def test_package_version_is_consistent(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(__version__, project["project"]["version"])
        app_source = (ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8")
        self.assertIn("__version__", app_source)

    def test_both_builds_bundle_selenium(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("--hidden-import selenium"), 2)
        self.assertGreaterEqual(workflow.count("--collect-all selenium"), 2)


if __name__ == "__main__":
    unittest.main()
