from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

from remax_bot.whatsapp_webengine import EmbeddedWhatsAppBot, MAX_INTRO, MessageRouter
from remax_bot.whatsapp_playwright import EXTERNAL_SNAPSHOT_JS


ROOT = Path(__file__).resolve().parents[1]


def run_script(setup: str, script: str):
    program = setup + r'''
const result = eval(process.argv[1]);
console.log(JSON.stringify(result));
'''
    completed = subprocess.run(
        ["node", "-e", program, script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout.strip())


def run_snapshot(setup: str):
    return run_script(setup, EmbeddedWhatsAppBot.SNAPSHOT_JS)


def test_reader_detects_current_dom_without_footer_or_legacy_testids():
    setup = r'''
const commandText = {
  parentElement: null,
  innerText: '#max başla', textContent: '#max başla',
  matches(selector){ return selector.includes('[data-lexical-text="true"]'); },
  closest(selector){ return selector.includes('[data-id]') ? messageRow : null; },
  getRootNode(){ return document; },
  getAttribute(){ return ''; },
};
const messageRow = {
  parentElement: null,
  innerText: '#max başla 09:39', textContent: '#max başla 09:39',
  matches(selector){ return selector.includes('[data-id]'); },
  closest(){ return this; },
  querySelector(selector){ return selector.includes('[data-lexical-text="true"]') ? commandText : null; },
  querySelectorAll(selector){ return selector.includes('[data-lexical-text="true"]') ? [commandText] : []; },
  getRootNode(){ return document; },
  getAttribute(name){ return name === 'data-id' ? 'false_120363_current_ABC' : ''; },
};
commandText.parentElement = messageRow;
const composer = {
  parentElement: null, offsetParent: {}, isContentEditable: true, tagName: 'DIV',
  innerText: '', textContent: '',
  matches(selector){ return selector.includes('[contenteditable="true"]'); },
  closest(){ return null; },
  getRootNode(){ return document; },
  getClientRects(){ return [1]; },
  getAttribute(name){
    if(name === 'role') return 'textbox';
    if(name === 'aria-placeholder') return 'Bir mesaj yazın';
    return '';
  },
};
global.document = {
  querySelector(){ return null; },
  querySelectorAll(selector){
    if(selector.includes('footer ')) return [];
    if(selector.includes('[contenteditable="true"]')) return [composer];
    if(selector.includes('[data-lexical-text="true"]')) return [commandText];
    if(selector.includes('[data-id]')) return [messageRow];
    if(selector === '*') return [composer,messageRow,commandText];
    return [];
  },
};
'''

    result = run_snapshot(setup)

    assert result["chat"]["title"] == "Açık sohbet"
    assert result["diagnostics"]["composer"] is True
    assert result["messages"] == [
        {"id": "false_120363_current_ABC", "text": "#max başla"}
    ]


def test_reader_traverses_open_shadow_roots():
    setup = r'''
const commandText = {
  parentElement: null,
  innerText: '#izmit kiralık', textContent: '#izmit kiralık',
  matches(selector){ return selector.includes('[data-lexical-text="true"]'); },
  closest(selector){ return selector.includes('[data-id]') ? messageRow : null; },
  getRootNode(){ return shadow; },
  getAttribute(){ return ''; },
};
const messageRow = {
  parentElement: null,
  innerText: '#izmit kiralık 09:40', textContent: '#izmit kiralık 09:40',
  matches(selector){ return selector.includes('[data-id]'); },
  closest(){ return this; },
  querySelector(selector){ return selector.includes('[data-lexical-text="true"]') ? commandText : null; },
  querySelectorAll(selector){ return selector.includes('[data-lexical-text="true"]') ? [commandText] : []; },
  getRootNode(){ return shadow; },
  getAttribute(name){ return name === 'data-id' ? 'true_120363_shadow_DEF' : ''; },
};
commandText.parentElement = messageRow;
const composer = {
  parentElement: null, offsetParent: {}, isContentEditable: true, tagName: 'DIV',
  innerText: '', textContent: '',
  matches(selector){ return selector.includes('[contenteditable="true"]'); },
  closest(){ return null; },
  getRootNode(){ return shadow; },
  getClientRects(){ return [1]; },
  getAttribute(name){ return name === 'role' ? 'textbox' : ''; },
};
const shadow = {
  host: null,
  querySelectorAll(selector){
    if(selector.includes('[contenteditable="true"]')) return [composer];
    if(selector.includes('[data-lexical-text="true"]')) return [commandText];
    if(selector.includes('[data-id]')) return [messageRow];
    if(selector === '*') return [composer,messageRow,commandText];
    return [];
  },
};
const host = {shadowRoot: shadow};
shadow.host = host;
global.document = {
  querySelector(){ return null; },
  querySelectorAll(selector){ return selector === '*' ? [host] : []; },
};
'''

    result = run_snapshot(setup)

    assert result["diagnostics"]["composer"] is True
    assert result["messages"] == [
        {"id": "true_120363_shadow_DEF", "text": "#izmit kiralık"}
    ]


def test_reader_ignores_command_previews_in_chat_sidebar():
    setup = r'''
const sidebar = {
  parentElement: null,
  matches(selector){ return selector.includes('#side'); },
  getRootNode(){ return document; },
};
const preview = {
  parentElement: sidebar,
  innerText: '#max başla', textContent: '#max başla',
  matches(selector){ return selector.includes('[data-id]'); },
  querySelector(){ return null; },
  getRootNode(){ return document; },
  getAttribute(name){ return name === 'data-id' ? 'false_sidebar_PREVIEW' : ''; },
};
global.document = {
  querySelector(){ return null; },
  querySelectorAll(selector){
    if(selector === '[data-id]') return [preview];
    if(selector === '*') return [sidebar,preview];
    return [];
  },
};
'''

    result = run_snapshot(setup)

    assert result["messages"] == []


def test_reply_can_be_composed_without_a_footer_element():
    setup = r'''
global.InputEvent = class { constructor(type,options){ this.type=type; this.options=options; } };
const composer = {
  parentElement: null, offsetParent: {}, isContentEditable: true, tagName: 'DIV',
  innerText: '', textContent: '',
  matches(selector){ return selector.includes('[contenteditable="true"]'); },
  closest(){ return null; },
  getRootNode(){ return document; },
  getClientRects(){ return [1]; },
  getAttribute(name){
    if(name === 'role') return 'textbox';
    if(name === 'aria-placeholder') return 'Bir mesaj yazın';
    return '';
  },
  focus(){}, dispatchEvent(){ return true; },
};
const selection = {removeAllRanges(){},addRange(){}};
global.window = {getSelection(){ return selection; }};
global.document = {
  querySelectorAll(selector){
    if(selector.includes('footer ')) return [];
    if(selector.includes('[contenteditable="true"]')) return [composer];
    if(selector === '*') return [composer];
    return [];
  },
  createRange(){ return {selectNodeContents(){},collapse(){}}; },
  execCommand(command,_ui,value){
    if(command === 'delete') composer.innerText=composer.textContent='';
    if(command === 'insertText') composer.innerText=composer.textContent=String(value || '');
    return true;
  },
};
'''
    script = EmbeddedWhatsAppBot.COMPOSE_MESSAGE_JS.replace(
        "__MESSAGE_JSON__", json.dumps("Max: Hazırım", ensure_ascii=False)
    )

    assert run_script(setup, script) is True


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

    assert project["project"]["version"] == "0.40.0"
    assert '__version__="0.40.0"' in package


def test_all_embedded_browser_scripts_are_valid_javascript():
    scripts = [
        EXTERNAL_SNAPSHOT_JS,
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
