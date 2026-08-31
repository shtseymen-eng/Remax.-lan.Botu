from pathlib import Path
BOT = Path("src/remax_bot/whatsapp_bot.py").read_text(encoding="utf-8")

def test_open_chat_gate_accepts_current_message_bubbles_and_metadata():
    assert "bubbleRows.length>0" in BOT
    assert "metaRows.length>0" in BOT
    assert "const rows=[...new Set(" in BOT

def test_open_chat_gate_does_not_return_before_fallback_rows_are_checked():
    gate = BOT.index("const isOpen=")
    fallback = BOT.index("const bubbleRows=")
    assert fallback < gate

def test_composer_supports_new_whatsapp_editor_shapes():
    assert 'data-lexical-editor="true"' in BOT
    assert 'aria-placeholder*="mesaj"' in BOT
    assert 'aria-placeholder*="message"' in BOT
