from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8")


def test_home_uses_visible_whatsapp_panel_for_the_bot():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _new_listing_table(self):")]
    assert "WhatsApp Web" in home
    assert "Max bu paneli doğrudan kullanır" in home
    assert "gerçek Chrome WhatsApp" not in home
    assert "QTableWidget" not in home
    assert "TARA / GÜNCELLE" not in home
    assert "KOMUTU TEST ET" not in home


def test_sidebar_keeps_bot_controls_and_branding():
    assert "BOTU BAŞLAT" in APP
    assert "BOTU DURDUR" in APP
    assert "Bot Durumu:" in APP
    assert "S.Seymen tarafından hazırlanmıştır." in APP
    assert "class SeymenRibbon" in APP


def test_navigation_and_listing_tools_remain_available():
    assert "['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Bot Testi','Ayarlar']" in APP
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]
    assert "self.listing_tabs=QTabWidget" in listings
    assert "'Sahibinden','Emlakjet','MyRE/MAX'" in listings
    assert "self.other_table" in listings
    assert "İçe Aktarılan / Kaynağı Belirsiz" in listings
    assert "self.advisor_filter" in listings
    assert "TARA / GÜNCELLE" in listings
    assert "EXCEL / CSV YÜKLE" in listings


def test_command_test_result_can_be_collapsed():
    assert "self.quick_result.setMaximumHeight(" in APP
    assert "def toggle_quick_result(self):" in APP
    assert "SONUCU GÖSTER" in APP
    assert "SONUCU GİZLE" in APP


def test_settings_show_group_but_bot_test_has_its_own_page():
    assert "WhatsApp grup/sohbet adı:" in APP
    bot_test = APP[APP.index("    def _bot_test(self):"):APP.index("    def _settings(self):")]
    settings = APP[APP.index("    def _settings(self):"):APP.index("    def refresh(self")]
    assert "self.commandlist.setPlainText(command_help())" in bot_test
    assert "Bot Komut Testi" not in settings


def test_saved_link_source_is_used_by_whatsapp_and_bot_test():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _new_listing_table(self):")]
    bot_test = APP[APP.index("    def quick_test(self):"):APP.index("    def toggle_quick_result(self):")]
    settings = APP[APP.index("    def _settings(self):"):APP.index("    def refresh(self")]
    save = APP[APP.index("    def save_settings(self):"):APP.index("    def open_link(self,table,row):")]

    assert "'link_source':'MyRE/MAX'" in APP
    assert "İlan linki kaynağı:" in settings
    assert "self.link_source.addItems(list(LINK_SOURCES))" in settings
    assert "link_source=self.settings.get('link_source','MyRE/MAX')" in home
    assert "link_source=self.settings.get('link_source','MyRE/MAX')" in bot_test
    assert "link_source=self.link_source.currentText()" in save
