from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

from remax_bot.whatsapp_webengine import EmbeddedWhatsAppBot, MAX_INTRO, MessageRouter


ROOT = Path(__file__).resolve().parents[1]


def run_snapshot(setup: str):
    program = setup + r'''
const result = eval(process.argv[1]);
console.log(JSON.stringify(result));
'''
    completed = subprocess.run(
        ["node", "-e", program, EmbeddedWhatsAppBot.SNAPSHOT_JS],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout.strip())


def test_reader_works_when_whatsapp_no_longer_exposes_main_id():
    setup = r'''
const textNode = {innerText: '#max başla', textContent: '#max başla'};
const meta = {
  innerText: '#max başla',
  getAttribute(name){ return name === 'data-pre-plain-text' ? '[18:00, 31.08.2026] Siz: ' : ''; },
};
const row = {
  parentElement: null,
  innerText: '#max başla\n18:00',
  textContent: '#max başla 18:00',
  matches(selector){ return selector.includes('msg-container'); },
  closest(){ return this; },
  querySelector(selector){
    if(selector === '[data-testid="msg-text"]') return textNode;
    if(selector === '[data-pre-plain-text]') return meta;
    return null;
  },
  getAttribute(name){ return name === 'data-id' ? 'true_120363_group_ABC' : ''; },
};
const composer = {
  offsetParent: {},
  getClientRects(){ return [1]; },
};
global.document = {
  querySelector(){ return null; },
  querySelectorAll(selector){
    if(selector === '[data-testid="msg-container"]') return [row];
    if(selector.includes('footer div[contenteditable="true"]')) return [composer];
    return [];
  },
};
'''

    result = run_snapshot(setup)

    assert result["chat"]["title"] == "Açık sohbet"
    assert result["messages"] == [{"id": "true_120363_group_ABC", "text": "#max başla"}]


def test_open_chat_is_detected_from_visible_composer_without_messages():
    setup = r'''
const composer = {
  offsetParent: {},
  getClientRects(){ return [1]; },
};
global.document = {
  querySelector(){ return null; },
  querySelectorAll(selector){
    if(selector.includes('footer div[contenteditable="true"]')) return [composer];
    return [];
  },
};
'''

    result = run_snapshot(setup)

    assert result["chat"]["title"] == "Açık sohbet"
    assert result["messages"] == []


def test_reader_prefers_conversation_title_over_header_button_title():
    setup = r'''
const composer = {offsetParent: {}, getClientRects(){ return [1]; }};
const wrong = {
  innerText: 'Ara', textContent: 'Ara',
  getAttribute(name){ return name === 'title' ? 'Ara' : ''; },
};
const group = {
  innerText: 'Max deneme', textContent: 'Max deneme',
  getAttribute(name){ return name === 'title' ? 'Max deneme' : ''; },
};
const header = {
  querySelector(selector){
    if(selector === '[data-testid="conversation-info-header-chat-title"]') return group;
    if(selector === 'span[title]' || selector === '[title]') return wrong;
    return null;
  },
};
const main = {querySelector(selector){ return selector === 'header' ? header : null; }};
global.document = {
  querySelector(selector){ return selector === '#main' ? main : null; },
  querySelectorAll(selector){
    if(selector.includes('footer div[contenteditable="true"]')) return [composer];
    return [];
  },
};
'''

    result = run_snapshot(setup)

    assert result["chat"]["title"] == "Max deneme"


def test_dynamic_mode_locks_to_chat_where_start_arrived():
    router = MessageRouter(lambda text: f"Sonuç: {text}")
    first = {"chat": {"id": "one", "title": "Max deneme"}, "messages": []}
    router.process(first)

    started = router.process(
        {
            "chat": {"id": "one", "title": "Max deneme"},
            "messages": [{"id": "start", "text": "#max başla"}],
        }
    )
    other = router.process(
        {"chat": {"id": "two", "title": "Başka grup"}, "messages": []}
    )

    assert started.replies == [MAX_INTRO]
    assert router.locked_chat_title == "Max deneme"
    assert other.open_group == "Max deneme"


def test_saved_group_is_opened_in_embedded_whatsapp():
    class Page:
        def __init__(self):
            self.calls = []

        def runJavaScript(self, script, callback=None):
            self.calls.append(script)
            if callback:
                callback(True)

    page = Page()
    bot = EmbeddedWhatsAppBot(
        lambda _text: "",
        page=page,
        schedule=lambda _milliseconds, callback: callback(),
    )
    page.calls.clear()

    bot.set_group("  Max deneme  ")

    assert bot.router.configured_group == "Max deneme"
    assert any('const wanted="Max deneme"' in script for script in page.calls)


def test_application_and_package_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = (ROOT / "src/remax_bot/__init__.py").read_text(encoding="utf-8")

    assert project["project"]["version"] == "0.38.0"
    assert '__version__="0.38.0"' in package


def test_all_embedded_browser_scripts_are_valid_javascript():
    scripts = [
        EmbeddedWhatsAppBot.SNAPSHOT_JS,
        EmbeddedWhatsAppBot.SEARCH_GROUP_JS.replace("__GROUP_JSON__", '"Max deneme"'),
        EmbeddedWhatsAppBot.OPEN_GROUP_JS.replace("__GROUP_JSON__", '"Max deneme"'),
        EmbeddedWhatsAppBot.COMPOSE_MESSAGE_JS.replace("__MESSAGE_JSON__", '"Max: test"'),
        EmbeddedWhatsAppBot.CLICK_SEND_JS,
        EmbeddedWhatsAppBot.COMPOSER_EMPTY_JS,
        EmbeddedWhatsAppBot.CLEAR_COMPOSER_JS,
        EmbeddedWhatsAppBot.CLEAR_LEAKED_GROUP_DRAFT_JS.replace(
            "__GROUP_JSON__", '"Max deneme"'
        ),
    ]

    for script in scripts:
        subprocess.run(
            ["node", "-e", "new Function(process.argv[1]);", script],
            check=True,
            capture_output=True,
            text=True,
        )
