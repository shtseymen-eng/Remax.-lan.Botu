from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
BOT=(ROOT/"src/remax_bot/whatsapp_webengine.py").read_text(encoding="utf-8")

def snap():
    return BOT[BOT.index("SNAPSHOT_JS"):BOT.index("COMPOSE_MESSAGE_JS")]

def test_reader_uses_pregate_global_msg_container():
    s=snap()
    assert 'document.querySelectorAll(\'[data-testid="msg-container"]\')' in s
    assert "const root=document.querySelector('#main')" not in s

def test_reader_does_not_require_header_title():
    s=snap()
    assert "if(!title) return null" not in s
    assert "title || 'Açık sohbet'" in s

def test_reader_has_working_pregate_text_selectors():
    s=snap()
    for selector in [
        '[data-testid="msg-text"]',
        'span.selectable-text.copyable-text',
        'span[class*="selectable-text"]',
        'div[class*="copyable-text"] span[dir]',
    ]:
        assert selector in s

def test_reader_climbs_to_data_id():
    s=snap()
    assert "while(dataIdEl && !dataIdEl.getAttribute('data-id'))" in s

def test_outgoing_max_commands_are_not_discarded():
    s=snap()
    assert "outgoing" in s
    assert "if(outgoing) return" not in s

def test_open_chat_can_be_detected_from_composer():
    s=snap()
    assert "const composer=" in s
    assert "if(!rows.length && !composer) return null" in s

def test_sender_works_without_main_id():
    compose=BOT[BOT.index("COMPOSE_MESSAGE_JS"):BOT.index("CLICK_SEND_JS")]
    assert "document.querySelector('#main')" not in compose
    assert "document.querySelectorAll(selector)" in compose
