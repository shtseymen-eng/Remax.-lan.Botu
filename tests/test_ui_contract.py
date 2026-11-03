from pathlib import Path
from types import SimpleNamespace

import remax_bot.app as app_module


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


class _FakeButton:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class _FakeCombo:
    def __init__(self, current_data=None):
        self.items = []
        self.index = -1
        self._current_data = current_data

    def currentData(self):
        if 0 <= self.index < len(self.items):
            return self.items[self.index][1]
        return self._current_data

    def currentText(self):
        if 0 <= self.index < len(self.items):
            return self.items[self.index][0]
        return ""

    def blockSignals(self, _blocked):
        pass

    def clear(self):
        self.items = []
        self.index = -1

    def addItem(self, text, data=None):
        self.items.append((text, data))
        if self.index < 0:
            self.index = 0

    def findData(self, data):
        return next((i for i, item in enumerate(self.items) if item[1] == data), -1)

    def setCurrentIndex(self, index):
        self.index = index


class _FakeIndex:
    def __init__(self, row):
        self._row = row

    def row(self):
        return self._row


class _FakeCell:
    def __init__(self, identity):
        self.identity = identity

    def data(self, _role):
        return self.identity


class _FakeTable:
    def __init__(self, identities):
        self.identities = identities

    def selectionModel(self):
        return self

    def hasSelection(self):
        return bool(self.identities)

    def selectedRows(self):
        return [_FakeIndex(row) for row in range(len(self.identities))]

    def item(self, row, column):
        assert column == 0
        identity = self.identities[row]
        return _FakeCell(identity) if identity else None


def test_listing_deletion_controls_keep_the_existing_layout_and_allow_multi_select():
    table = APP[APP.index("    def _new_listing_table(self):"):APP.index("    def _listings(self):")]
    listings = APP[APP.index("    def _listings(self):"):APP.index("    def _data(self):")]

    assert "setSelectionMode(QAbstractItemView.ExtendedSelection)" in table
    assert "self.delete_source_combo=QComboBox()" in listings
    assert "SEÇİLİ İLANLARI SİL" in listings
    assert "KAYNAĞI SİL" in listings
    assert "TÜM İLANLARI SİL" in listings


def test_delete_confirmation_shows_count_and_defaults_to_no(monkeypatch):
    captured = {}

    def question(_parent, title, message, buttons, default):
        captured.update(title=title, message=message, buttons=buttons, default=default)
        return app_module.QMessageBox.StandardButton.No

    monkeypatch.setattr(app_module.QMessageBox, "question", question)

    confirmed = app_module.Main._confirm_listing_delete(
        object(), "Seçili İlanları Sil", 7, "Seçili kayıtlar silinecek."
    )

    assert not confirmed
    assert "7" in captured["message"]
    assert "kalıcı" in captured["message"].casefold()
    assert captured["default"] == app_module.QMessageBox.StandardButton.No
    assert captured["buttons"] & app_module.QMessageBox.StandardButton.Yes


def test_delete_source_picker_uses_real_database_sources_and_preserves_selection():
    carsi_2 = "https://remax.com.tr/tr/ofis/detay/carsi-2"
    combo = _FakeCombo(current_data=carsi_2)
    source_button = _FakeButton()
    all_button = _FakeButton()
    fake = SimpleNamespace(
        db=SimpleNamespace(
            source_counts=lambda: [("excel://import/", 3), (carsi_2, 2)],
            count=lambda: 5,
        ),
        delete_source_combo=combo,
        delete_source_button=source_button,
        delete_all_button=all_button,
    )

    app_module.Main._refresh_delete_sources(fake)

    assert combo.items == [
        ("EXCEL / LİSTE (3)", "excel://import/"),
        ("MyRE/MAX ÇARŞI 2 (2)", carsi_2),
    ]
    assert combo.currentData() == carsi_2
    assert source_button.enabled
    assert all_button.enabled


def test_selected_listing_identities_are_deduplicated_from_selected_rows():
    table = _FakeTable([
        ("manual://entry/", "1"),
        ("manual://entry/", "1"),
        ("excel://import/", "2"),
        None,
    ])
    fake = SimpleNamespace(
        _last_listing_table=table,
        listing_tabs=SimpleNamespace(currentWidget=lambda: table),
    )

    assert app_module.Main._selected_listing_identities(fake) == [
        ("manual://entry/", "1"),
        ("excel://import/", "2"),
    ]


def test_all_and_source_deletions_use_current_counts_then_refresh(monkeypatch):
    events = []
    source = "manual://entry/"

    class DB:
        def count(self): return 4
        def source_count(self, value):
            assert value == source
            return 2
        def delete_all(self):
            events.append(("delete_all",))
            return 4
        def delete_source(self, value):
            events.append(("delete_source", value))
            return 2

    fake = SimpleNamespace(
        db=DB(),
        delete_source_combo=_FakeCombo(current_data=source),
        _last_listing_table=object(),
        _confirm_listing_delete=lambda title, count, detail: events.append(
            ("confirm", title, count, detail)
        ) or True,
        refresh=lambda: events.append(("refresh",)),
    )
    monkeypatch.setattr(app_module.QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(app_module.QMessageBox, "warning", lambda *_args: None)

    app_module.Main.delete_source_listings(fake)
    app_module.Main.delete_all_listings(fake)

    assert ("delete_source", source) in events
    assert ("delete_all",) in events
    assert [event[2] for event in events if event[0] == "confirm"] == [2, 4]
    assert events.count(("refresh",)) == 2
    assert fake._last_listing_table is None


def test_selected_deletion_counts_existing_records_and_refreshes(monkeypatch):
    events = []
    identities = [("manual://entry/", "1"), ("excel://import/", "2")]

    class DB:
        def raw_listing(self, source, listing_id):
            return object() if (source, listing_id) in identities else None
        def delete_listings(self, values):
            events.append(("delete_listings", list(values)))
            return len(values)

    fake = SimpleNamespace(
        db=DB(),
        _last_listing_table=object(),
        _selected_listing_identities=lambda: identities + [("manual://entry/", "missing")],
        _confirm_listing_delete=lambda title, count, detail: events.append(
            ("confirm", title, count, detail)
        ) or True,
        refresh=lambda: events.append(("refresh",)),
    )
    monkeypatch.setattr(app_module.QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(app_module.QMessageBox, "warning", lambda *_args: None)

    app_module.Main.delete_selected_listings(fake)

    assert ("delete_listings", identities) in events
    assert next(event[2] for event in events if event[0] == "confirm") == 2
    assert events[-1] == ("refresh",)
    assert fake._last_listing_table is None
