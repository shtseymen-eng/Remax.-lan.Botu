from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8")


def test_home_keeps_whatsapp_preview_separate_from_listing_table():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _listings(self):")]
    assert "WhatsApp Web" in home
    assert "gerçek Chrome WhatsApp" in home
    assert "QTableWidget" not in home
    assert "TARA / GÜNCELLE" not in home


def test_sidebar_keeps_bot_controls_and_branding():
    assert "BOTU BAŞLAT" in APP
    assert "BOTU DURDUR" in APP
    assert "Bot Durumu:" in APP
    assert "S.Seymen tarafından hazırlanmıştır." in APP
    assert "class SeymenRibbon" in APP


def test_navigation_and_listing_tools_remain_available():
    assert "['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Ayarlar']" in APP
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]
    assert "self.table=QTableWidget" in listings
    assert "self.advisor_filter" in listings
    assert "TARA / GÜNCELLE" in listings
    assert "EXCEL / CSV YÜKLE" in listings


def test_command_test_result_can_be_collapsed():
    assert "self.quick_result.setMaximumHeight(" in APP
    assert "def toggle_quick_result(self):" in APP
    assert "SONUCU GÖSTER" in APP
    assert "SONUCU GİZLE" in APP


def test_settings_show_group_and_command_help():
    assert "WhatsApp grup/sohbet adı:" in APP
    assert "self.commandlist.setPlainText(command_help())" in APP
