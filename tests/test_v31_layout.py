from pathlib import Path

APP = Path("src/remax_bot/app.py").read_text(encoding="utf-8")

def test_sidebar_has_separate_listings_page():
    assert "['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Ayarlar']" in APP

def test_home_is_whatsapp_only_not_listing_table():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _listings(self):")]
    assert "WhatsApp Web" in home
    assert "self.wa=QWebEngineView()" in home
    assert "QTableWidget" not in home
    assert "TARA / GÜNCELLE" not in home
    assert "EXCEL / CSV YÜKLE" not in home

def test_listings_page_contains_listing_table_scan_and_excel_import():
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]
    assert "İlanlar" in listings
    assert "TARA / GÜNCELLE" in listings
    assert "EXCEL / CSV YÜKLE" in listings
    assert "self.table=QTableWidget" in listings
    assert "self.advisor_filter" in listings

def test_web_open_from_listing_uses_new_web_page_index():
    assert "self._go(3)" in APP
    assert "self.nav_buttons[3].setChecked(True)" in APP

def test_version_is_v31():
    assert "v31.0.0" in APP
