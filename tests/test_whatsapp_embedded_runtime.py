from __future__ import annotations

import ast
import tomllib
import unittest
from collections import defaultdict, deque
from pathlib import Path

from remax_bot.whatsapp_webengine import (
    EmbeddedWhatsAppBot,
    MAX_INTRO,
    MessageRouter,
    classify_command,
)


ROOT = Path(__file__).resolve().parents[1]


def snapshot(chat_id="group-1", title="Bot deneme", messages=None):
    return {
        "chat": {"id": chat_id, "title": title},
        "messages": list(messages or []),
    }


class FakePage:
    def __init__(self):
        self.responses = defaultdict(deque)
        self.fallback = deque()
        self.calls = []

    def add(self, script, *responses):
        self.responses[script].extend(responses)

    def add_any(self, *responses):
        self.fallback.extend(responses)

    def runJavaScript(self, script, callback=None):
        self.calls.append(script)
        values = self.responses[script]
        value = values.popleft() if values else (self.fallback.popleft() if self.fallback else None)
        if callback:
            callback(value)


class EmbeddedWhatsAppRuntimeTests(unittest.TestCase):
    def test_start_aliases_are_accepted(self):
        self.assertEqual(classify_command("#Max başla"), "start")
        self.assertEqual(classify_command("#MAX BAŞLAT"), "start")

    def test_existing_messages_are_primed_without_any_reply(self):
        router = MessageRouter(lambda text: f"Sonuç: {text}")

        result = router.process(
            snapshot(messages=[{"id": "old-1", "text": "#Max başlat"}])
        )

        self.assertEqual(result.replies, [])
        self.assertFalse(router.active)

    def test_dynamic_mode_locks_to_chat_where_start_arrived(self):
        router = MessageRouter(lambda text: f"Sonuç: {text}")
        router.process(snapshot())

        started = router.process(
            snapshot(messages=[{"id": "new-1", "text": "#Max başlat"}])
        )
        other_chat = router.process(snapshot("group-2", "Başka grup"))

        self.assertEqual(started.replies, [MAX_INTRO])
        self.assertTrue(router.active)
        self.assertEqual(router.locked_chat_title, "Bot deneme")
        self.assertEqual(other_chat.open_group, "Bot deneme")

    def test_configured_group_has_priority_over_other_chats(self):
        router = MessageRouter(lambda text: f"Sonuç: {text}")
        router.set_group("RE/MAX ÇARŞI")

        result = router.process(snapshot("other", "Bot deneme"))

        self.assertEqual(result.replies, [])
        self.assertEqual(result.open_group, "RE/MAX ÇARŞI")
        self.assertFalse(router.active)

    def test_same_message_id_is_answered_only_once(self):
        router = MessageRouter(lambda text: f"Sonuç: {text}")
        router.process(snapshot())
        router.process(snapshot(messages=[{"id": "start-1", "text": "#Max başla"}]))
        command = {"id": "query-1", "text": "#izmit kiralık 55 bin"}

        first = router.process(snapshot(messages=[command]))
        second = router.process(snapshot(messages=[command]))

        self.assertEqual(first.replies, ["Max: Sonuç: #izmit kiralık 55 bin"])
        self.assertEqual(second.replies, [])

    def test_bot_output_containing_hash_is_ignored(self):
        router = MessageRouter(lambda text: f"Sonuç: {text}")
        router.process(snapshot())
        router.process(snapshot(messages=[{"id": "start-1", "text": "#Max başla"}]))

        result = router.process(
            snapshot(messages=[{"id": "bot-1", "text": MAX_INTRO}])
        )

        self.assertEqual(result.replies, [])

    def test_save_group_immediately_opens_it_inside_embedded_page(self):
        page = FakePage()
        page.add_any(True, True)
        bot = EmbeddedWhatsAppBot(lambda _text: "", page=page, schedule=lambda _ms, fn: fn())

        bot.set_group("  Bot deneme  ")

        self.assertEqual(bot.router.configured_group, "Bot deneme")
        self.assertEqual(len(page.calls), 2)
        self.assertTrue(all('"Bot deneme"' in script for script in page.calls))

    def test_configured_group_retries_after_whatsapp_page_becomes_ready(self):
        page = FakePage()
        page.add_any(False, False)
        bot = EmbeddedWhatsAppBot(lambda _text: "", page=page, schedule=lambda _ms, fn: fn())

        bot.start("Bot deneme")
        bot._on_snapshot(None)

        search_calls = [script for script in page.calls if 'const wanted="Bot deneme"' in script]
        self.assertGreaterEqual(len(search_calls), 2)

    def test_send_is_emitted_once_only_after_real_send_button_clears_draft(self):
        page = FakePage()
        page.add_any(True)
        page.add(EmbeddedWhatsAppBot.CLICK_SEND_JS, True)
        page.add(EmbeddedWhatsAppBot.COMPOSER_EMPTY_JS, True)
        bot = EmbeddedWhatsAppBot(lambda _text: "", page=page, schedule=lambda _ms, fn: fn())
        sent = []
        bot.sent.connect(lambda _channel, text: sent.append(text))

        bot._send("Max: Tek cevap")

        self.assertEqual(sent, ["Max: Tek cevap"])
        self.assertNotIn(EmbeddedWhatsAppBot.CLEAR_COMPOSER_JS, page.calls)

    def test_failed_send_clears_draft_and_never_reports_sent(self):
        page = FakePage()
        page.add_any(True)
        page.add(EmbeddedWhatsAppBot.CLICK_SEND_JS, False, False, False, False)
        page.add(EmbeddedWhatsAppBot.CLEAR_COMPOSER_JS, True)
        bot = EmbeddedWhatsAppBot(lambda _text: "", page=page, schedule=lambda _ms, fn: fn())
        sent = []
        bot.sent.connect(lambda _channel, text: sent.append(text))

        bot._send("Max: Gönderilemeyen cevap")

        self.assertEqual(sent, [])
        self.assertIn(EmbeddedWhatsAppBot.CLEAR_COMPOSER_JS, page.calls)

    def test_application_wires_the_visible_whatsapp_page_into_bot(self):
        tree = ast.parse((ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "whatsapp_webengine"
            for alias in node.names
        }
        constructors = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EmbeddedWhatsAppBot"
        ]

        self.assertIn("EmbeddedWhatsAppBot", imported)
        self.assertEqual(len(constructors), 1)
        self.assertIn("page", {keyword.arg for keyword in constructors[0].keywords})

    def test_runtime_and_build_no_longer_depend_on_selenium(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")

        self.assertFalse(any("selenium" in item.casefold() for item in project["project"]["dependencies"]))
        self.assertNotIn("selenium", workflow.casefold())


if __name__ == "__main__":
    unittest.main()
