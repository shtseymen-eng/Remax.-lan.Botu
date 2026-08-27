from __future__ import annotations
import re
from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from .core import Listing, source_key

DEEP_HELPERS = r'''
function deepRoots(){
  const out=[];
  const walk=(root)=>{
    if(!root || out.includes(root)) return;
    out.push(root);
    let els=[];
    try{ els=Array.from(root.querySelectorAll('*')); }catch(e){}
    for(const el of els){
      try{ if(el.shadowRoot) walk(el.shadowRoot); }catch(e){}
    }
  };
  walk(document);
  return out;
}
function deepAll(sel){
  const out=[];
  for(const root of deepRoots()){
    try{ out.push(...Array.from(root.querySelectorAll(sel))); }catch(e){}
  }
  return out;
}
function deepText(){
  const parts=[];
  for(const root of deepRoots()){
    try{
      if(root===document && document.body?.innerText) parts.push(document.body.innerText);
      else if(root.host){
        const t=root.host.innerText || root.textContent || '';
        if(t) parts.push(t);
      }
    }catch(e){}
  }
  return parts.join('\n');
}
'''

LIST_JS = r'''(() => {
''' + DEEP_HELPERS + r'''
  const cards=[];
  const seen=new Set();
  const candidates=deepAll('a[href], [role="link"], [onclick]');

  function abs(raw){
    if(!raw) return '';
    try{return new URL(raw,location.href).href.split('#')[0]}catch(e){return ''}
  }
  function cardCode(text,href){
    const m=(String(text||'')+' '+String(href||'')).match(/\bP\d{6,}\b/i);
    return m?m[0].toUpperCase():'';
  }
  function looksLikeCard(el){
    const tx=String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
    const href=abs(el.getAttribute?.('href')||'');
    const portfolioHref=/\/portfoy\/P\d{6,}/i.test(href);
    const portfolioText=/\bP\d{6,}\b/i.test(tx);
    const propertyText=/(?:₺|TL|Satılık|Kiralık|m²|m2)/i.test(tx);
    return portfolioHref || (portfolioText && propertyText);
  }

  for(const el of candidates){
    if(!looksLikeCard(el)) continue;
    const href=abs(el.getAttribute?.('href')||'');
    const tx=String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
    const code=cardCode(tx,href);
    const key=code || href || tx.slice(0,120);
    if(!key || seen.has(key)) continue;
    seen.add(key);
    el.setAttribute('data-remax-card-index',String(cards.length));
    cards.push({index:cards.length, href, code, text:tx.slice(0,500)});
  }

  // Bazı kartlarda tıklanabilir parent ayrı, portföy kodu child içindedir.
  if(!cards.length){
    for(const el of deepAll('*')){
      const tx=String(el.innerText||el.textContent||'').replace(/\s+/g,' ').trim();
      if(!/\bP\d{6,}\b/i.test(tx) || !/(?:₺|TL|Satılık|Kiralık|m²|m2)/i.test(tx)) continue;
      let cur=el, clicker=null;
      for(let i=0;i<6 && cur;i++,cur=cur.parentElement){
        if(cur.matches?.('a[href],[role="link"],[onclick]')){clicker=cur;break;}
      }
      if(!clicker) continue;
      const href=abs(clicker.getAttribute?.('href')||'');
      const code=cardCode(tx,href);
      const key=code || href || tx.slice(0,120);
      if(!key || seen.has(key)) continue;
      seen.add(key);
      clicker.setAttribute('data-remax-card-index',String(cards.length));
      cards.push({index:cards.length,href,code,text:tx.slice(0,500)});
    }
  }

  const pages=[];
  let currentPage=1;
  for(const el of deepAll('a,button,[role="button"],[role="link"]')){
    const t=String(el.innerText||el.textContent||'').trim();
    if(/^\d{1,3}$/.test(t)){
      const n=parseInt(t,10);
      if(n>=1 && n<=100){
        pages.push(n);
        if(el.getAttribute?.('aria-current')==='page' || /active|selected|current/i.test(String(el.className||''))) currentPage=n;
      }
    }
  }

  const text=deepText();
  let total=0;
  const pats=[/(\d+)\s*sonuç bulundu/i,/portföyünde\s*(\d+)\s*Gayrimenkul/i,/(\d+)\s*portföy/i];
  for(const p of pats){const m=text.match(p);if(m){total=parseInt(m[1],10)||0;break;}}

  return {
    cards,
    pages:Array.from(new Set(pages)).sort((a,b)=>a-b),
    currentPage,total,
    rootCount:deepRoots().length,
    candidateCount:candidates.length,
    textLength:text.length,
    url:location.href
  };
})()'''

CLICK_CARD_JS = r'''((idx) => {
''' + DEEP_HELPERS + r'''
  const el=deepAll('[data-remax-card-index="'+idx+'"]')[0];
  if(!el) return {ok:false,reason:'card_not_found'};
  try{
    el.scrollIntoView({block:'center'});
    el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
    el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}));
    el.click();
    return {ok:true,text:String(el.innerText||el.textContent||'').slice(0,300),href:el.getAttribute?.('href')||''};
  }catch(e){return {ok:false,reason:String(e)}}
})'''

CLICK_PAGE_JS = r'''((pageNo) => {
''' + DEEP_HELPERS + r'''
  const els=deepAll('a,button,[role="button"],[role="link"]');
  const el=els.find(x => String(x.innerText||x.textContent||'').trim()===String(pageNo));
  if(!el) return {ok:false,reason:'page_not_found'};
  try{el.scrollIntoView({block:'center'});el.click();return {ok:true}}catch(e){return {ok:false,reason:String(e)}}
})'''

DETAIL_JS = r'''(() => {
''' + DEEP_HELPERS + r'''
  const text=deepText();
  const clean=s=>String(s||'').replace(/\s+/g,' ').trim();
  const lines=text.split('\n').map(x=>x.trim()).filter(Boolean);
  function afterLabel(label){
    const n=label.toLocaleLowerCase('tr-TR');
    for(let i=0;i<lines.length-1;i++) if(lines[i].toLocaleLowerCase('tr-TR')===n) return lines[i+1];
    return '';
  }
  function firstDeep(sel){
    for(const e of deepAll(sel)){const t=clean(e.innerText||e.textContent||'');if(t)return t}
    return '';
  }

  let title=firstDeep('h1');
  if(!title){
    const idx=lines.findIndex(x=>/Teklif Ver/i.test(x));
    if(idx>0) title=lines[Math.max(0,idx-2)]||'';
  }
  let price='';
  const pm=text.match(/(?:^|\n)\s*([\d.]+)\s*(?:₺|TL)/m);if(pm)price=pm[1]+' ₺';
  const listingId=afterLabel('Portföy No') || ((text.match(/\bP\d{6,}\b/)||[])[0]||'');
  const emlak=afterLabel('Emlak Tipi');
  const date=afterLabel('Yayınlanma Tarihi');
  const gross=afterLabel('m2 (Brüt)')||afterLabel('m² (Brüt)')||afterLabel('m²')||afterLabel('m2');
  const rooms=afterLabel('Oda Sayısı');

  let locationText='';
  const li=lines.findIndex(x=>/^Portföy No$/i.test(x));
  if(li>0){
    const before=lines.slice(Math.max(0,li-8),li);
    const locs=before.filter(x=>/\//.test(x)||/Mah\.|Köy|İzmit|Kocaeli|Kartepe|Başiskele|Derince|Körfez|Gölcük|Kandıra/i.test(x));
    if(locs.length) locationText=clean(locs[locs.length-1]);
  }

  let phone='';
  for(const el of deepAll('a,button,[role="button"]')){
    const t=clean(el.innerText||el.textContent||'');
    if(/(?:\+90\s*)?5\d{2}[\s\d]{7,}/.test(t)){phone=t;break;}
  }
  if(!phone){const m=text.match(/(?:\+90\s*)?5\d{2}[\s\d]{7,}/);if(m)phone=clean(m[0]);}

  let advisor='';
  const advisorLabels=['Gayrimenkul Danışmanı','Danışman'];
  for(const lab of advisorLabels){const v=afterLabel(lab);if(v){advisor=v;break;}}
  if(!advisor && phone){
    const pi=lines.findIndex(x=>x.includes(phone));
    if(pi>0){
      for(let i=pi-1;i>=Math.max(0,pi-6);i--){
        const x=lines[i];
        if(x.length>=5&&x.length<=80&&!/\d/.test(x)&&!/RE\/MAX|iletişim|portföy|sertifika/i.test(x)){advisor=x;break;}
      }
    }
  }

  let transaction='',propertyType='';
  if(emlak.includes('/')){const p=emlak.split('/').map(clean);propertyType=p[0]||'';transaction=p[1]||'';}
  else{
    propertyType=emlak;
    const probe=title+' '+text.slice(0,4000);
    if(/Kiralık/i.test(probe))transaction='Kiralık';else if(/Satılık/i.test(probe))transaction='Satılık';
  }

  return {url:location.href,listingId:clean(listingId),title:clean(title),price,location:locationText,rooms,
          transaction,propertyType,sqm:gross?clean(gross)+' m²':'',listingDate:clean(date),advisor:clean(advisor),phone:clean(phone),
          textLength:text.length,rootCount:deepRoots().length};
})()'''

class EmbeddedRemaxScanner(QObject):
    progress=Signal(str); status=Signal(str); done=Signal(str,list); failed=Signal(str); busy_changed=Signal(bool)

    def __init__(self,view):
        super().__init__(); self.view=view; self.phase='idle'; self.source=''; self.base_url=''; self.rows=[]; self.expected=0
        self.page_no=1; self.card_index=0; self.card_count=0; self.pages=[]; self.seen=set(); self.returning=False
        self.view.loadFinished.connect(self._loaded)

    def start(self,url):
        if self.phase!='idle': return
        self.source=source_key(url); self.base_url=url; self.rows=[]; self.expected=0; self.page_no=1; self.card_index=0; self.card_count=0; self.pages=[]; self.seen=set(); self.returning=False
        self.phase='list'; self.busy_changed.emit(True); self.status.emit('1. sayfadaki portföy kartları hazırlanıyor...'); self.view.setUrl(QUrl(url))

    def stop(self):
        self.phase='idle'; self.busy_changed.emit(False); self.status.emit('Tarama durduruldu.')

    def resume(self):
        if self.phase=='list': QTimer.singleShot(500,self._inspect_list)
        elif self.phase=='detail': QTimer.singleShot(500,self._inspect_detail)

    def _loaded(self,ok):
        if self.phase=='idle': return
        if not ok: self._fail('RE/MAX sayfası yüklenemedi.'); return
        if self.phase=='list': QTimer.singleShot(1300,self._inspect_list)
        elif self.phase=='detail': QTimer.singleShot(900,self._inspect_detail)

    def _inspect_list(self):
        if self.phase!='list': return
        self.view.page().runJavaScript(LIST_JS,self._list_result)

    def _list_result(self,d):
        d=d or {}; cards=d.get('cards') or []; self.pages=d.get('pages') or self.pages
        self.expected=max(self.expected,int(d.get('total') or 0)); self.card_count=len(cards)
        if not cards:
            self._fail(f'Portföy kartı bulunamadı. Shadow kök: {d.get("rootCount",0)}, aday öğe: {d.get("candidateCount",0)}, metin: {d.get("textLength",0)} karakter.'); return
        self.status.emit(f'Sayfa {self.page_no}: {self.card_count} portföy kartı bulundu. {self.card_index+1}. karta geçiliyor...')
        if self.card_index>=self.card_count:
            self._next_page(); return
        js=CLICK_CARD_JS + f'({self.card_index})'
        self.view.page().runJavaScript(js,self._card_clicked)

    def _card_clicked(self,res):
        res=res or {}
        if not res.get('ok'):
            self.card_index+=1; QTimer.singleShot(300,self._inspect_list); return
        self.status.emit(f'Sayfa {self.page_no} - Portföy {self.card_index+1}/{self.card_count} açılıyor...')
        QTimer.singleShot(1200,self._after_card_click)

    def _after_card_click(self):
        url=self.view.url().toString()
        if re.search(r'/portfoy/P\d{6,}',url,re.I):
            self.phase='detail'; self._inspect_detail(); return
        # SPA route biraz gecikebilir.
        QTimer.singleShot(900,self._after_card_click_second)

    def _after_card_click_second(self):
        url=self.view.url().toString()
        if re.search(r'/portfoy/P\d{6,}',url,re.I):
            self.phase='detail'; self._inspect_detail(); return
        self.card_index+=1; self.status.emit('Kart tıklandı ancak detay açılmadı; sıradaki karta geçiliyor.'); self._inspect_list()

    def _inspect_detail(self):
        if self.phase!='detail': return
        self.view.page().runJavaScript(DETAIL_JS,self._detail_result)

    def _detail_result(self,d):
        d=d or {}; url=d.get('url') or self.view.url().toString(); lid=(d.get('listingId') or '').strip()
        if not lid:
            m=re.search(r'P\d{6,}',url,re.I); lid=m.group(0).upper() if m else ''
        if lid and lid not in self.seen:
            self.seen.add(lid)
            self.rows.append(Listing(lid,d.get('title') or f'Portföy {lid}',url,d.get('advisor') or '',d.get('phone') or '',d.get('price') or '',d.get('location') or '',d.get('rooms') or '',d.get('transaction') or '',d.get('propertyType') or '',d.get('sqm') or '',d.get('listingDate') or '',self.source))
        self.progress.emit(f'{len(self.rows)} / {self.expected or "?"}')
        self.card_index+=1; self.phase='list'; self.returning=True
        self.status.emit(f'{len(self.rows)} ilan alındı. Listeye geri dönülüyor...')
        self.view.back()
        QTimer.singleShot(1700,self._after_back)

    def _after_back(self):
        if self.phase!='list': return
        self.returning=False; self._inspect_list()

    def _next_page(self):
        targets=[p for p in self.pages if p>self.page_no]
        if not targets or (self.expected and len(self.rows)>=self.expected): self._finish(); return
        target=min(targets); self.status.emit(f'Sayfa {self.page_no} tamamlandı. Sayfa {target} açılıyor...')
        js=CLICK_PAGE_JS + f'({target})'
        self.view.page().runJavaScript(js,lambda r,t=target:self._page_clicked(r,t))

    def _page_clicked(self,res,target):
        res=res or {}
        if not res.get('ok'):
            self._finish(); return
        self.page_no=target; self.card_index=0; self.card_count=0
        QTimer.singleShot(1600,self._inspect_list)

    def _finish(self):
        if not self.rows: self._fail('Hiç portföy detayı alınamadı.'); return
        self.phase='idle'; self.busy_changed.emit(False); self.status.emit(f'Güncelleme tamamlandı: {len(self.rows)} ilan.'); self.done.emit(self.source,self.rows)

    def _fail(self,msg):
        self.phase='idle'; self.busy_changed.emit(False); self.failed.emit(msg)
