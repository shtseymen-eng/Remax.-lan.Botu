from __future__ import annotations

import importlib
import importlib.util
import threading

from remax_bot.whatsapp_webengine import MAX_INTRO


class FakeWhatsAppSession:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.sent = []
        self.opened = []

    def snapshot(self):
        return self.snapshots.pop(0)

    def send(self, message):
        self.sent.append(message)
        return True

    def open_group(self, group):
        self.opened.append(group)
        return True


class FlakyWhatsAppSession(FakeWhatsAppSession):
    def __init__(self, snapshots, send_results):
        super().__init__(snapshots)
        self.send_results = list(send_results)
        self.send_attempts = 0

    def send(self, message):
        self.send_attempts += 1
        ok = self.send_results.pop(0)
        if ok:
            self.sent.append(message)
        return ok


class FakeComposer:
    def __init__(self, page):
        self.page = page

    def count(self):
        return 1

    def last(self):
        return self

    def is_visible(self):
        return True

    def fill(self, message):
        self.page.draft = message

    def press(self, key):
        if key == "Enter":
            self.page.sent.append(self.page.draft)
            self.page.draft = ""


class FakeBrowserPage:
    def __init__(self, fallback_snapshot):
        self.fallback_snapshot = fallback_snapshot
        self.draft = "eski taslak"
        self.sent = []
        self.evaluate_calls = 0

    def evaluate(self, _script):
        self.evaluate_calls += 1
        return None if self.evaluate_calls == 1 else self.fallback_snapshot

    def locator(self, _selector):
        return FakeComposer(self)


class FakeGroupControl:
    def __init__(self, page, kind, text=""):
        self.page = page
        self.kind = kind
        self.text = text

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def count(self):
        return 1

    def is_visible(self):
        return True

    def fill(self, value):
        self.page.search_value = value

    def get_by_text(self, text, exact=False):
        assert exact is True
        return FakeGroupControl(self.page, "result", text)

    def click(self):
        if self.kind == "result" and self.text == self.page.search_value:
            self.page.current_chat = self.text


class FakeGroupPage:
    def __init__(self):
        self.search_value = ""
        self.current_chat = ""

    def locator(self, selector):
        kind = "side" if selector == "#pane-side" else "search"
        return FakeGroupControl(self, kind)

    def wait_for_timeout(self, _milliseconds):
        pass


class EmptyLocator:
    def count(self):
        return 0


class FakeCompatibilityGroupPage:
    def __init__(self):
        self.search_value = ""
        self.current_chat = ""

    def locator(self, _selector):
        return EmptyLocator()

    def evaluate(self, script):
        if "document.execCommand('insertText'" in script:
            self.search_value = "Max deneme"
            return True
        if "const nodes=Array.from" in script:
            self.current_chat = "Max deneme"
            return True
        return False

    def wait_for_timeout(self, _milliseconds):
        pass


def snapshot(*messages, title="Max deneme"):
    return {
        "chat": {"id": "chat-1", "title": title, "identified": True},
        "messages": list(messages),
    }


def load_runtime():
    spec = importlib.util.find_spec("remax_bot.whatsapp_playwright")
    assert spec is not None, "Dış Chromium WhatsApp okuyucusu henüz yok"
    return importlib.import_module("remax_bot.whatsapp_playwright")


def test_activation_ignores_history_then_answers_a_new_command_from_any_sender():
    runtime = load_runtime()
    old = {"id": "old", "text": "#max başla"}
    own_new = {"id": "new", "text": "#max başla", "outgoing": True}
    session = FakeWhatsAppSession([
        snapshot(old),
        snapshot(old, own_new),
    ])
    loop = runtime.WhatsAppConversationLoop(lambda _text: "unused", session)

    loop.start(activate=True)
    loop.tick()
    assert session.sent == []

    loop.tick()
    assert session.sent == [MAX_INTRO]


def test_configured_group_is_opened_before_processing_another_chat():
    runtime = load_runtime()
    session = FakeWhatsAppSession([
        snapshot({"id": "new", "text": "#max başla"}, title="Yanlış grup")
    ])
    loop = runtime.WhatsAppConversationLoop(
        lambda _text: "unused", session, initial_group="Max deneme"
    )

    loop.start(activate=True)
    loop.tick()

    assert session.opened == ["Max deneme"]
    assert session.sent == []


def test_activation_waits_until_a_real_conversation_is_visible():
    runtime = load_runtime()
    session = FakeWhatsAppSession([
        {
            "chat": {
                "id": "open-chat",
                "title": "Açık sohbet",
                "identified": False,
            },
            "messages": [],
        }
    ])
    loop = runtime.WhatsAppConversationLoop(lambda _text: "unused", session)

    loop.start(activate=True)
    loop.tick()

    assert loop.active is False


def test_saved_group_is_opened_even_when_no_conversation_is_currently_visible():
    runtime = load_runtime()
    placeholder = {
        "chat": {"id": "open-chat", "title": "Açık sohbet", "identified": False},
        "messages": [],
    }
    session = FakeWhatsAppSession([placeholder])
    loop = runtime.WhatsAppConversationLoop(
        lambda _text: "unused", session, initial_group="Max deneme"
    )

    loop.start(activate=False)
    loop.tick()

    assert session.opened == ["Max deneme"]


def test_a_reply_is_retried_after_the_composer_is_temporarily_unavailable():
    runtime = load_runtime()
    new_command = {"id": "new", "text": "#max başla"}
    session = FlakyWhatsAppSession(
        [snapshot(), snapshot(new_command), snapshot(new_command)],
        send_results=[False, True],
    )
    loop = runtime.WhatsAppConversationLoop(lambda _text: "unused", session)

    loop.start(activate=False)
    loop.tick()
    loop.tick()
    assert session.sent == []

    loop.tick()
    assert session.sent == [MAX_INTRO]
    assert session.send_attempts == 2


def test_reactivation_discards_a_reply_queued_before_the_new_baseline():
    runtime = load_runtime()
    old_command = {"id": "old", "text": "#max başla"}
    session = FlakyWhatsAppSession(
        [snapshot(), snapshot(old_command), snapshot(old_command)],
        send_results=[False, True],
    )
    loop = runtime.WhatsAppConversationLoop(lambda _text: "unused", session)

    loop.start(activate=False)
    loop.tick()
    loop.tick()
    assert session.send_attempts == 1

    loop.start(activate=True)
    loop.tick()

    assert session.sent == []
    assert session.send_attempts == 1


def test_browser_session_falls_back_to_compatibility_scan_when_primary_scan_is_empty():
    runtime = load_runtime()
    wanted = snapshot({"id": "new", "text": "#max başla"})
    page = FakeBrowserPage(wanted)
    session = runtime.PlaywrightWhatsAppSession(page)

    assert session.snapshot() == wanted


def test_browser_session_replaces_a_draft_and_sends_with_a_real_enter_key():
    runtime = load_runtime()
    page = FakeBrowserPage(snapshot())
    session = runtime.PlaywrightWhatsAppSession(page)

    assert session.send("Max: Merhaba") is True
    assert page.sent == ["Max: Merhaba"]
    assert page.draft == ""


def test_browser_session_searches_and_opens_the_saved_group():
    runtime = load_runtime()
    page = FakeGroupPage()
    session = runtime.PlaywrightWhatsAppSession(page)

    assert session.open_group("Max deneme") is True
    assert page.search_value == "Max deneme"
    assert page.current_chat == "Max deneme"


def test_group_search_falls_back_to_current_whatsapp_sidebar_variants():
    runtime = load_runtime()
    page = FakeCompatibilityGroupPage()
    session = runtime.PlaywrightWhatsAppSession(page)

    assert session.open_group("Max deneme") is True
    assert page.search_value == "Max deneme"
    assert page.current_chat == "Max deneme"


def test_shutdown_cancels_browser_startup_and_finishes_the_worker():
    runtime = load_runtime()
    entered = threading.Event()

    def cancellable_factory(stop_event):
        entered.set()
        stop_event.wait(2)
        raise RuntimeError("cancelled")

    bot = runtime.ExternalWhatsAppBot(
        lambda _text: "unused",
        profile_dir="unused-in-test",
        session_factory=cancellable_factory,
    )
    assert entered.wait(1)

    bot.shutdown()

    assert bot._thread.is_alive() is False
