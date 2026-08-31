from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BOT=(ROOT/"src/remax_bot/whatsapp_webengine.py").read_text(encoding="utf-8")

def test_max_reader_autostarts_without_sidebar_button():
    assert "self._auto_start_when_ready()" in BOT
    assert "def _auto_start_when_ready" in BOT

def test_start_command_is_max_only():
    assert '"#max başla"' in BOT
    assert '"#max başlat"' in BOT
    assert '"#bot başlat"' not in BOT

def test_compose_clears_before_inserting_once():
    compose=BOT[BOT.index("COMPOSE_MESSAGE_JS"):BOT.index("CLICK_SEND_JS")]
    assert "selection.addRange(range)" in compose
    assert "document.execCommand('delete'" in compose
    assert "document.execCommand('insertText',false,message)" in compose

def test_send_has_button_then_enter_fallback():
    send=BOT[BOT.index("CLICK_SEND_JS"):BOT.index("COMPOSER_EMPTY_JS")]
    assert 'data-icon="send"' in send
    assert "KeyboardEvent('keydown'" in send
    assert "key:'Enter'" in send

def test_group_search_is_limited_to_whatsapp_sidebar():
    search=BOT[BOT.index("SEARCH_GROUP_JS"):BOT.index("OPEN_GROUP_JS")]
    assert "const side=" in search
    assert "side.querySelectorAll(selector)" in search
    assert "side.closest?.('#main,footer')" in search
    assert "document.querySelectorAll(selector)" not in search
