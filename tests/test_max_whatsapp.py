from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
BOT=(ROOT/"src/remax_bot/whatsapp_bot.py").read_text(encoding="utf-8")
STATE=(ROOT/"src/remax_bot/whatsapp_state.py").read_text(encoding="utf-8")
APP=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")

sys.path.insert(0,str(ROOT/"src"))
from remax_bot.whatsapp_state import ActivationGate

def test_reader_uses_known_working_whatsapp_msg_container_selector():
    assert '[data-testid="msg-container"]' in BOT
    assert 'msgContainers' in BOT

def test_reader_can_process_outgoing_user_commands_too():
    assert "direction==='out'" in BOT
    assert "fullText.startsWith('#')" in BOT
    assert "if(direction==='out') return" not in BOT

def test_reader_does_not_require_main_or_footer_to_declare_chat_open():
    assert "msgContainers.length" in BOT
    assert "const isOpen=msgContainers.length>0 || !!inputBox" in BOT

def test_max_start_command():
    gate=ActivationGate()
    action,_=gate.handle("#Max başla")
    assert action=="started"
    assert gate.active is True

def test_old_bot_start_is_not_required_anymore():
    gate=ActivationGate()
    assert gate.handle("#bot başlat")[0]!="started"

def test_max_identity_is_used_on_all_whatsapp_replies():
    assert "def _max_message" in BOT
    assert "Max:" in BOT
    assert "Merhaba, ben Max." in BOT

def test_ui_hints_use_max_start_command():
    assert "#Max başla" in APP
