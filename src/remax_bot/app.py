from __future__ import annotations
import os,sys,re,json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit

from PySide6.QtCore import Qt,QUrl,QTimer,QObject,Signal,QPointF
from PySide6.QtGui import QPixmap,QIcon,QPainter,QPolygonF,QFont
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage

from .core import DB,Listing,search,source_key,source_label
from .playwright_scanner import PlaywrightScanner
from .importer import read_list_file, command_response, command_help
from .whatsapp_bot import WhatsAppBot

BLUE='#003DA5';RED='#E31837';BG='#F6F8FB';BORDER='#D8E0EA';TEXT='#172033'
SOURCES={
    'RE/MAX ÇARŞI':'https://remax.com.tr/tr/ofis/detay/carsi?tab=portfoylerimiz',
    'RE/MAX ÇARŞI 2':'https://remax.com.tr/tr/ofis/detay/carsi-2?tab=portfoylerimiz'
}

def app_data():
    h=Path.home()
    return (Path(os.getenv('LOCALAPPDATA',h))/'RemaxIlanBotu') if os.name=='nt' else (h/'Library'/'Application Support'/'RemaxIlanBotu')

def asset(name):
    return Path(__file__).resolve().parent/'assets'/name

def list_view_url(url):
    p=urlsplit(url)
    q=dict(parse_qsl(p.query,keep_blank_values=True))
    q['display']='list'
    return urlunsplit((p.scheme,p.netloc,p.path or '/',urlencode(q),''))

class SeymenRibbon(QWidget):
    # Sarı, iki ucu makine kesimi gibi tırtıklı SEYMEN bandı.
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(205,62)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing,True)
        w=float(self.width()); h=float(self.height())
        teeth=7
        step=h/teeth
        pts=[QPointF(16,0),QPointF(w-16,0)]
        for i in range(teeth):
            y=i*step
            pts.append(QPointF(w-2 if i%2==0 else w-18,y+step/2))
            pts.append(QPointF(w-16,y+step))
        pts += [QPointF(16,h)]
        for i in reversed(range(teeth)):
            y=i*step
            pts.append(QPointF(2 if i%2==0 else 18,y+step/2))
            pts.append(QPointF(16,y))
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.yellow)
        p.drawPolygon(QPolygonF(pts))
        p.setPen(Qt.black)
        font=QFont('Arial',24,QFont.Black)
        font.setItalic(True)
        p.setFont(font)
        p.drawText(self.rect(),Qt.AlignCenter,'SEYMEN')

COLLECT_JS=r'''(() => {
 const body=document.body?.innerText||''; const html=document.documentElement?.innerHTML||''; const found=new Set();
 const add=(raw)=>{ if(!raw)return; raw=String(raw).trim(); if(!raw||raw.startsWith('javascript:'))return; try{raw=new URL(raw,location.href).href}catch(e){}; if(!/sahibinden\.com/i.test(raw))return; if(/\/ilan\//i.test(raw)||/classifiedId=\d+/i.test(raw))found.add(raw.split('#')[0]); };
 document.querySelectorAll('a[href]').forEach(a=>add(a.getAttribute('href')));
 document.querySelectorAll('*').forEach(el=>{ for(const attr of Array.from(el.attributes||[])){ const n=(attr.name||'').toLowerCase(),v=attr.value||''; if(n.startsWith('data-')||n==='onclick'||n==='href'){ (v.match(/https?:\/\/[^\"' <>)]+|\/ilan\/[^\"' <>)]+/gi)||[]).forEach(add); } } });
 (html.match(/https?:\/\/[^\"' <>)]+\/ilan\/[^\"' <>)]+/gi)||[]).forEach(add); (html.match(/\/ilan\/[^\"' <>)]+/gi)||[]).forEach(add);
 let next=''; for(const a of document.querySelectorAll('a[href]')){ const tx=(a.innerText||'').trim().toLocaleLowerCase('tr-TR'),ar=(a.getAttribute('aria-label')||'').toLocaleLowerCase('tr-TR'),ti=(a.getAttribute('title')||'').toLocaleLowerCase('tr-TR'); if(tx==='sonraki'||tx==='sonraki sayfa'||ar.includes('sonraki')||ti.includes('sonraki')||a.getAttribute('rel')==='next'){next=a.href;break;} }
 let total=0; const ms=[body.match(/seçimlerinize uygun\s+([\d.]+)\s+ilan listeleniyor/i),body.match(/portföyümüz[\s\S]{0,100}?([\d.]+)\s+ilan/i),body.match(/([\d.]+)\s+ilan\s+listeleniyor/i)].filter(Boolean); if(ms.length)total=parseInt(ms[0][1].replace(/\./g,''),10)||0;
 const blocked=/robot değilim|captcha|doğrulama|güvenlik kontrolü/i.test(body)&&found.size===0; return {links:Array.from(found),next,total,blocked,url:location.href};
})()'''

DETAIL_JS=r'''(() => {
 const text=document.body?.innerText||''; const q=(sels)=>{for(const s of sels){const e=document.querySelector(s);if(e&&e.innerText?.trim())return e.innerText.trim()}return ''};
 const title=q(['h1','.classifiedDetailTitle h1','[data-testid="classified-title"]']); const price=q(['.classifiedInfo h3','.classifiedInfo .price','[data-testid="classified-price"]']);
 let advisor=q(['.userInfoStoreName','.classifiedUserInfo .username-info-area','.user-info-store-name']); if(!advisor){const m=text.match(/(?:Danışman|İlan Sahibi|İlan sahibi)\s*[:\n]\s*([^\n]+)/i);if(m)advisor=m[1].trim()}
 let phone=''; const tel=document.querySelector('a[href^="tel:"]'); if(tel)phone=(tel.getAttribute('href')||'').replace(/^tel:/,'').trim(); if(!phone){const pm=text.match(/(?:\+90\s*)?(?:0?\s*)?(5\d{2})[\s\-().]*(\d{3})[\s\-()]*(\d{2})[\s\-()]*(\d{2})/);if(pm)phone='0'+pm[1]+' '+pm[2]+' '+pm[3]+' '+pm[4];}
 let phoneButton=false; if(!phone){const btn=Array.from(document.querySelectorAll('button,a,[role="button"]')).find(e=>/telefonu göster|telefon göster/i.test((e.innerText||'').trim())); if(btn){btn.click();phoneButton=true;}}
 const blocked=/robot değilim|captcha|doğrulama|güvenlik kontrolü/i.test(text)&&!/İlan No/i.test(text); return {text,title,price,advisor,phone,phoneButton,url:location.href,blocked};
})()'''

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RE/MAX ÇARŞI İlan Botu')
        self.setWindowIcon(QIcon(str(asset('app_icon.png'))))
        self.resize(1520,920)
        self.setMinimumSize(1160,720)
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
        self.wa_profile.setHttpUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36')

        self._build(); self._style(); self.refresh()

    def _load_settings(self):
        base={'group':'','sound':True,'bot':False,'days':7}
        try:
            if self.cfg.exists(): base.update(json.loads(self.cfg.read_text(encoding='utf-8')))
        except: pass
        return base

    def _save_settings(self):
        self.cfg.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')

    def _style(self):
        self.setStyleSheet(f'''QWidget{{background:{BG};color:{TEXT};font-family:Arial;font-size:13px}}
QFrame#side{{background:{BLUE}}}
QPushButton#nav{{color:white;background:transparent;border:none;text-align:left;padding:12px;border-radius:7px;font-weight:700}}
QPushButton#nav:hover{{background:rgba(255,255,255,.12)}}
QPushButton#red{{background:{RED};color:white;border:none;border-radius:7px;padding:9px 15px;font-weight:800}}
QPushButton#blue{{background:{BLUE};color:white;border:none;border-radius:7px;padding:9px 15px;font-weight:800}}
QPushButton#ghost{{background:white;border:1px solid {BORDER};border-radius:7px;padding:9px 13px;font-weight:700}}
QLineEdit,QSpinBox,QComboBox{{background:white;border:1px solid {BORDER};border-radius:7px;padding:8px}}
QTableWidget{{background:white;border:1px solid {BORDER};border-radius:8px;gridline-color:{BORDER}}}
QHeaderView::section{{background:white;padding:8px;border:none;border-bottom:1px solid {BORDER};font-weight:800}}
QTabBar::tab{{background:{BG};padding:10px 18px;border:1px solid {BORDER}}}
QTabBar::tab:selected{{background:white;border-top:3px solid {BLUE}}}''')

    def _build(self):
        root=QWidget(); self.setCentralWidget(root)
        o=QHBoxLayout(root); o.setContentsMargins(0,0,0,0); o.setSpacing(0)

        s=QFrame(); s.setObjectName('side'); s.setFixedWidth(245)
        sl=QVBoxLayout(s); sl.setContentsMargins(15,18,15,18)

        img=QLabel(); img.setAlignment(Qt.AlignCenter)
        px=QPixmap(str(asset('remax_carsi.jpg')))
        img.setPixmap(px.scaled(175,155,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        sl.addWidget(img)

        self.stack=QStackedWidget()
        for i,t in enumerate(['Ana Sayfa','İlanlar','Veri Ekle','Web Sekmeleri','Ayarlar']):
            b=QPushButton(t); b.setObjectName('nav')
            b.clicked.connect(lambda _,n=i:self.stack.setCurrentIndex(n))
            sl.addWidget(b)

        sl.addStretch()
        self.seymen_ribbon=SeymenRibbon()
        sl.addWidget(self.seymen_ribbon,0,Qt.AlignHCenter)
        v=QLabel('v29.0.0\nRE/MAX ÇARŞI')
        v.setAlignment(Qt.AlignCenter); v.setStyleSheet('color:white')
        sl.addWidget(v)

        o.addWidget(s); o.addWidget(self.stack,1)
        self._home(); self._list(); self._data(); self._web(); self._settings()

    def _page(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.setContentsMargins(22,20,22,20); l.setSpacing(14)
        return w,l

    def _home(self):
        p,l=self._page()
        t=QLabel('Kontrol Paneli'); t.setStyleSheet('font-size:25px;font-weight:900')
        l.addWidget(t)
        cards=QHBoxLayout(); self.cards=[]
        for name in ['Bot Durumu','WhatsApp Durumu','İlan Havuzu','Son Güncelleme']:
            f=QFrame(); f.setStyleSheet('background:white;border:1px solid #D8E0EA;border-radius:10px')
            q=QVBoxLayout(f); q.addWidget(QLabel(name))
            val=QLabel('-'); val.setStyleSheet('font-size:21px;font-weight:900')
            q.addWidget(val); cards.addWidget(f); self.cards.append(val)
        l.addLayout(cards)
        pic=QLabel(); pic.setAlignment(Qt.AlignCenter)
        px=QPixmap(str(asset('remax_carsi.jpg')))
        pic.setPixmap(px.scaled(520,410,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        l.addWidget(pic,1)
        self.stack.addWidget(p)

    def _list(self):
        p,l=self._page()
        r=QHBoxLayout(); title=QLabel('İlan Havuzu'); title.setStyleSheet('font-size:23px;font-weight:900')
        r.addWidget(title); r.addStretch()
        self.searchbox=QLineEdit(); self.searchbox.setPlaceholderText('yahya kaptan 3+1 kiralık')
        self.searchbox.returnPressed.connect(self.do_search); r.addWidget(self.searchbox)
        b=QPushButton('Ara'); b.setObjectName('blue'); b.clicked.connect(self.do_search); r.addWidget(b)
        l.addLayout(r)
        self.table=QTableWidget(0,11)
        self.table.setHorizontalHeaderLabels(['Kaynak','Danışman / İlan Sahibi','Telefon','Başlık','Fiyat','Bölge','Oda','m²','Tür','İlan Tarihi','İlan Linki'])
        [self.table.horizontalHeader().setSectionResizeMode(c,QHeaderView.Stretch) for c in [1,3,5,10]]
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(self.open_link)
        l.addWidget(self.table); self.stack.addWidget(p)

    def _data(self):
        p,l=self._page()
        title=QLabel('İlan Veritabanı / Liste Ekle'); title.setStyleSheet('font-size:23px;font-weight:900'); l.addWidget(title)
        info=QLabel('RE/MAX güncelleme, Excel/CSV içe aktarma ve manuel ilan ekleme aynı ortak ilan havuzunu kullanır.')
        info.setWordWrap(True); l.addWidget(info)
        row=QHBoxLayout()
        imp=QPushButton('EXCEL / CSV YÜKLE'); imp.setObjectName('blue'); imp.clicked.connect(self.import_file); row.addWidget(imp)
        helpb=QPushButton('BOT KOMUTLARI (#?)'); helpb.setObjectName('ghost'); helpb.clicked.connect(lambda:QMessageBox.information(self,'Bot Komutları',command_help())); row.addWidget(helpb)
        row.addStretch(); l.addLayout(row)

        box=QGroupBox('Manuel İlan Ekle'); form=QFormLayout(box)
        self.m_title=QLineEdit(); self.m_adv=QLineEdit(); self.m_phone=QLineEdit(); self.m_price=QLineEdit()
        self.m_loc=QLineEdit(); self.m_rooms=QLineEdit(); self.m_type=QLineEdit(); self.m_url=QLineEdit()
        for label,w in [('Başlık',self.m_title),('Danışman',self.m_adv),('Telefon',self.m_phone),('Fiyat',self.m_price),('Bölge',self.m_loc),('Oda',self.m_rooms),('Tür',self.m_type),('İlan Linki',self.m_url)]:
            form.addRow(label,w)
        add=QPushButton('MANUEL İLANI KAYDET'); add.setObjectName('red'); add.clicked.connect(self.manual_add); form.addRow('',add)
        l.addWidget(box); l.addStretch(); self.stack.addWidget(p)

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'İlan Listesi Seç','','Excel (*.xlsx);;CSV (*.csv)')
        if not path:return
        try:
            items=read_list_file(path); self.db.upsert(items)
            self.db.setmeta('last_update',datetime.now().strftime('%d.%m.%Y %H:%M'))
            self.refresh()
            QMessageBox.information(self,'İçe Aktarma',f'{len(items)} ilan listeye eklendi/güncellendi.')
        except Exception as e:
            QMessageBox.warning(self,'İçe Aktarma',str(e))

    def manual_add(self):
        title=self.m_title.text().strip(); url=self.m_url.text().strip()
        if not title and not url:
            QMessageBox.warning(self,'Manuel İlan','Başlık veya ilan linki girin.'); return
        lid=(re.search(r'(?:P)?(\d{5,})',url).group(1) if re.search(r'(?:P)?(\d{5,})',url) else str(int(datetime.now().timestamp()*1000)))
        x=Listing(lid,title or f'İlan {lid}',url,self.m_adv.text().strip(),self.m_phone.text().strip(),self.m_price.text().strip(),self.m_loc.text().strip(),self.m_rooms.text().strip(),'',self.m_type.text().strip(),'','', 'manual://entry')
        self.db.add_one(x); self.refresh(); QMessageBox.information(self,'Manuel İlan','İlan kaydedildi.')

    def _web(self):
        p,l=self._page()
        h=QHBoxLayout(); h.addWidget(QLabel('Web Sekmeleri')); h.addStretch()
        self.scanstatus=QLabel('Beklemede'); self.scanprog=QLabel('0 / 0')
        h.addWidget(self.scanstatus); h.addWidget(self.scanprog); l.addLayout(h)

        self.tabs=QTabWidget()

        self.wa=QWebEngineView()
        self.wa.setPage(QWebEnginePage(self.wa_profile,self.wa))
        self.wa.setUrl(QUrl('https://web.whatsapp.com/'))
        self.tabs.addTab(self.wa,'WhatsApp Web')
        self.wa_status_text='Web sekmesi hazır'
        self.wabot=WhatsAppBot(self.wa,lambda text:command_response(self.db.all(),text))
        self.wabot.status.connect(self._wa_status)

        w=QWidget(); wl=QVBoxLayout(w); tb=QHBoxLayout()
        back=QPushButton('←'); fwd=QPushButton('→'); reload=QPushButton('Yenile')
        self.source_combo=QComboBox(); self.source_combo.addItems(list(SOURCES.keys()))
        open_source=QPushButton('KAYNAĞI AÇ'); open_source.setObjectName('ghost')
        self.addr=QLineEdit(); go=QPushButton('Git'); go.setObjectName('red')
        scan=QPushButton('TARA'); scan.setObjectName('blue')
        resume=QPushButton('DEVAM ET'); resume.setObjectName('ghost')
        stop=QPushButton('DURDUR'); stop.setObjectName('red')
        for x in [back,fwd,reload,self.source_combo,open_source,self.addr,go,scan,resume,stop]:
            tb.addWidget(x,1 if x is self.addr else 0)
        wl.addLayout(tb)
        note=QLabel('TARA: gerçek Chromium motoru ile RE/MAX portföy linklerini toplar, tüm sayfaları ve ilan detaylarını okur.')
        note.setStyleSheet('color:#667085;padding:4px'); wl.addWidget(note)

        self.browser=QWebEngineView()
        self.browser.setPage(QWebEnginePage(self.profile,self.browser))
        self.browser.setUrl(QUrl(SOURCES['RE/MAX ÇARŞI']))
        wl.addWidget(self.browser,1)
        self.tabs.addTab(w,'İlan Tarayıcı')
        l.addWidget(self.tabs,1); self.stack.addWidget(p)

        back.clicked.connect(self.browser.back); fwd.clicked.connect(self.browser.forward); reload.clicked.connect(self.browser.reload)
        self.browser.urlChanged.connect(lambda u:self.addr.setText(u.toString()))
        go.clicked.connect(self.nav); self.addr.returnPressed.connect(self.nav); open_source.clicked.connect(self.open_source)

        self.sc=PlaywrightScanner(app_data()/"browser-profile")
        self.sc.progress.connect(self.scanprog.setText); self.sc.status.connect(self.scanstatus.setText)
        self.sc.failed.connect(self.scan_failed); self.sc.done.connect(self.scan_done)
        self.sc.busy_changed.connect(lambda b:self.source_combo.setEnabled(not b))
        self.sc.verification_needed.connect(self.scan_verification)
        scan.clicked.connect(lambda:self.sc.start(SOURCES[self.source_combo.currentText()]))
        resume.clicked.connect(self.sc.resume); stop.clicked.connect(self.sc.stop)
        self.source_combo.currentTextChanged.connect(lambda name:self.addr.setText(SOURCES[name]) if self.sc.phase=='idle' else None)

    def _settings(self):
        p,l=self._page()
        t=QLabel('Bot Ayarları'); t.setStyleSheet('font-size:23px;font-weight:900'); l.addWidget(t)
        f=QFormLayout()
        self.group=QLineEdit(self.settings['group'])
        self.sound=QCheckBox('Bildirim sesi açık'); self.sound.setChecked(self.settings['sound'])
        self.days=QSpinBox(); self.days.setRange(1,60); self.days.setValue(self.settings['days']); self.days.setSuffix(' gün')
        f.addRow('WhatsApp grup adı:',self.group); f.addRow('Bildirim:',self.sound); f.addRow('Güncelleme hatırlatması:',self.days)
        l.addLayout(f)

        r=QHBoxLayout()
        for txt,obj,fn in [('Ayarları Kaydet','blue',self.save_settings),('Botu Başlat','ghost',self.bot_start),('Botu Durdur','red',self.bot_stop),('Programı Kapat','ghost',QApplication.quit)]:
            b=QPushButton(txt); b.setObjectName(obj); b.clicked.connect(fn); r.addWidget(b)
        r.addStretch(); l.addLayout(r)

        test=QGroupBox('Bot Komut Testi'); tf=QVBoxLayout(test)
        self.cmdtest=QLineEdit()
        self.cmdtest.setPlaceholderText('#bot başlat# / #? / #danışmanlar# / #izmit kiralık 55 bin#')
        self.cmdout=QPlainTextEdit(); self.cmdout.setReadOnly(True)
        cb=QPushButton('KOMUTU TEST ET'); cb.setObjectName('blue'); cb.clicked.connect(self.test_command)
        tf.addWidget(self.cmdtest); tf.addWidget(cb); tf.addWidget(self.cmdout)
        l.addWidget(test)

        commands=QGroupBox('Komut Listesi'); cf=QVBoxLayout(commands)
        self.commandlist=QPlainTextEdit(); self.commandlist.setReadOnly(True)
        self.commandlist.setPlainText(command_help())
        self.commandlist.setMinimumHeight(240)
        cf.addWidget(self.commandlist)
        l.addWidget(commands)

        l.addStretch(); self.stack.addWidget(p)

    def _wa_status(self,msg):
        self.wa_status_text=msg
        if hasattr(self,'cards'): self.cards[1].setText(msg)

    def test_command(self):
        out=command_response(self.db.all(),self.cmdtest.text().strip())
        self.cmdout.setPlainText(out or "Bot bu mesajı görmezden gelir.")

    def open_source(self):
        self.browser.setUrl(QUrl(SOURCES[self.source_combo.currentText()]))
        self.tabs.setCurrentIndex(1)

    def nav(self):
        x=self.addr.text().strip()
        x=('https://'+x) if x and not x.startswith(('http://','https://')) else x
        if x:self.browser.setUrl(QUrl(x))

    def bot_start(self):
        self.settings.update(bot=True,group=self.group.text().strip())
        self._save_settings()
        self.tabs.setCurrentIndex(0)
        self.wabot.start(self.settings['group'])
        self.refresh()

    def bot_stop(self):
        self.settings['bot']=False; self._save_settings(); self.wabot.stop(); self.refresh()

    def save_settings(self):
        self.settings.update(group=self.group.text().strip(),sound=self.sound.isChecked(),days=self.days.value())
        self._save_settings()
        if self.settings.get('bot'): self.wabot.start(self.settings['group'])
        self.refresh()

    def refresh(self,rows=None):
        self.cards[0].setText('Açık' if self.settings['bot'] else 'Durduruldu')
        self.cards[1].setText(getattr(self,'wa_status_text','Web sekmesi hazır'))
        self.cards[2].setText(str(self.db.count()))
        self.cards[3].setText(self.db.meta('last_update'))
        self.fill(self.db.all() if rows is None else rows)

    def fill(self,rows):
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            vals=[source_label(x.source_url),x.advisor,x.phone,x.title,x.price,x.location,x.rooms,x.sqm,' / '.join(v for v in [x.transaction_type,x.property_type] if v),x.listing_date,x.url]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))

    def do_search(self):
        self.fill(search(self.db.all(),self.searchbox.text().strip()))

    def open_link(self,row,col):
        x=self.table.item(row,10)
        if x:
            self.stack.setCurrentIndex(3)
            self.tabs.setCurrentIndex(1)
            self.browser.setUrl(QUrl(x.text()))

    def scan_verification(self,msg):
        self.scanstatus.setText(msg); QMessageBox.information(self,'Kullanıcı İşlemi Gerekiyor',msg)

    def scan_failed(self,msg):
        self.scanstatus.setText(msg); QMessageBox.warning(self,'Tarama',msg)

    def scan_done(self,source,rows):
        if not rows:return
        self.db.replace_source(source,rows)
        stamp=datetime.now().strftime('%d.%m.%Y %H:%M')
        self.db.setmeta('last_update',stamp); self.db.setmeta('last_source',source)
        self.refresh()
        self.scanstatus.setText(f'{source_label(source)} güncellendi: {len(rows)} ilan. Diğer kaynaklar korundu.')
        QApplication.beep() if self.settings['sound'] else None

def main():
    app=QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(asset('app_icon.png'))))
    w=Main(); w.show(); sys.exit(app.exec())

if __name__=='__main__':
    main()
