from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v31_home_contains_embedded_whatsapp_only():
    app=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")
    home=app[app.index("    def _home(self):"):app.index("    def _listings(self):")]
    assert "WhatsApp Web" in home
    assert "self.wa=QWebEngineView()" in home
    assert "QTableWidget" not in home
    assert "TARA / GÜNCELLE" not in home

def test_v31_sidebar_keeps_bot_controls_and_seymen_signature():
    app=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")
    assert "BOTU BAŞLAT" in app
    assert "BOTU DURDUR" in app
    assert "Bot Durumu:" in app
    assert "S.Seymen tarafından hazırlanmıştır." in app
    assert "class SeymenRibbon" in app

def test_v31_navigation_has_separate_listings_page():
    app=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")
    assert "['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Ayarlar']" in app
    assert "v31.0.0" in app

def test_v31_listings_has_filters_and_remax_sources():
    app=(ROOT/"src/remax_bot/app.py").read_text(encoding="utf-8")
    listings=app[app.index("    def _listings(self):"):app.index("    def _data(self):")]
    assert "self.advisor_filter" in listings
    assert "RE/MAX ÇARŞI 2" in app
    assert "TARA / GÜNCELLE" in listings
    assert "EXCEL / CSV YÜKLE" in listings
    assert "self.table=QTableWidget" in listings

def test_advisor_selection_filters_immediately():
    app=(ROOT/'src/remax_bot/app.py').read_text(encoding='utf-8')
    assert 'self.advisor_filter.currentTextChanged.connect(self.apply_filters)' in app
