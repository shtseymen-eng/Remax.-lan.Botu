from pathlib import Path
from remax_bot.whatsapp_logic import should_process, decorate_response, command_key

def test_only_hash_commands_are_processed():
    assert should_process('#?')
    assert should_process('#izmit kiralık 3+1#')
    assert should_process('#eksik')
    assert not should_process('merhaba')

def test_response_names_sender():
    text=decorate_response('Serhat', '2 uygun ilan bulundu')
    assert text.startswith('Serhat için')
    assert '2 uygun ilan bulundu' in text

def test_command_key_deduplicates_same_message():
    assert command_key('Ali','#?','10:30') == command_key('Ali','#?','10:30')
    assert command_key('Ali','#?','10:31') != command_key('Ali','#?','10:30')

def test_whatsapp_js_reads_open_chat_and_message_logic():
    s=Path('src/remax_bot/whatsapp_bot.py').read_text(encoding='utf-8')
    assert 'contenteditable' in s
    assert 'data-pre-plain-text' in s
    assert "document.querySelector('#main')" in s
