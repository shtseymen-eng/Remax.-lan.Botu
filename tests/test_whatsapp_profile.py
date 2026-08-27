from pathlib import Path

APP = Path('src/remax_bot/app.py').read_text(encoding='utf-8')

def test_whatsapp_has_separate_profile():
    assert "self.wa_profile=QWebEngineProfile('RemaxWhatsApp'" in APP

def test_whatsapp_uses_modern_chrome_user_agent():
    assert 'Chrome/136.0.0.0' in APP
    assert 'setHttpUserAgent' in APP

def test_whatsapp_profile_persists_session():
    assert "whatsapp-profile" in APP
    assert 'ForcePersistentCookies' in APP

def test_whatsapp_view_uses_whatsapp_profile():
    assert 'QWebEnginePage(self.wa_profile,self.wa)' in APP
