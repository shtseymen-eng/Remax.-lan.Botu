from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/remax_bot/app.py").read_text(encoding="utf-8")


def test_home_uses_a_persistent_external_chrome_whatsapp_session():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _new_listing_table(self):")]
    assert "WhatsApp Web" in home
    assert "ayrı Google Chrome penceresinde" in home
    assert "whatsapp-chrome-profile" in home
    assert "ExternalWhatsAppBot" in home
    assert "QWebEngineView" not in home
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
    assert "SEÇİLİ İLANI DÜZENLE" in listings


def test_data_movement_controls_are_collected_on_the_data_page():
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]
    data = APP[APP.index("    def _data(self):"):APP.index("    def _web(self):")]

    assert "EXCEL / CSV YÜKLE" not in listings
    assert "EXCEL'E AKTAR" not in listings
    assert "EXCEL / CSV YÜKLE" in data
    assert "VERİLERİ EXCEL'E AKTAR" in data
    assert "YAPAY ZEKÂ EXCEL ŞABLONU" in data
    assert "Excel (*.xlsx);;CSV (*.csv)" in data
    assert "self.export_source.addItems(list(LINK_SOURCES))" in data
    assert "exportb.clicked.connect(self.export_selected_site)" in data


def test_listing_editor_forgets_a_hidden_table_when_the_site_tab_changes():
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]
    edit_logic = APP[APP.index("    def edit_selected_listing(self):"):APP.index("    def manual_add(self):")]

    assert "self.listing_tabs.currentChanged.connect(self._listing_tab_changed)" in listings
    assert "def _listing_tab_changed(self,_index):" in edit_logic
    assert "self._last_listing_table=None" in edit_logic


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


def test_saved_max_search_settings_are_used_by_whatsapp_and_bot_test():
    home = APP[APP.index("    def _home(self):"):APP.index("    def _new_listing_table(self):")]
    bot_test = APP[APP.index("    def quick_test(self):"):APP.index("    def toggle_quick_result(self):")]
    settings = APP[APP.index("    def _settings(self):"):APP.index("    def refresh(self")]
    save = APP[APP.index("    def save_settings(self):"):APP.index("    def open_link(self,table,row):")]

    assert "Max Arama Ayarları" in settings
    assert "Komut işareti:" in settings
    assert "Aranacak kaynaklar" in settings
    assert "Aranacak veri alanları" in settings
    assert "Yükleme sonrası otomatik tarama" in settings
    assert "search_sources=self.settings.get('search_sources')" in home
    assert "search_fields=self.settings.get('search_fields')" in home
    assert "prefix=self.settings.get('command_prefix','#')" in home
    assert "self.chrome_info.setText" in save
    assert "{prefix} komutlarını" in APP
    assert "search_sources=self.settings.get('search_sources')" in bot_test
    assert "self.wabot.set_command_prefix" in save


def test_listing_table_adds_one_address_column_and_keeps_link_navigation():
    table = APP[APP.index("    def _new_listing_table(self):"):APP.index("    def _listings(self):")]
    fill = APP[APP.index("    def _fill_listing_table(self,table,rows):"):APP.index("    def apply_filters(self):")]
    open_link = APP[APP.index("    def open_link(self,table,row):"):APP.index("    def scan_verification(self,msg):")]

    assert "QTableWidget(0,12)" in table
    assert "'Bölge','Adres','Oda'" in table
    assert "display_address(x)" in fill
    assert "table.item(row,11)" in open_link


def test_import_success_can_start_the_selected_automatic_scan_queue():
    import_logic = APP[APP.index("    def import_file(self):"):APP.index("    def export_selected_site(self):")]
    scan_logic = APP[APP.index("    def _start_auto_scan_queue(self):"):APP.index("    def import_file(self):")]

    assert "self._start_auto_scan_queue()" in import_logic
    assert "def _scan_next_queued_source(self):" in scan_logic
    assert "def _complete_current_scan(self,success):" in scan_logic
    assert "self.sc.start(url)" in scan_logic


def test_automatic_scan_failure_remains_visible_to_the_user():
    failed = APP[APP.index("    def scan_failed(self,msg):"):APP.index("    def scan_done(self,source,rows):")]

    assert "QMessageBox.warning(self,'Tarama',msg)" in failed
    assert "if not automatic" not in failed
