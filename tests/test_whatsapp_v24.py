from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'src/remax_bot/app.py').read_text(encoding='utf-8')
BOT=(ROOT/'src/remax_bot/whatsapp_bot.py').read_text(encoding='utf-8')


def test_no_open_chat_group_button():
    assert 'AÇIK SOHBETİ BOT GRUBU YAP' not in APP


def test_bot_does_not_require_group_name_to_start():
    assert "if not self.group" not in BOT
    assert "Grup adı girilmedi" not in BOT


def test_poll_does_not_search_or_match_group_name():
    assert 'targetLower' not in BOT
    assert 'targetVisibleInMain' not in BOT
    assert 'activeGroup' not in BOT


def test_bot_listens_to_current_open_chat_only():
    assert "document.querySelector('#main')" in BOT
    assert "Dinleniyor: açık WhatsApp sohbeti" in BOT


def test_old_open_chat_reader_removed():
    assert 'READ_OPEN_CHAT_JS' not in BOT
    assert 'read_open_chat' not in BOT
