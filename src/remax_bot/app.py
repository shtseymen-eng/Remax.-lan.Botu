from __future__ import annotations
import os,sys,re,json
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt,QUrl,QPointF
from PySide6.QtGui import QPixmap,QIcon,QPainter,QPolygonF,QFont
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage

from .core import DB,Listing,norm,source_key,source_label,split_listings_by_site,update_listing_fields
from .listing_details import display_address
from .playwright_scanner import PlaywrightScanner
from .importer import LINK_SOURCES,read_list_file,write_list_file,write_ai_template,command_response,command_help,advisor_names,advisor_display_name,is_valid_advisor,filter_listings,price_number
from .scan_queue import AUTO_SCAN_SOURCE_LABELS,AutoScanQueue
from .settings_schema import DEFAULT_SEARCH_FIELDS,DEFAULT_SEARCH_SOURCES,SEARCH_FIELD_LABELS,normalize_command_prefix,normalize_search_fields,normalize_search_sources
from .whatsapp_playwright import ExternalWhatsAppBot
from . import __version__

BLUE='#0B4DB8';NAVY='#062D69';RED='#E31837';GREEN='#13A84A'
BG='#F4F7FB';CARD='#FFFFFF';BORDER='#D9E2EF';TEXT='#172033';MUTED='#667085'
SOURCES={
    'MyRE/MAX ÇARŞI':'https://remax.com.tr/tr/ofis/detay/carsi?tab=portfoylerimiz',
    'MyRE/MAX ÇARŞI 2':'https://remax.com.tr/tr/ofis/detay/carsi-2?tab=portfoylerimiz',
    'Emlakjet ÇARŞI':'https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566',
    'Sahibinden ÇARŞI':'https://carsigayrimenkulkocaeli.sahibinden.com/',
    'Sahibinden ÇARŞI 2':'https://remaxcarsi2.sahibinden.com/'
}

def app_data():
    h=Path.home()
    return (Path(os.getenv('LOCALAPPDATA',h))/'RemaxIlanBotu') if os.name=='nt' else (h/'Library'/'Application Support'/'RemaxIlanBotu')

def asset(name): return Path(__file__).resolve().parent/'assets'/name

class SeymenRibbon(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(205,68)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing,True)
        w=float(self.width()); h=float(self.height()); teeth=7; step=h/teeth
        pts=[QPointF(17,8),QPointF(w-17,0)]
        for i in range(teeth):
            y=i*step
            pts += [QPointF(w-2 if i%2==0 else w-18,y+step/2),QPointF(w-17,y+step)]
        pts += [QPointF(17,h)]
        for i in reversed(range(teeth)):
            y=i*step
            pts += [QPointF(2 if i%2==0 else 18,y+step/2),QPointF(17,y)]
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.yellow)
        p.drawPolygon(QPolygonF(pts))
        p.setPen(Qt.black)
        f=QFont('Arial',23,QFont.Black); f.setItalic(True); p.setFont(f)
        p.drawText(self.rect(),Qt.AlignCenter,'SEYMEN')

class ListingEditDialog(QDialog):
    FIELDS=[
        ('listing_id','İlan No'),('title','Başlık'),('advisor','Danışman'),
        ('phone','Telefon'),('price','Fiyat'),('location','Bölge'),('rooms','Oda'),
        ('transaction_type','Satılık / Kiralık'),('property_type','Emlak Türü'),
        ('sqm','Brüt m²'),('net_sqm','Net m²'),('listing_date','İlan Tarihi'),
        ('province','İl'),('district','İlçe'),('neighborhood','Mahalle'),
        ('street','Sokak / Cadde'),('complex_name','Site / Proje'),
        ('full_address','Açık Adres'),('description','İlan Açıklaması'),
        ('details','Ek Özellikler (JSON)'),('url','İlan Linki'),
        ('source_url','Kaynak Linki'),
    ]

    def __init__(self,item,parent=None,raw_item=None):
        super().__init__(parent)
        self.item=item
        self.raw_item=raw_item or item
        self.setWindowTitle('İlanı Düzenle')
        self.resize(720,620)
        layout=QVBoxLayout(self)
        form=QFormLayout()
        self.inputs={}
        for field,label in self.FIELDS:
            value=getattr(item,field)
            if field=='details':value=json.dumps(value or {},ensure_ascii=False,sort_keys=True)
            edit=QLineEdit(str(value or ''))
            edit.setObjectName(f'listing_{field}')
            self.inputs[field]=edit
            form.addRow(label+':',edit)
        layout.addLayout(form)
        save_button=QDialogButtonBox.StandardButton.Save
        cancel_button=QDialogButtonBox.StandardButton.Cancel
        buttons=QDialogButtonBox(save_button|cancel_button)
        buttons.button(save_button).setText('İLANI GÜNCELLE')
        buttons.button(cancel_button).setText('VAZGEÇ')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def edited_listing(self):
        values={field:edit.text() for field,edit in self.inputs.items()}
        if values['advisor'].strip()==self.item.advisor.strip():
            values['advisor']=self.raw_item.advisor
        return update_listing_fields(self.raw_item,values)

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RE/MAX ÇARŞI İlan Botu')
        self.setWindowIcon(QIcon(str(asset('app_icon.png'))))
        self.resize(1540,960)
        self.setMinimumSize(1200,760)
        d=app_data(); d.mkdir(parents=True,exist_ok=True)
        self.db=DB(d/'data'/'listings.sqlite3')
        self.cfg=d/'settings.json'
        self.settings=self._load_settings()

        self.profile=QWebEngineProfile('RemaxIlanBotu',self)
        self.profile.setPersistentStoragePath(str(d/'web-profile'))
        self.profile.setCachePath(str(d/'web-cache'))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)

        self._build()
        self._style()
        self.refresh()

    def _load_settings(self):
        base={
            'group':'','sound':True,'bot':False,'days':7,'link_source':'MyRE/MAX',
            'command_prefix':'#','search_sources':list(DEFAULT_SEARCH_SOURCES),
            'search_fields':list(DEFAULT_SEARCH_FIELDS),'auto_scan_after_import':True,
            'auto_scan_sources':list(AUTO_SCAN_SOURCE_LABELS),
        }
        try:
            if self.cfg.exists():
                base.update(json.loads(self.cfg.read_text(encoding='utf-8')))
        except Exception:
            pass
        base['command_prefix']=normalize_command_prefix(base.get('command_prefix'))
        base['search_sources']=normalize_search_sources(base.get('search_sources'))
        base['search_fields']=normalize_search_fields(base.get('search_fields'))
        selected_auto=base.get('auto_scan_sources')
        if not isinstance(selected_auto,(list,tuple,set)):
            selected_auto=AUTO_SCAN_SOURCE_LABELS
        base['auto_scan_sources']=[
            label for label in AUTO_SCAN_SOURCE_LABELS if label in selected_auto
        ]
        base['auto_scan_after_import']=bool(base.get('auto_scan_after_import',True))
        return base

    def _save_settings(self):
        self.cfg.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')

    def _style(self):
        self.setStyleSheet(f'''QWidget{{background:{BG};color:{TEXT};font-family:Arial;font-size:13px}}
QFrame#side{{background:{NAVY}}}
QFrame#card,QGroupBox{{background:{CARD};border:1px solid {BORDER};border-radius:12px}}
QGroupBox{{margin-top:12px;padding-top:14px;font-weight:800}}
QPushButton#nav{{color:white;background:transparent;border:none;text-align:left;padding:13px;border-radius:8px;font-weight:800}}
QPushButton#nav:hover{{background:rgba(255,255,255,.10)}}
QPushButton#nav:checked{{background:{BLUE}}}
QPushButton#blue{{background:{BLUE};color:white;border:none;border-radius:8px;padding:10px 16px;font-weight:800}}
QPushButton#red{{background:{RED};color:white;border:none;border-radius:8px;padding:10px 16px;font-weight:800}}
QPushButton#green{{background:{GREEN};color:white;border:none;border-radius:8px;padding:11px 16px;font-weight:900}}
QPushButton#ghost{{background:white;border:1px solid {BORDER};border-radius:8px;padding:9px 13px;font-weight:700}}
QLineEdit,QSpinBox,QComboBox{{background:white;border:1px solid {BORDER};border-radius:8px;padding:8px}}
QTableWidget{{background:white;border:1px solid {BORDER};border-radius:10px;gridline-color:{BORDER};selection-background-color:#EAF2FF}}
QHeaderView::section{{background:#F8FAFD;padding:9px;border:none;border-bottom:1px solid {BORDER};font-weight:900}}
QTabBar::tab{{background:#F5F7FB;padding:10px 18px;border:1px solid {BORDER}}}
QTabBar::tab:selected{{background:white;border-top:3px solid {BLUE}}}''')

    def _build(self):
        root=QWidget()
        self.setCentralWidget(root)
        outer=QHBoxLayout(root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        side=QFrame()
        side.setObjectName('side')
        side.setFixedWidth(250)
        sl=QVBoxLayout(side)
        sl.setContentsMargins(16,20,16,16)
        sl.setSpacing(8)

        logo=QLabel()
        logo.setAlignment(Qt.AlignCenter)
        px=QPixmap(str(asset('remax_carsi.jpg')))
        logo.setPixmap(px.scaled(190,150,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        sl.addWidget(logo)

        self.stack=QStackedWidget()
        self.nav_buttons=[]
        for i,t in enumerate(['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Bot Testi','Ayarlar']):
            b=QPushButton(t)
            b.setObjectName('nav')
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.clicked.connect(lambda _,n=i:self._go(n))
            sl.addWidget(b)
            self.nav_buttons.append(b)
        self.nav_buttons[0].setChecked(True)

        sl.addStretch()

        start=QPushButton('▶  BOTU BAŞLAT')
        start.setObjectName('green')
        start.clicked.connect(self.bot_start)
        sl.addWidget(start)

        stop=QPushButton('■  BOTU DURDUR')
        stop.setObjectName('red')
        stop.clicked.connect(self.bot_stop)
        sl.addWidget(stop)

        self.side_status=QLabel('●  Bot Durumu: Durduruldu')
        self.side_status.setStyleSheet('color:#D9E6FF;font-size:12px;padding:7px')
        sl.addWidget(self.side_status)

        self.seymen_ribbon=SeymenRibbon()
        sl.addWidget(self.seymen_ribbon,0,Qt.AlignHCenter)

        credit=QLabel('S.Seymen tarafından hazırlanmıştır.')
        credit.setAlignment(Qt.AlignCenter)
        credit.setStyleSheet('color:#D9E6FF;font-size:10px')
        sl.addWidget(credit)

        ver=QLabel(f'v{__version__}  •  RE/MAX ÇARŞI')
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet('color:#8FA9CC;font-size:10px')
        sl.addWidget(ver)

        outer.addWidget(side)
        outer.addWidget(self.stack,1)

        self._home()
        self._listings()
        self._data()
        self._web()
        self._bot_test()
        self._settings()
        self.stack.setCurrentIndex(0)

    def _go(self,index):
        self.stack.setCurrentIndex(index)

    def _page(self):
        w=QWidget()
        l=QVBoxLayout(w)
        l.setContentsMargins(20,18,20,18)
        l.setSpacing(12)
        return w,l

    def _home(self):
        p,l=self._page()

        top=QHBoxLayout()
        title=QLabel('Ana Sayfa')
        title.setStyleSheet('font-size:25px;font-weight:900')
        top.addWidget(title)
        top.addStretch()
        self.wa_status_chip=QLabel('Web sekmesi hazır')
        self.wa_status_chip.setStyleSheet('color:#087A3B;font-weight:800')
        top.addWidget(self.wa_status_chip)
        l.addLayout(top)

        wa_card=QFrame()
        wa_card.setObjectName('card')
        wal=QVBoxLayout(wa_card)

        wh=QHBoxLayout()
        wt=QLabel('WhatsApp Web')
        wt.setStyleSheet('font-size:18px;font-weight:900')
        wh.addWidget(wt)
        wh.addStretch()
        info=QLabel('Max, WhatsApp\'ı ayrı Google Chrome penceresinde güvenilir biçimde okur.')
        info.setStyleSheet(f'color:{MUTED};font-size:11px')
        wh.addWidget(info)
        wal.addLayout(wh)

        prefix=self.settings.get('command_prefix','#')
        self.chrome_info=QLabel(
            'Google Chrome otomatik açılır. İlk kullanımda QR kodunu bir kez okutun; '
            'oturum daha sonraki açılışlarda korunur. Chrome penceresinde hedef sohbeti '
            'açık bırakabilirsiniz. Max hem sizin hem de diğer grup üyelerinin yeni '
            f'{prefix} komutlarını okuyup aynı sohbette yanıtlar.'
        )
        self.chrome_info.setWordWrap(True)
        self.chrome_info.setAlignment(Qt.AlignCenter)
        self.chrome_info.setStyleSheet(
            f'font-size:16px;font-weight:700;color:{TEXT};padding:45px;'
            f'background:{BG};border:1px solid {BORDER};border-radius:12px'
        )
        wal.addWidget(self.chrome_info,1)

        show_chrome=QPushButton('WHATSAPP CHROME PENCERESİNİ GÖSTER')
        show_chrome.setObjectName('green')
        wal.addWidget(show_chrome)

        l.addWidget(wa_card,1)
        self.stack.addWidget(p)

        self.wabot=ExternalWhatsAppBot(
            lambda text:command_response(
                self.db.all(),text,
                prefix=self.settings.get('command_prefix','#'),
                search_sources=self.settings.get('search_sources'),
                search_fields=self.settings.get('search_fields'),
            ),
            profile_dir=app_data()/'whatsapp-chrome-profile',
            initial_group=self.settings.get('group',''),
            start_active=bool(self.settings.get('bot')),
            command_prefix=self.settings.get('command_prefix','#'),
        )
        self.wabot.status.connect(self._wa_status)
        show_chrome.clicked.connect(self.wabot.show_browser)
        QApplication.instance().aboutToQuit.connect(self.wabot.shutdown)

    def _new_listing_table(self):
        table=QTableWidget(0,12)
        table.setHorizontalHeaderLabels([
            'Kaynak','Danışman / İlan Sahibi','Telefon','Başlık','Fiyat',
            'Bölge','Adres','Oda','m²','Tür','İlan Tarihi','İlan Linki'
        ])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.itemSelectionChanged.connect(lambda t=table:self._remember_listing_table(t))
        [table.horizontalHeader().setSectionResizeMode(c,QHeaderView.Stretch) for c in [1,3,5,6,11]]
        table.cellDoubleClicked.connect(lambda row,_col,t=table:self.open_link(t,row))
        return table

    def _listings(self):
        p,l=self._page()
        self._last_listing_table=None

        top=QHBoxLayout()
        title=QLabel('İlanlar')
        title.setStyleSheet('font-size:25px;font-weight:900')
        top.addWidget(title)
        top.addStretch()
        self.total_label=QLabel('Toplam İlan: 0')
        self.total_label.setStyleSheet(f'font-size:15px;font-weight:900;color:{BLUE};padding:6px 12px;background:white;border:1px solid {BORDER};border-radius:8px')
        top.addWidget(self.total_label)
        l.addLayout(top)

        listing_card=QFrame()
        listing_card.setObjectName('card')
        ll=QVBoxLayout(listing_card)

        lh=QHBoxLayout()
        lt=QLabel('İlan Tarama ve İlan Havuzu')
        lt.setStyleSheet('font-size:18px;font-weight:900')
        lh.addWidget(lt)
        lh.addStretch()
        self.scanstatus=QLabel('Beklemede')
        self.scanprog=QLabel('0 / 0')
        lh.addWidget(self.scanstatus)
        lh.addWidget(self.scanprog)
        ll.addLayout(lh)

        actions=QHBoxLayout()

        self.source_combo=QComboBox()
        self.source_combo.addItems(list(SOURCES.keys()))
        actions.addWidget(self.source_combo)

        scan=QPushButton('TARA / GÜNCELLE')
        scan.setObjectName('blue')
        scan.clicked.connect(self.scan_selected)
        actions.addWidget(scan)

        editb=QPushButton('SEÇİLİ İLANI DÜZENLE')
        editb.setObjectName('ghost')
        editb.clicked.connect(self.edit_selected_listing)
        actions.addWidget(editb)
        actions.addStretch()
        ll.addLayout(actions)

        note=QLabel('TARA / GÜNCELLE seçilen kaynağı açar. Dosya yükleme ve Excel dışa aktarma işlemleri Veri Ekle sayfasından yapılır.')
        note.setWordWrap(True)
        note.setStyleSheet(f'color:{MUTED};font-size:11px;padding:2px 0 6px 0')
        ll.addWidget(note)

        filters=QHBoxLayout()
        self.advisor_filter=QComboBox()
        self.advisor_filter.addItem('Tüm Danışmanlar')
        self.advisor_filter.currentTextChanged.connect(self.apply_filters)

        self.trans_filter=QComboBox()
        self.trans_filter.addItems(['Tümü','Satılık','Kiralık'])

        self.location_filter=QLineEdit()
        self.location_filter.setPlaceholderText('İl / ilçe / mahalle')

        self.min_price=QLineEdit()
        self.min_price.setPlaceholderText('Min fiyat')

        self.max_price=QLineEdit()
        self.max_price.setPlaceholderText('Maks fiyat')

        self.searchbox=QLineEdit()
        self.searchbox.setPlaceholderText('Kelime, ilan no, mahalle...')

        for w in [self.advisor_filter,self.trans_filter,self.location_filter,self.min_price,self.max_price,self.searchbox]:
            filters.addWidget(w)

        searchb=QPushButton('ARA')
        searchb.setObjectName('blue')
        searchb.clicked.connect(self.apply_filters)
        filters.addWidget(searchb)

        clear=QPushButton('TEMİZLE')
        clear.setObjectName('ghost')
        clear.clicked.connect(self.clear_filters)
        filters.addWidget(clear)
        ll.addLayout(filters)

        self.listing_tabs=QTabWidget()
        self.site_tables={}
        for site in ['Sahibinden','Emlakjet','MyRE/MAX']:
            table=self._new_listing_table()
            self.site_tables[site]=table
            self.listing_tabs.addTab(table,site)
        self.listing_tabs.currentChanged.connect(self._listing_tab_changed)
        ll.addWidget(self.listing_tabs,1)

        self.other_box=QGroupBox('İçe Aktarılan / Kaynağı Belirsiz')
        other_layout=QVBoxLayout(self.other_box)
        self.other_table=self._new_listing_table()
        self.other_table.setMaximumHeight(210)
        other_layout.addWidget(self.other_table)
        ll.addWidget(self.other_box)

        l.addWidget(listing_card,1)
        self.stack.addWidget(p)

        self.sc=PlaywrightScanner(app_data()/'browser-profile')
        self.sc.progress.connect(self.scanprog.setText)
        self.sc.status.connect(self.scanstatus.setText)
        self.sc.failed.connect(self.scan_failed)
        self.sc.done.connect(self.scan_done)
        self.sc.busy_changed.connect(self._scanner_busy_changed)
        self.sc.verification_needed.connect(self.scan_verification)
        self.auto_scan_queue=AutoScanQueue(SOURCES)
        self._auto_advance_pending=False

    def _data(self):
        p,l=self._page()
        t=QLabel('Veri Ekle')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        info=QLabel('Dosyadan veri ekleme, manuel kayıt ve Excel dışa aktarma işlemlerini bu sayfadan yönetebilirsiniz.')
        info.setStyleSheet(f'color:{MUTED}')
        l.addWidget(info)

        movement=QHBoxLayout()

        import_box=QGroupBox('Dosyadan Veri Ekle')
        import_layout=QVBoxLayout(import_box)
        import_note=QLabel('Excel veya CSV dosyasındaki ilanları kaynak bilgileriyle ilan havuzuna ekler.')
        import_note.setWordWrap(True)
        import_layout.addWidget(import_note)
        imp=QPushButton('EXCEL / CSV YÜKLE')
        imp.setObjectName('blue')
        imp.clicked.connect(self.import_file)
        import_layout.addWidget(imp)
        template_button=QPushButton('YAPAY ZEKÂ EXCEL ŞABLONU')
        template_button.setObjectName('ghost')
        template_button.clicked.connect(self.save_ai_template)
        import_layout.addWidget(template_button)
        movement.addWidget(import_box,1)

        export_box=QGroupBox('Verileri Dışarı Aktar')
        export_layout=QVBoxLayout(export_box)
        export_note=QLabel('Seçilen sitenin bütün ilanlarını Excel veya CSV dosyası olarak kaydeder.')
        export_note.setWordWrap(True)
        export_layout.addWidget(export_note)
        export_formats=QLabel('Desteklenen biçimler: Excel (*.xlsx);;CSV (*.csv)')
        export_formats.setStyleSheet(f'color:{MUTED};font-size:11px')
        export_layout.addWidget(export_formats)
        export_row=QHBoxLayout()
        self.export_source=QComboBox()
        self.export_source.addItems(list(LINK_SOURCES))
        self.export_source.setCurrentText(list(self.site_tables)[self.listing_tabs.currentIndex()])
        export_row.addWidget(self.export_source)
        exportb=QPushButton("VERİLERİ EXCEL'E AKTAR")
        exportb.setObjectName('ghost')
        exportb.clicked.connect(self.export_selected_site)
        export_row.addWidget(exportb)
        export_layout.addLayout(export_row)
        movement.addWidget(export_box,1)

        l.addLayout(movement)

        box=QGroupBox('Manuel İlan Ekle')
        f=QFormLayout(box)
        self.m_title=QLineEdit()
        self.m_adv=QLineEdit()
        self.m_phone=QLineEdit()
        self.m_price=QLineEdit()
        self.m_loc=QLineEdit()
        self.m_rooms=QLineEdit()
        self.m_type=QLineEdit()
        self.m_url=QLineEdit()
        for label,w in [('Başlık',self.m_title),('Danışman',self.m_adv),('Telefon',self.m_phone),('Fiyat',self.m_price),('Bölge',self.m_loc),('Oda',self.m_rooms),('Tür',self.m_type),('İlan Linki',self.m_url)]:
            f.addRow(label,w)

        b=QPushButton('MANUEL İLANI KAYDET')
        b.setObjectName('red')
        b.clicked.connect(self.manual_add)
        f.addRow('',b)

        l.addWidget(box)
        l.addStretch()
        self.stack.addWidget(p)

    def _web(self):
        p,l=self._page()
        t=QLabel('Web Sekmeleri / İlan Tarayıcı')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        row=QHBoxLayout()
        self.web_source=QComboBox()
        self.web_source.addItems(list(SOURCES.keys()))
        openb=QPushButton('KAYNAĞI AÇ')
        openb.setObjectName('ghost')
        row.addWidget(self.web_source)
        row.addWidget(openb)
        row.addStretch()
        l.addLayout(row)

        self.browser=QWebEngineView()
        self.browser.setPage(QWebEnginePage(self.profile,self.browser))
        self.browser.setUrl(QUrl(SOURCES['MyRE/MAX ÇARŞI']))
        l.addWidget(self.browser,1)
        self.stack.addWidget(p)
        openb.clicked.connect(lambda:self.browser.setUrl(QUrl(SOURCES[self.web_source.currentText()])))

    def _bot_test(self):
        p,l=self._page()
        t=QLabel('Bot Testi')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        test=QGroupBox('Bot Komut Testi')
        tf=QVBoxLayout(test)
        self.quick_cmd=QLineEdit()
        prefix=self.settings.get('command_prefix','#')
        self.quick_cmd.setPlaceholderText(f'{prefix}Max başla / {prefix}? / {prefix}danışmanlar / {prefix}izmit kiralık 55 bin')
        cb=QPushButton('KOMUTU TEST ET')
        cb.setObjectName('blue')
        cb.clicked.connect(self.quick_test)
        tf.addWidget(self.quick_cmd)
        tf.addWidget(cb)

        result_head=QHBoxLayout()
        result_label=QLabel('Bot Komut Sonucu')
        result_label.setStyleSheet(f'color:{MUTED};font-size:11px;font-weight:800')
        self.quick_toggle=QPushButton('▲ SONUCU GİZLE')
        self.quick_toggle.setObjectName('ghost')
        self.quick_toggle.clicked.connect(self.toggle_quick_result)
        result_head.addWidget(result_label)
        result_head.addStretch()
        result_head.addWidget(self.quick_toggle)
        tf.addLayout(result_head)

        self.quick_result=QPlainTextEdit()
        self.quick_result.setReadOnly(True)
        self.quick_result.setMaximumHeight(220)
        self.quick_result.setPlainText(f'Komutun yalnızca başında {prefix} olması yeterlidir.')
        tf.addWidget(self.quick_result)
        l.addWidget(test)

        commands=QGroupBox('Komut Listesi')
        cf=QVBoxLayout(commands)
        self.commandlist=QPlainTextEdit()
        self.commandlist.setReadOnly(True)
        self.commandlist.setPlainText(command_help())
        if prefix!='#':self.commandlist.setPlainText(command_help(prefix=prefix))
        self.commandlist.setMinimumHeight(280)
        cf.addWidget(self.commandlist)
        l.addWidget(commands,1)
        self.stack.addWidget(p)

    def _settings(self):
        p,outer=self._page()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content=QWidget()
        l=QVBoxLayout(content)
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        t=QLabel('Ayarlar')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        f=QFormLayout()
        self.group=QLineEdit(self.settings.get('group',''))
        self.group.setPlaceholderText(
            f"Boşsa {self.settings.get('command_prefix','#')}Max başla yazılan açık sohbet kullanılır."
        )
        self.sound=QCheckBox('Bildirim sesi açık')
        self.sound.setChecked(self.settings.get('sound',True))
        self.days=QSpinBox()
        self.days.setRange(1,60)
        self.days.setValue(self.settings.get('days',7))
        self.days.setSuffix(' gün')
        f.addRow('WhatsApp grup/sohbet adı:',self.group)
        f.addRow('Bildirim:',self.sound)
        f.addRow('Güncelleme hatırlatması:',self.days)
        l.addLayout(f)

        max_box=QGroupBox('Max Arama Ayarları')
        max_layout=QVBoxLayout(max_box)
        prefix_form=QFormLayout()
        self.command_prefix=QLineEdit(self.settings.get('command_prefix','#'))
        self.command_prefix.setMaxLength(1)
        self.command_prefix.setFixedWidth(80)
        prefix_form.addRow('Komut işareti:',self.command_prefix)
        max_layout.addLayout(prefix_form)

        search_columns=QHBoxLayout()
        source_column=QVBoxLayout()
        source_column.addWidget(QLabel('Aranacak kaynaklar'))
        self.search_source_checks={}
        selected_sources=set(self.settings.get('search_sources',DEFAULT_SEARCH_SOURCES))
        for source in DEFAULT_SEARCH_SOURCES:
            check=QCheckBox(source)
            check.setChecked(source in selected_sources)
            self.search_source_checks[source]=check
            source_column.addWidget(check)
        source_column.addStretch()
        search_columns.addLayout(source_column,1)

        field_column=QVBoxLayout()
        field_column.addWidget(QLabel('Aranacak veri alanları'))
        field_grid=QGridLayout()
        self.search_field_checks={}
        selected_fields=set(self.settings.get('search_fields',DEFAULT_SEARCH_FIELDS))
        for index,field in enumerate(DEFAULT_SEARCH_FIELDS):
            check=QCheckBox(SEARCH_FIELD_LABELS[field])
            check.setChecked(field in selected_fields)
            self.search_field_checks[field]=check
            field_grid.addWidget(check,index//2,index%2)
        field_column.addLayout(field_grid)
        search_columns.addLayout(field_column,2)
        max_layout.addLayout(search_columns)

        auto_note=QLabel('Sahibinden Excel/CSV yüklendikten sonra seçilen kaynaklar sırayla taranır.')
        auto_note.setWordWrap(True)
        auto_note.setStyleSheet(f'color:{MUTED};font-size:11px')
        max_layout.addWidget(auto_note)
        self.auto_scan_after_import=QCheckBox('Yükleme sonrası otomatik tarama')
        self.auto_scan_after_import.setChecked(self.settings.get('auto_scan_after_import',True))
        max_layout.addWidget(self.auto_scan_after_import)
        self.auto_scan_source_checks={}
        selected_auto=set(self.settings.get('auto_scan_sources',AUTO_SCAN_SOURCE_LABELS))
        auto_row=QHBoxLayout()
        for source in AUTO_SCAN_SOURCE_LABELS:
            check=QCheckBox(source)
            check.setChecked(source in selected_auto)
            self.auto_scan_source_checks[source]=check
            auto_row.addWidget(check)
        auto_row.addStretch()
        max_layout.addLayout(auto_row)
        l.addWidget(max_box)

        save=QPushButton('AYARLARI KAYDET')
        save.setObjectName('blue')
        save.clicked.connect(self.save_settings)
        l.addWidget(save,0,Qt.AlignLeft)

        merge_box=QGroupBox('Danışman İsimlerini Birleştir')
        merge_layout=QVBoxLayout(merge_box)
        merge_note=QLabel('Yalnızca işaretlediğiniz isimler birleştirilir. Aynı soyadlı diğer danışmanlar değiştirilmez; kural sonraki tarama ve yüklemelerde de uygulanır.')
        merge_note.setWordWrap(True)
        merge_note.setStyleSheet(f'color:{MUTED};font-size:11px')
        merge_layout.addWidget(merge_note)

        merge_columns=QHBoxLayout()
        available=QVBoxLayout()
        available.addWidget(QLabel('Tüm danışmanlar'))
        self.advisor_merge_search=QLineEdit()
        self.advisor_merge_search.setPlaceholderText('İsimlerde ara...')
        available.addWidget(self.advisor_merge_search)
        self.advisor_merge_list=QListWidget()
        self.advisor_merge_list.setMinimumHeight(190)
        available.addWidget(self.advisor_merge_list)
        merge_columns.addLayout(available,2)

        selected=QVBoxLayout()
        selected.addWidget(QLabel('Seçilen isimler'))
        self.advisor_merge_selected=QListWidget()
        self.advisor_merge_selected.setMinimumHeight(150)
        selected.addWidget(self.advisor_merge_selected)
        selected.addWidget(QLabel('Kullanılacak ana isim'))
        self.advisor_canonical=QComboBox()
        self.advisor_canonical.setEditable(True)
        self.advisor_canonical.setInsertPolicy(QComboBox.NoInsert)
        selected.addWidget(self.advisor_canonical)
        merge_columns.addLayout(selected,2)
        merge_layout.addLayout(merge_columns)

        merge_actions=QHBoxLayout()
        merge_button=QPushButton('BİRLEŞTİR VE GÜNCELLE')
        merge_button.setObjectName('blue')
        merge_button.clicked.connect(self.merge_selected_advisors)
        merge_actions.addWidget(merge_button)
        merge_actions.addStretch()
        self.advisor_alias_group=QComboBox()
        self.advisor_alias_group.setMinimumWidth(260)
        merge_actions.addWidget(self.advisor_alias_group)
        unmerge_button=QPushButton('BİRLEŞTİRMEYİ KALDIR')
        unmerge_button.setObjectName('ghost')
        unmerge_button.clicked.connect(self.unmerge_advisor_group)
        merge_actions.addWidget(unmerge_button)
        merge_layout.addLayout(merge_actions)
        l.addWidget(merge_box,1)

        self._advisor_merge_selection=set()
        self._updating_advisor_merge=False
        self.advisor_merge_search.textChanged.connect(self.refresh_advisor_merge_list)
        self.advisor_merge_list.itemChanged.connect(self.advisor_merge_item_changed)
        self.refresh_advisor_merge_list()

        self.stack.addWidget(p)

    def refresh(self,rows=None):
        all_rows=self.db.all()
        self.total_label.setText(f'Toplam İlan: {len(all_rows)}')
        active='Aktif' if self.settings.get('bot') else 'Durduruldu'
        color='#62E37D' if self.settings.get('bot') else '#FFB4B4'
        self.side_status.setText(f'●  Bot Durumu: {active}')
        self.side_status.setStyleSheet(f'color:{color};font-size:12px;padding:7px')

        current=self.advisor_filter.currentText() if hasattr(self,'advisor_filter') else 'Tüm Danışmanlar'
        if hasattr(self,'advisor_filter'):
            self.advisor_filter.blockSignals(True)
            self.advisor_filter.clear()
            self.advisor_filter.addItem('Tüm Danışmanlar')
            self.advisor_filter.addItems(advisor_names(all_rows))
            i=self.advisor_filter.findText(current)
            self.advisor_filter.setCurrentIndex(i if i>=0 else 0)
            self.advisor_filter.blockSignals(False)

        self.fill(all_rows if rows is None else rows)
        if hasattr(self,'advisor_merge_list'):
            self.refresh_advisor_merge_list()

    def fill(self,rows):
        buckets=split_listings_by_site(rows)
        for index,(site,table) in enumerate(self.site_tables.items()):
            site_rows=buckets[site]
            self.listing_tabs.setTabText(index,f'{site} ({len(site_rows)})')
            self._fill_listing_table(table,site_rows)
        other_rows=buckets['Diğer']
        self._fill_listing_table(self.other_table,other_rows)
        self.other_box.setVisible(bool(other_rows))

    def _fill_listing_table(self,table,rows):
        table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[
                source_label(x.source_url),advisor_display_name(x.advisor),x.phone,x.title,x.price,x.location,display_address(x),x.rooms,x.sqm,
                ' / '.join(v for v in [x.transaction_type,x.property_type] if v),x.listing_date,x.url
            ]
            for c,v in enumerate(vals):
                cell=QTableWidgetItem(v)
                if c==0: cell.setData(Qt.UserRole,(x.source_url,x.listing_id))
                table.setItem(r,c,cell)

    def apply_filters(self):
        advisor='' if self.advisor_filter.currentIndex()==0 else self.advisor_filter.currentText()
        trans='' if self.trans_filter.currentIndex()==0 else self.trans_filter.currentText()
        minp=price_number(self.min_price.text()) if self.min_price.text().strip() else None
        maxp=price_number(self.max_price.text()) if self.max_price.text().strip() else None
        rows=filter_listings(
            self.db.all(),
            advisor=advisor,
            transaction=trans,
            location=self.location_filter.text().strip(),
            min_price=minp,
            max_price=maxp,
            query=self.searchbox.text().strip()
        )
        self.fill(rows)
        self.total_label.setText(f'Toplam İlan: {len(rows)} / {self.db.count()}')

    def clear_filters(self):
        self.advisor_filter.setCurrentIndex(0)
        self.trans_filter.setCurrentIndex(0)
        for w in [self.location_filter,self.min_price,self.max_price,self.searchbox]:
            w.clear()
        self.refresh()

    def scan_selected(self):
        self.auto_scan_queue.start([])
        self._auto_advance_pending=False
        self.scanstatus.setText('Tarama başlatılıyor...')
        self.sc.start(SOURCES[self.source_combo.currentText()])

    def _start_auto_scan_queue(self):
        if not self.settings.get('auto_scan_after_import',True):return
        self.auto_scan_queue.start(self.settings.get('auto_scan_sources',AUTO_SCAN_SOURCE_LABELS))
        self._auto_advance_pending=self.sc.phase=='busy'
        if not self._auto_advance_pending:self._scan_next_queued_source()

    def _scan_next_queued_source(self):
        item=self.auto_scan_queue.next_item()
        if item is None:
            if self.auto_scan_queue.finished:
                self.scanstatus.setText('Yükleme sonrası otomatik taramalar tamamlandı.')
            return
        label,url=item
        self.scanstatus.setText(f'Otomatik tarama başlatılıyor: {label}')
        self.sc.start(url)

    def _complete_current_scan(self,success):
        if self.auto_scan_queue.current is None:return
        self.auto_scan_queue.complete(success)
        self._auto_advance_pending=True

    def _scanner_busy_changed(self,busy):
        if not busy and self._auto_advance_pending:
            self._auto_advance_pending=False
            self._scan_next_queued_source()

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'İlan Listesi Seç','','Excel (*.xlsx);;CSV (*.csv)')
        if not path:return
        try:
            items=read_list_file(path)
            self.db.upsert(items)
            self.db.setmeta('last_update',datetime.now().strftime('%d.%m.%Y %H:%M'))
            self.refresh()
            QMessageBox.information(self,'İçe Aktarma',f'{len(items)} ilan eklendi/güncellendi.')
            self._start_auto_scan_queue()
        except Exception as e:
            QMessageBox.warning(self,'İçe Aktarma',str(e))

    def save_ai_template(self):
        suggested='REMAX İlan Bot Şablon.xlsx'
        path,_=QFileDialog.getSaveFileName(self,'Yapay Zekâ Excel Şablonunu Kaydet',suggested,'Excel (*.xlsx)')
        if not path:return
        if not path.lower().endswith('.xlsx'):path+='.xlsx'
        try:
            write_ai_template(path)
            QMessageBox.information(self,'Excel Şablonu',f'Şablon kaydedildi.\n{path}')
        except Exception as error:
            QMessageBox.warning(self,'Excel Şablonu',str(error))

    def export_selected_site(self):
        site=self.export_source.currentText()
        rows=split_listings_by_site(self.db.all())[site]
        if not rows:
            QMessageBox.warning(self,'Excel Dışa Aktarma',f'{site} listesinde aktarılacak ilan yok.')
            return
        stamp=datetime.now().strftime('%Y%m%d')
        suggested=f"REMAX_{site.replace('/','-')}_{stamp}.xlsx"
        path,selected_filter=QFileDialog.getSaveFileName(
            self,'İlanları Dışa Aktar',suggested,'Excel (*.xlsx);;CSV (*.csv)'
        )
        if not path:return
        if not path.lower().endswith(('.xlsx','.csv')):
            path+='.csv' if selected_filter.startswith('CSV') else '.xlsx'
        try:
            write_list_file(path,rows)
            QMessageBox.information(self,'Dışa Aktarma',f'{site}: {len(rows)} ilan kaydedildi.\n{path}')
        except Exception as error:
            QMessageBox.warning(self,'Dışa Aktarma',str(error))

    def edit_selected_listing(self):
        current_table=self.listing_tabs.currentWidget()
        table=self._last_listing_table
        if table is None or table.currentRow()<0:
            table=current_table
        row=table.currentRow()
        if row<0:
            QMessageBox.warning(self,'İlan Düzenle','Önce tablodan bir ilan seçin.')
            return
        identity=table.item(row,0).data(Qt.UserRole) if table.item(row,0) else None
        if not identity:
            QMessageBox.warning(self,'İlan Düzenle','Seçilen ilanın kayıt bilgisi bulunamadı.')
            return
        original_source,original_id=identity
        raw_item=self.db.raw_listing(original_source,original_id)
        item=next((x for x in self.db.all() if source_key(x.source_url)==source_key(original_source) and str(x.listing_id)==str(original_id)),None)
        if item is None or raw_item is None:
            QMessageBox.warning(self,'İlan Düzenle','Seçilen ilan veritabanında bulunamadı.')
            return
        dialog=ListingEditDialog(item,self,raw_item=raw_item)
        if dialog.exec()!=QDialog.Accepted:return
        updated=dialog.edited_listing()
        try:
            self.db.update_listing(original_source,original_id,updated)
        except ValueError as error:
            QMessageBox.warning(self,'İlan Düzenle',str(error))
            return
        self.refresh()
        QMessageBox.information(self,'İlan Düzenle','İlan bilgileri güncellendi.')

    def _remember_listing_table(self,table):
        if table.selectionModel().hasSelection():
            self._last_listing_table=table

    def _listing_tab_changed(self,_index):
        self._last_listing_table=None

    def manual_add(self):
        title=self.m_title.text().strip()
        url=self.m_url.text().strip()
        if not title and not url:
            QMessageBox.warning(self,'Manuel İlan','Başlık veya ilan linki girin.')
            return
        m=re.search(r'(?:P)?(\d{5,})',url)
        lid=m.group(1) if m else str(int(datetime.now().timestamp()*1000))
        x=Listing(
            lid,title or f'İlan {lid}',url,self.m_adv.text().strip(),self.m_phone.text().strip(),
            self.m_price.text().strip(),self.m_loc.text().strip(),self.m_rooms.text().strip(),
            '',self.m_type.text().strip(),'','', 'manual://entry'
        )
        self.db.add_one(x)
        self.refresh()
        QMessageBox.information(self,'Manuel İlan','İlan kaydedildi.')

    def bot_start(self):
        self.settings['bot']=True
        self.settings['group']=self.group.text().strip() if hasattr(self,'group') else self.settings.get('group','')
        self._save_settings()
        self.wabot.start(self.settings.get('group',''))
        self.refresh()

    def bot_stop(self):
        self.settings['bot']=False
        self._save_settings()
        self.wabot.stop()
        self.refresh()

    def _wa_status(self,msg):
        self.wa_status_chip.setText(msg)

    def quick_test(self):
        out=command_response(
            self.db.all(),self.quick_cmd.text().strip(),
            prefix=self.settings.get('command_prefix','#'),
            search_sources=self.settings.get('search_sources'),
            search_fields=self.settings.get('search_fields'),
        )
        self.quick_result.setPlainText(out or 'Bot bu mesajı görmezden gelir.')
        self.quick_result.setVisible(True)
        self.quick_toggle.setText('▲ SONUCU GİZLE')

    def toggle_quick_result(self):
        visible=self.quick_result.isVisible()
        self.quick_result.setVisible(not visible)
        self.quick_toggle.setText('▼ SONUCU GÖSTER' if visible else '▲ SONUCU GİZLE')

    def save_settings(self):
        prefix=normalize_command_prefix(self.command_prefix.text())
        sources=[name for name,check in self.search_source_checks.items() if check.isChecked()]
        fields=[name for name,check in self.search_field_checks.items() if check.isChecked()]
        auto_sources=[name for name,check in self.auto_scan_source_checks.items() if check.isChecked()]
        self.settings.update(
            group=self.group.text().strip(),
            sound=self.sound.isChecked(),
            days=self.days.value(),
            command_prefix=prefix,
            search_sources=sources,
            search_fields=fields,
            auto_scan_after_import=self.auto_scan_after_import.isChecked(),
            auto_scan_sources=auto_sources,
        )
        self._save_settings()
        self.command_prefix.setText(prefix)
        self.wabot.set_group(self.settings.get('group',''))
        self.wabot.set_command_prefix(prefix)
        self.commandlist.setPlainText(command_help(prefix=prefix))
        self.quick_cmd.setPlaceholderText(f'{prefix}Max başla / {prefix}? / {prefix}danışmanlar / {prefix}izmit kiralık 55 bin')
        self.quick_result.setPlainText(f'Komutun yalnızca başında {prefix} olması yeterlidir.')
        self.group.setPlaceholderText(f'Boşsa {prefix}Max başla yazılan açık sohbet kullanılır.')
        self.chrome_info.setText(
            'Google Chrome otomatik açılır. İlk kullanımda QR kodunu bir kez okutun; '
            'oturum daha sonraki açılışlarda korunur. Chrome penceresinde hedef sohbeti '
            'açık bırakabilirsiniz. Max hem sizin hem de diğer grup üyelerinin yeni '
            f'{prefix} komutlarını okuyup aynı sohbette yanıtlar.'
        )
        self.refresh()

    def refresh_advisor_merge_list(self,*_args):
        if not hasattr(self,'advisor_merge_list'):return
        query=norm(self.advisor_merge_search.text())
        names=[name for name in self.db.raw_advisor_names() if is_valid_advisor(name)]
        self._updating_advisor_merge=True
        self.advisor_merge_list.clear()
        for name in names:
            if query and query not in norm(name):continue
            item=QListWidgetItem(name)
            item.setData(Qt.UserRole,name)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in self._advisor_merge_selection else Qt.CheckState.Unchecked)
            self.advisor_merge_list.addItem(item)
        self._updating_advisor_merge=False
        self._refresh_advisor_merge_summary()

    def advisor_merge_item_changed(self,item):
        if self._updating_advisor_merge:return
        name=item.data(Qt.UserRole)
        if item.checkState()==Qt.CheckState.Checked:self._advisor_merge_selection.add(name)
        else:self._advisor_merge_selection.discard(name)
        self._refresh_advisor_merge_summary()

    def _refresh_advisor_merge_summary(self):
        names=sorted(self._advisor_merge_selection,key=norm)
        self.advisor_merge_selected.clear()
        self.advisor_merge_selected.addItems(names)
        current=self.advisor_canonical.currentText().strip()
        self.advisor_canonical.blockSignals(True)
        self.advisor_canonical.clear()
        self.advisor_canonical.addItems(names)
        if not names:self.advisor_canonical.setEditText('')
        elif current:self.advisor_canonical.setEditText(current)
        elif names:self.advisor_canonical.setCurrentText(names[0])
        self.advisor_canonical.blockSignals(False)

        current_group=self.advisor_alias_group.currentData()
        groups={}
        for alias,canonical in self.db.advisor_aliases():
            groups.setdefault(canonical,[]).append(alias)
        self.advisor_alias_group.clear()
        for canonical,aliases in sorted(groups.items(),key=lambda pair:norm(pair[0])):
            self.advisor_alias_group.addItem(f'{canonical} ({len(aliases)} isim)',canonical)
        if current_group:
            index=self.advisor_alias_group.findData(current_group)
            if index>=0:self.advisor_alias_group.setCurrentIndex(index)

    def merge_selected_advisors(self):
        names=sorted(self._advisor_merge_selection,key=norm)
        canonical=self.advisor_canonical.currentText().strip()
        if not names or not canonical:
            QMessageBox.warning(self,'Danışman Birleştirme','En az bir danışman seçin ve kullanılacak ana ismi yazın.')
            return
        self.db.merge_advisors(names,canonical)
        self._advisor_merge_selection.clear()
        self.refresh()
        QMessageBox.information(self,'Danışman Birleştirme',f'{len(names)} isim “{canonical}” altında birleştirildi.')

    def unmerge_advisor_group(self):
        canonical=self.advisor_alias_group.currentData()
        if not canonical:
            QMessageBox.warning(self,'Danışman Birleştirme','Kaldırılacak bir birleştirme seçin.')
            return
        self.db.unmerge_advisor(canonical)
        self._advisor_merge_selection.clear()
        self.refresh()
        QMessageBox.information(self,'Danışman Birleştirme',f'“{canonical}” birleştirmesi kaldırıldı.')

    def open_link(self,table,row):
        x=table.item(row,11)
        if x and x.text():
            self._go(3)
            self.nav_buttons[3].setChecked(True)
            self.browser.setUrl(QUrl(x.text()))

    def scan_verification(self,msg):
        self.scanstatus.setText(msg)
        QMessageBox.information(self,'Kullanıcı İşlemi Gerekiyor',msg)

    def scan_failed(self,msg):
        self.scanstatus.setText(msg)
        self._complete_current_scan(False)
        QMessageBox.warning(self,'Tarama',msg)

    def scan_done(self,source,rows):
        try:
            if rows:
                self.db.replace_source(source,rows)
                stamp=datetime.now().strftime('%d.%m.%Y %H:%M')
                self.db.setmeta('last_update',stamp)
                self.db.setmeta('last_source',source)
                self.refresh()
                self.scanstatus.setText(f'{source_label(source)} güncellendi: {len(rows)} ilan.')
                if self.settings.get('sound'):QApplication.beep()
            else:
                self.scanstatus.setText(f'{source_label(source)} için ilan bulunamadı; eski veriler korundu.')
        finally:
            self._complete_current_scan(bool(rows))

def main():
    app=QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(asset('app_icon.png'))))
    w=Main()
    w.show()
    sys.exit(app.exec())

if __name__=='__main__':
    main()
