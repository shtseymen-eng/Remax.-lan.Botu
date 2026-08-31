from __future__ import annotations
import os,sys,re,json
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt,QUrl,QPointF
from PySide6.QtGui import QPixmap,QIcon,QPainter,QPolygonF,QFont
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage

from .core import DB,Listing,source_label
from .playwright_scanner import PlaywrightScanner
from .importer import read_list_file,command_response,command_help,advisor_names,filter_listings,price_number
from .whatsapp_bot import WhatsAppBot

BLUE='#0B4DB8';NAVY='#062D69';RED='#E31837';GREEN='#13A84A'
BG='#F4F7FB';CARD='#FFFFFF';BORDER='#D9E2EF';TEXT='#172033';MUTED='#667085'
SOURCES={
    'RE/MAX ÇARŞI':'https://remax.com.tr/tr/ofis/detay/carsi?tab=portfoylerimiz',
    'RE/MAX ÇARŞI 2':'https://remax.com.tr/tr/ofis/detay/carsi-2?tab=portfoylerimiz'
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

        self.wa_profile=QWebEngineProfile('RemaxWhatsApp',self)
        self.wa_profile.setPersistentStoragePath(str(d/'whatsapp-profile'))
        self.wa_profile.setCachePath(str(d/'whatsapp-cache'))
        self.wa_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.wa_profile.setHttpAcceptLanguage('tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7')

        self._build()
        self._style()
        self.refresh()

    def _load_settings(self):
        base={'group':'','sound':True,'bot':False,'days':7}
        try:
            if self.cfg.exists():
                base.update(json.loads(self.cfg.read_text(encoding='utf-8')))
        except Exception:
            pass
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
        for i,t in enumerate(['Ana Sayfa','Veri Ekle','Web Sekmeleri','Ayarlar']):
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

        ver=QLabel('v30.0.0  •  RE/MAX ÇARŞI')
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet('color:#8FA9CC;font-size:10px')
        sl.addWidget(ver)

        outer.addWidget(side)
        outer.addWidget(self.stack,1)

        self._home()
        self._data()
        self._web()
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
        self.total_label=QLabel('Toplam İlan: 0')
        self.total_label.setStyleSheet(f'font-size:15px;font-weight:900;color:{BLUE};padding:6px 12px;background:white;border:1px solid {BORDER};border-radius:8px')
        top.addWidget(self.total_label)
        l.addLayout(top)

        split=QSplitter(Qt.Vertical)

        wa_card=QFrame()
        wa_card.setObjectName('card')
        wal=QVBoxLayout(wa_card)
        wh=QHBoxLayout()
        wt=QLabel('WhatsApp Web')
        wt.setStyleSheet('font-size:18px;font-weight:900')
        wh.addWidget(wt)
        wh.addStretch()
        self.wa_status_chip=QLabel('Web sekmesi hazır')
        self.wa_status_chip.setStyleSheet('color:#087A3B;font-weight:800')
        wh.addWidget(self.wa_status_chip)
        wal.addLayout(wh)

        self.wa=QWebEngineView()
        self.wa.setPage(QWebEnginePage(self.wa_profile,self.wa))
        self.wa.setUrl(QUrl('https://web.whatsapp.com/'))
        self.wa.setMinimumHeight(300)
        wal.addWidget(self.wa,1)

        cmdrow=QHBoxLayout()
        self.quick_cmd=QLineEdit()
        self.quick_cmd.setPlaceholderText('#bot başlat   veya   #izmit kiralık 55 bin')
        sendcmd=QPushButton('KOMUTU TEST ET')
        sendcmd.setObjectName('blue')
        sendcmd.clicked.connect(self.quick_test)
        cmdrow.addWidget(self.quick_cmd,1)
        cmdrow.addWidget(sendcmd)
        wal.addLayout(cmdrow)

        self.quick_result=QLabel('Komutun yalnızca başında # olması yeterlidir.')
        self.quick_result.setWordWrap(True)
        self.quick_result.setStyleSheet(f'color:{MUTED};font-size:11px')
        wal.addWidget(self.quick_result)

        listing_card=QFrame()
        listing_card.setObjectName('card')
        ll=QVBoxLayout(listing_card)

        lh=QHBoxLayout()
        lt=QLabel('İlanlar')
        lt.setStyleSheet('font-size:18px;font-weight:900')
        lh.addWidget(lt)
        self.source_combo=QComboBox()
        self.source_combo.addItems(list(SOURCES.keys()))
        lh.addWidget(self.source_combo)
        scan=QPushButton('TARA / GÜNCELLE')
        scan.setObjectName('blue')
        scan.clicked.connect(self.scan_selected)
        lh.addWidget(scan)
        importb=QPushButton('EXCEL / CSV YÜKLE')
        importb.setObjectName('ghost')
        importb.clicked.connect(self.import_file)
        lh.addWidget(importb)
        lh.addStretch()
        self.scanstatus=QLabel('Beklemede')
        self.scanprog=QLabel('0 / 0')
        lh.addWidget(self.scanstatus)
        lh.addWidget(self.scanprog)
        ll.addLayout(lh)

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

        self.table=QTableWidget(0,11)
        self.table.setHorizontalHeaderLabels(['Kaynak','Danışman / İlan Sahibi','Telefon','Başlık','Fiyat','Bölge','Oda','m²','Tür','İlan Tarihi','İlan Linki'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        [self.table.horizontalHeader().setSectionResizeMode(c,QHeaderView.Stretch) for c in [1,3,5,10]]
        self.table.cellDoubleClicked.connect(self.open_link)
        ll.addWidget(self.table,1)

        split.addWidget(wa_card)
        split.addWidget(listing_card)
        split.setStretchFactor(0,1)
        split.setStretchFactor(1,2)
        l.addWidget(split,1)
        self.stack.addWidget(p)

        self.wabot=WhatsAppBot(self.wa,lambda text:command_response(self.db.all(),text))
        self.wabot.status.connect(self._wa_status)

        self.sc=PlaywrightScanner(app_data()/'browser-profile')
        self.sc.progress.connect(self.scanprog.setText)
        self.sc.status.connect(self.scanstatus.setText)
        self.sc.failed.connect(self.scan_failed)
        self.sc.done.connect(self.scan_done)
        self.sc.verification_needed.connect(self.scan_verification)

    def _data(self):
        p,l=self._page()
        t=QLabel('Veri Ekle')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        info=QLabel('Excel/CSV içe aktarımı ve manuel kayıt mevcut ilan havuzuna eklenir.')
        info.setStyleSheet(f'color:{MUTED}')
        l.addWidget(info)

        imp=QPushButton('EXCEL / CSV YÜKLE')
        imp.setObjectName('blue')
        imp.clicked.connect(self.import_file)
        l.addWidget(imp,0,Qt.AlignLeft)

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
        self.browser.setUrl(QUrl(SOURCES['RE/MAX ÇARŞI']))
        l.addWidget(self.browser,1)
        self.stack.addWidget(p)
        openb.clicked.connect(lambda:self.browser.setUrl(QUrl(SOURCES[self.web_source.currentText()])))

    def _settings(self):
        p,l=self._page()
        t=QLabel('Ayarlar')
        t.setStyleSheet('font-size:24px;font-weight:900')
        l.addWidget(t)

        f=QFormLayout()
        self.group=QLineEdit(self.settings.get('group',''))
        self.group.setPlaceholderText('İsteğe bağlı. Boşsa açık WhatsApp sohbeti kullanılır.')
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

        save=QPushButton('AYARLARI KAYDET')
        save.setObjectName('blue')
        save.clicked.connect(self.save_settings)
        l.addWidget(save,0,Qt.AlignLeft)

        test=QGroupBox('Bot Komut Testi')
        tf=QVBoxLayout(test)
        self.cmdtest=QLineEdit()
        self.cmdtest.setPlaceholderText('#bot başlat / #? / #danışmanlar / #izmit kiralık 55 bin')
        self.cmdout=QPlainTextEdit()
        self.cmdout.setReadOnly(True)
        cb=QPushButton('KOMUTU TEST ET')
        cb.setObjectName('blue')
        cb.clicked.connect(self.test_command)
        tf.addWidget(self.cmdtest)
        tf.addWidget(cb)
        tf.addWidget(self.cmdout)
        l.addWidget(test)

        commands=QGroupBox('Komut Listesi')
        cf=QVBoxLayout(commands)
        self.commandlist=QPlainTextEdit()
        self.commandlist.setReadOnly(True)
        self.commandlist.setPlainText(command_help())
        self.commandlist.setMinimumHeight(250)
        cf.addWidget(self.commandlist)
        l.addWidget(commands)

        l.addStretch()
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

    def fill(self,rows):
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[
                source_label(x.source_url),x.advisor,x.phone,x.title,x.price,x.location,x.rooms,x.sqm,
                ' / '.join(v for v in [x.transaction_type,x.property_type] if v),x.listing_date,x.url
            ]
            for c,v in enumerate(vals):
                self.table.setItem(r,c,QTableWidgetItem(v))

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
        self.scanstatus.setText('Tarama başlatılıyor...')
        self.sc.start(SOURCES[self.source_combo.currentText()])

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'İlan Listesi Seç','','Excel (*.xlsx);;CSV (*.csv)')
        if not path:return
        try:
            items=read_list_file(path)
            self.db.upsert(items)
            self.db.setmeta('last_update',datetime.now().strftime('%d.%m.%Y %H:%M'))
            self.refresh()
            QMessageBox.information(self,'İçe Aktarma',f'{len(items)} ilan eklendi/güncellendi.')
        except Exception as e:
            QMessageBox.warning(self,'İçe Aktarma',str(e))

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
        out=command_response(self.db.all(),self.quick_cmd.text().strip())
        self.quick_result.setText(out or 'Bot bu mesajı görmezden gelir.')

    def test_command(self):
        out=command_response(self.db.all(),self.cmdtest.text().strip())
        self.cmdout.setPlainText(out or 'Bot bu mesajı görmezden gelir.')

    def save_settings(self):
        self.settings.update(
            group=self.group.text().strip(),
            sound=self.sound.isChecked(),
            days=self.days.value()
        )
        self._save_settings()
        self.refresh()

    def open_link(self,row,col):
        x=self.table.item(row,10)
        if x and x.text():
            self._go(2)
            self.nav_buttons[2].setChecked(True)
            self.browser.setUrl(QUrl(x.text()))

    def scan_verification(self,msg):
        self.scanstatus.setText(msg)
        QMessageBox.information(self,'Kullanıcı İşlemi Gerekiyor',msg)

    def scan_failed(self,msg):
        self.scanstatus.setText(msg)
        QMessageBox.warning(self,'Tarama',msg)

    def scan_done(self,source,rows):
        if not rows:return
        self.db.replace_source(source,rows)
        stamp=datetime.now().strftime('%d.%m.%Y %H:%M')
        self.db.setmeta('last_update',stamp)
        self.db.setmeta('last_source',source)
        self.refresh()
        self.scanstatus.setText(f'{source_label(source)} güncellendi: {len(rows)} ilan.')
        if self.settings.get('sound'):
            QApplication.beep()

def main():
    app=QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(asset('app_icon.png'))))
    w=Main()
    w.show()
    sys.exit(app.exec())

if __name__=='__main__':
    main()
