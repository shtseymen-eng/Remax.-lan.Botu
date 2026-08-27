from pathlib import Path
BOT=Path("src/remax_bot/whatsapp_bot.py")
APP=Path("src/remax_bot/app.py")

def test_poll_reads_both_message_directions_without_sidebar_lookup():
    s=BOT.read_text(encoding="utf-8")
    assert "message-in" in s and "message-out" in s
    assert "data-pre-plain-text" in s
    assert "pane-side" not in s

def test_settings_page_has_no_whatsapp_log_panel():
    s=APP.read_text(encoding="utf-8")
    assert "WhatsApp Bot Günlüğü" not in s
    assert "self.walog" not in s
