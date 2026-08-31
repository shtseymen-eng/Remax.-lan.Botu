from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")
BOT=(ROOT/"src/remax_bot/whatsapp_bot.py").read_text(encoding="utf-8")

def test_reader_does_not_depend_only_on_main_id():
    assert "msgContainers" in BOT
    assert '[data-testid="msg-container"]' in BOT
    assert "document.body" in BOT
    assert "conversationRoot.querySelectorAll" in BOT

def test_reader_accepts_single_hash_from_open_conversation():
    assert "fullText.startsWith('#')" in BOT
    assert "commands=[fullText]" in BOT

def test_command_result_uses_bounded_panel():
    assert "self.quick_result=QPlainTextEdit()" in APP
    assert "self.quick_result.setMaximumHeight(" in APP
    assert "self.quick_toggle" in APP

def test_command_result_can_be_collapsed():
    assert "def toggle_quick_result(self):" in APP
    assert "self.quick_result.setVisible(" in APP
    assert "SONUCU GÖSTER" in APP
    assert "SONUCU GİZLE" in APP

def test_quick_test_opens_result_panel():
    assert "self.quick_result.setPlainText(" in APP
    assert "self.quick_result.setVisible(True)" in APP
