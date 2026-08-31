from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = (ROOT / "src/remax_bot/whatsapp_bot.py").read_text(encoding="utf-8")

def test_group_reader_uses_message_containers():
    assert '[data-testid="msg-container"]' in BOT
    assert "data-pre-plain-text" in BOT
    assert "sender" in BOT

def test_group_reader_accepts_incoming_and_outgoing_hash_commands():
    assert "direction=outNode ? 'out'" in BOT
    assert "fullText.startsWith('#')" in BOT
    assert "if(direction==='out') return" not in BOT

def test_group_sender_is_parsed_from_whatsapp_metadata():
    assert "pre.match(" in BOT
    assert "sender=clean(m[2])" in BOT
