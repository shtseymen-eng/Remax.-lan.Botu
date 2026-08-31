from pathlib import Path

APP = Path('src/remax_bot/app.py').read_text(encoding='utf-8')

def test_whatsapp_uses_modern_chrome_user_agent():
    assert 'Chrome/136.0.0.0' in APP
    assert 'setHttpUserAgent' in APP
