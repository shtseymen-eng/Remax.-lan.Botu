from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v30_home_contains_embedded_whatsapp_and_listing_table():
    p=ROOT/"src/remax_bot/app.py"
    assert p.exists()
    app=p.read_text(encoding="utf-8")
    assert "WhatsApp Web" in app
    assert "İlanlar" in app
    assert "Danışman / İlan Sahibi" in app
    assert "Toplam İlan" in app
    assert "self.wa=QWebEngineView()" in app

def test_v30_sidebar_moves_bot_controls_and_keeps_seymen_signature():
    p=ROOT/"src/remax_bot/app.py"
    assert p.exists()
    app=p.read_text(encoding="utf-8")
    assert "BOTU BAŞLAT" in app
    assert "BOTU DURDUR" in app
    assert "Bot Durumu:" in app
    assert "S.Seymen tarafından hazırlanmıştır." in app
    assert "class SeymenRibbon" in app

def test_v30_main_navigation_has_no_separate_listings_page():
    p=ROOT/"src/remax_bot/app.py"
    assert p.exists()
    app=p.read_text(encoding="utf-8")
    assert "['Ana Sayfa','Veri Ekle','Web Sekmeleri','Ayarlar']" in app
    assert "v30.0.0" in app

def test_v30_home_has_advisor_filter_and_remax_sources():
    p=ROOT/"src/remax_bot/app.py"
    assert p.exists()
    app=p.read_text(encoding="utf-8")
    assert "self.advisor_filter" in app
    assert "RE/MAX ÇARŞI 2" in app
    assert "TARA / GÜNCELLE" in app

def test_whatsapp_reader_accepts_single_hash_messages():
    p=ROOT/"src/remax_bot/whatsapp_bot.py"
    assert p.exists()
    bot=p.read_text(encoding="utf-8")
    assert "startsWith('#')" in bot

def test_advisor_selection_filters_immediately():
    app=(ROOT/'src/remax_bot/app.py').read_text(encoding='utf-8')
    assert 'self.advisor_filter.currentTextChanged.connect(self.apply_filters)' in app
