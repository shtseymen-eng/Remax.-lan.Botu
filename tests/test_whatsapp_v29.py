from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'src/remax_bot/app.py').read_text(encoding='utf-8')
PYPROJECT=(ROOT/'pyproject.toml').read_text(encoding='utf-8')

def test_app_uses_embedded_whatsapp_bot_not_selenium():
    assert 'from .whatsapp_bot import WhatsAppBot' in APP
    assert 'SeleniumWhatsAppBot' not in APP
    assert 'WhatsAppBot(self.wa' in APP

def test_settings_show_command_list_under_test_area():
    test_pos=APP.index("Bot Komut Testi")
    list_pos=APP.index("Komut Listesi")
    assert list_pos > test_pos
    assert 'self.commandlist.setPlainText(command_help())' in APP

def test_seymen_ribbon_branding_exists():
    assert 'class SeymenRibbon' in APP
    assert 'drawText' in APP
    assert 'SEYMEN' in APP

def test_version_is_031():
    assert 'v31.0.0' in APP
    assert 'version = "0.31.0"' in PYPROJECT
