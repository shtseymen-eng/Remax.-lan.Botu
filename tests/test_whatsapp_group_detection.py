from pathlib import Path
TEXT=Path('src/remax_bot/whatsapp_bot.py').read_text(encoding='utf-8')

def test_no_sidebar_or_group_title_dependency():
    assert 'pane-side' not in TEXT
    assert 'activeGroup' not in TEXT
    assert 'targetLower' not in TEXT

def test_message_scan_uses_current_main_chat():
    assert "document.querySelector('#main')" in TEXT
    assert "document.querySelectorAll('[data-id]')" not in TEXT  # scoped via main.querySelectorAll
    assert "main.querySelectorAll('[data-id]')" in TEXT
    assert 'message-in' in TEXT and 'message-out' in TEXT

def test_hash_command_extraction_exists():
    assert 'match(/#[^#\\n]+#/g)' in TEXT
