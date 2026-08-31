from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

def test_selenium_engine_exists():
    import remax_bot.whatsapp_selenium as w
    assert hasattr(w,"SeleniumWhatsAppBot")

def test_uses_persistent_chrome_profile():
    s=(ROOT/"src/remax_bot/whatsapp_selenium.py").read_text(encoding="utf-8")
    assert "--user-data-dir=" in s
    assert "--profile-directory=MaxBot" in s

def test_reader_based_on_working_pregate_selectors():
    s=(ROOT/"src/remax_bot/whatsapp_selenium.py").read_text(encoding="utf-8")
    assert '[data-testid="msg-container"]' in s
    assert '[data-testid="msg-text"]' in s
    assert "data-pre-plain-text" in s

def test_max_commands():
    from remax_bot.whatsapp_selenium import classify_command
    assert classify_command("#Max başla")=="start"
    assert classify_command("#max durdur")=="stop"
    assert classify_command("#?")=="query"
    assert classify_command("#izmit kiralık 55 bin")=="query"
    assert classify_command("merhaba")=="ignore"

def test_max_intro():
    from remax_bot.whatsapp_selenium import MAX_INTRO
    assert MAX_INTRO.startswith("Max:")
    assert "arama konusunda size yardımcı olacağım" in MAX_INTRO

def test_workflow_packages_selenium():
    y=(ROOT/".github/workflows/main.yml").read_text(encoding="utf-8")
    assert "--hidden-import selenium" in y

def test_pyproject_has_selenium():
    p=(ROOT/"pyproject.toml").read_text(encoding="utf-8")
    assert "selenium" in p
