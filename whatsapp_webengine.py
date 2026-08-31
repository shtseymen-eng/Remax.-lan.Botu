from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    from PySide6.QtCore import QObject, QTimer, Signal
except ImportError:
    class QObject:
        def __init__(self,*_args,**_kwargs): pass
    class _DummySignal:
        def __init__(self): self._callbacks=[]
        def connect(self,cb): self._callbacks.append(cb)
        def emit(self,*args):
            for cb in list(self._callbacks): cb(*args)
    def Signal(*_args,**_kwargs): return _DummySignal()
    class QTimer:
        def __init__(self,*_args,**_kwargs):
            self.timeout=_DummySignal(); self.running=False
        def setInterval(self,_ms): pass
        def start(self): self.running=True
        def stop(self): self.running=False
        @staticmethod
        def singleShot(_ms,cb): cb()

MAX_INTRO=(
    "Max: Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. "
    "Komut listesini görmek için #? yazabilirsiniz."
)
MAX_STOPPED=(
    "Max: İlan arama botu durduruldu. "
    "Yeniden başlatmak için #Max başla yazabilirsiniz."
)

def classify_command(text:str)->str:
    value=str(text or "").strip()
    if not value.startswith("#"): return "ignore"
    if value.endswith("#") and len(value)>1:
        value=value[:-1].rstrip()
    low=value.casefold()
    if low in {"#max başla","#max başlat"}: return "start"
    if low in {"#max dur","#max durdur"}: return "stop"
    return "query" if len(value)>=2 else "ignore"

@dataclass
class RouteResult:
    replies:list[str]=field(default_factory=list)
    status:str=""

class MessageRouter:
    def __init__(self,response_fn:Callable[[str],str]):
        self.response_fn=response_fn
        self.active=False
        self.seen=set()
        self._seen_order=deque()
        self.primed=False

    def _remember(self,message_id:str):
        if not message_id or message_id in self.seen: return
        self.seen.add(message_id)
        self._seen_order.append(message_id)
        while len(self._seen_order)>2500:
            self.seen.discard(self._seen_order.popleft())

    def process(self,snapshot:dict|None)->RouteResult:
        result=RouteResult()
        if not isinstance(snapshot,dict): return result
        title=" ".join(str((snapshot.get("chat") or {}).get("title") or "Açık sohbet").split()) or "Açık sohbet"
        messages=snapshot.get("messages") or []

        if not self.primed:
            for m in messages:
                self._remember(str((m or {}).get("id") or ""))
            self.primed=True
            result.status=f"Max dinleyici hazır - {title} içinde #Max başla yazın"
            return result

        for m in messages:
            if not isinstance(m,dict): continue
            mid=str(m.get("id") or "").strip()
            text=str(m.get("text") or "").strip()
            if not mid or mid in self.seen: continue
            self._remember(mid)

            action=classify_command(text)
            if action=="start":
                self.active=True
                result.replies.append(MAX_INTRO)
                result.status=f"Max aktif - {title} dinleniyor"
                continue
            if action=="stop":
                if self.active: result.replies.append(MAX_STOPPED)
                self.active=False
                result.status=f"Max dinleyici hazır - {title} içinde #Max başla yazın"
                continue
            if action!="query" or not self.active: continue

            answer=self.response_fn(text)
            if answer:
                answer=str(answer).strip()
                result.replies.append(answer if answer.startswith("Max:") else "Max: "+answer)
        return result

class EmbeddedWhatsAppBot(QObject):
    status=Signal(str)
    log=Signal(str)
    sent=Signal(str,str)

    # Okuma mantığı, çalışan pregate-mail-bot ile aynı temel yöntemi kullanır:
    # document genelinde msg-container taranır. #main veya sohbet başlığı zorunlu değildir.
    SNAPSHOT_JS=r"""
    (() => {
      const clean=v=>String(v || '').replace(/\s+/g,' ').trim();
      const rows=Array.from(document.querySelectorAll('[data-testid="msg-container"]'));

      const composer=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]'))
          .find(el=>el.offsetParent!==null || el.getClientRects().length>0) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]'))
          .find(el=>el.offsetParent!==null || el.getClientRects().length>0) ||
        Array.from(document.querySelectorAll('[contenteditable="true"][data-lexical-editor="true"]'))
          .find(el=>el.offsetParent!==null || el.getClientRects().length>0);

      if(!rows.length && !composer) return null;

      let title='';
      const main=document.querySelector('#main');
      const header=main?.querySelector('header');
      const titleNode=
        header?.querySelector('span[title]') ||
        header?.querySelector('[title]') ||
        header?.querySelector('span[dir="auto"]');
      title=clean(titleNode?.getAttribute?.('title') || titleNode?.innerText || titleNode?.textContent || '');

      const messages=[];
      let lastSender='';

      rows.slice(-120).forEach((el,idx)=>{
        let dataIdEl=el;
        while(dataIdEl && !dataIdEl.getAttribute('data-id')){
          dataIdEl=dataIdEl.parentElement;
        }
        const dataId=dataIdEl ? (dataIdEl.getAttribute('data-id') || '') : '';
        const outgoing=!!el.closest('[class*="message-out"]') || dataId.startsWith('true_');

        let text='';
        const selectors=[
          '[data-testid="msg-text"]',
          'span.selectable-text.copyable-text',
          'span[class*="selectable-text"]',
          'div[class*="copyable-text"] span[dir]'
        ];
        for(const sel of selectors){
          const node=el.querySelector(sel);
          if(node && node.innerText){
            text=node.innerText.trim();
            break;
          }
        }
        if(!text) text=clean(el.innerText || '');

        let sender='';
        const copyable=el.querySelector('[data-pre-plain-text]');
        const pre=copyable ? (copyable.getAttribute('data-pre-plain-text') || '') : '';
        const m=pre.match(/] (.+?):\s*$/);
        if(m) sender=m[1].trim();

        if(sender) lastSender=sender;
        else if(lastSender) sender=lastSender;

        if(!text || !text.startsWith('#')) return;

        const id=
          dataId ||
          el.getAttribute('data-id') ||
          el.getAttribute('data-key') ||
          (pre+'::'+idx+'::'+text);

        messages.push({
          id,
          text,
          sender:sender || (outgoing ? 'Siz' : 'Kullanıcı'),
          outgoing,
          pre
        });
      });

      return {
        chat:{
          id:(title || 'Açık sohbet').toLocaleLowerCase('tr-TR'),
          title:title || 'Açık sohbet'
        },
        messages,
        diagnostics:{
          msgContainers:rows.length,
          composer:!!composer,
          main:!!main
        }
      };
    })()
    """

    COMPOSE_MESSAGE_JS=r"""
    (() => {
      const message=__MESSAGE_JSON__;
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const selectors=[
        'footer div[contenteditable="true"][role="textbox"]',
        'footer div[contenteditable="true"][data-lexical-editor="true"]',
        'footer div[contenteditable="true"]'
      ];

      let box=null;
      for(const selector of selectors){
        const matches=Array.from(document.querySelectorAll(selector)).filter(visible);
        if(matches.length){ box=matches[matches.length-1]; break; }
      }
      if(!box) return false;

      box.focus();
      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand('delete',false,null);
      if(String(box.textContent || '').trim()) box.textContent='';
      box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward',data:null}));

      const fresh=document.createRange();
      fresh.selectNodeContents(box);
      fresh.collapse(false);
      selection.removeAllRanges();
      selection.addRange(fresh);

      document.execCommand('insertText',false,message);
      box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message}));
      return String(box.innerText || box.textContent || '').trim()===String(message).trim();
    })()
    """

    CLICK_SEND_JS=r"""
    (() => {
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const buttons=Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
      const send=buttons.find(button=>{
        if(button.disabled || button.getAttribute('aria-disabled')==='true') return false;
        const label=String(button.getAttribute('aria-label') || '').trim().toLocaleLowerCase('tr-TR');
        const testid=String(button.getAttribute('data-testid') || '');
        const icon=button.querySelector('[data-icon="send"],[data-testid="send"],[data-testid="compose-btn-send"]');
        return label==='gönder' || label==='send' || testid==='send' || testid==='compose-btn-send' || !!icon;
      });

      if(send){ send.click(); return true; }

      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);
      if(!box) return false;

      box.focus();
      box.dispatchEvent(new KeyboardEvent('keydown',{
        bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13
      }));
      box.dispatchEvent(new KeyboardEvent('keyup',{
        bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13
      }));
      return true;
    })()
    """

    COMPOSER_EMPTY_JS=r"""
    (() => {
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);
      if(!box) return false;
      return String(box.innerText || box.textContent || '').trim()==='';
    })()
    """

    CLEAR_COMPOSER_JS=r"""
    (() => {
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);
      if(!box) return false;
      box.focus();
      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand('delete',false,null);
      if(String(box.textContent || '').trim()) box.textContent='';
      box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward',data:null}));
      return true;
    })()
    """

    def __init__(self,response_fn:Callable[[str],str],page=None,poll_ms:int=900,
                 schedule:Optional[Callable[[int,Callable],None]]=None):
        super().__init__()
        self.router=MessageRouter(response_fn)
        self.page=page
        self.running=False
        self._read_pending=False
        self._outbox=deque()
        self._send_busy=False
        self._last_status=""
        self._schedule=schedule or (lambda ms,cb:QTimer.singleShot(ms,cb))
        self._timer=QTimer(self)
        self._timer.setInterval(max(500,int(poll_ms)))
        self._timer.timeout.connect(self.poll_once)
        self._schedule(700,self._auto_start_when_ready)

    @property
    def active(self): return self.router.active

    def attach_page(self,page):
        self.page=page
        self._auto_start_when_ready()

    def _status(self,text:str):
        if text and text!=self._last_status:
            self._last_status=text
            self.status.emit(text)

    def _auto_start_when_ready(self):
        if not self.running: self.start()

    def start(self,group:str=""):
        if not self.running:
            self.running=True
            self._timer.start()
        self._status("Max dinleyici açık - WhatsApp sohbetinde #Max başla yazın")
        self._schedule(300,self.poll_once)
        return True

    def stop(self):
        self.router.active=False
        self._status("Max pasif - tekrar başlatmak için sohbete #Max başla yazın")

    def set_group(self,group:str):
        self._status("Max açık sohbeti kullanır - #Max başla yazın")
        return True

    def shutdown(self):
        self.running=False
        self.router.active=False
        self._timer.stop()

    def poll_once(self):
        if not self.running or not self.page or self._read_pending: return
        self._read_pending=True
        try:
            self.page.runJavaScript(self.SNAPSHOT_JS,self._on_snapshot)
        except Exception as e:
            self._read_pending=False
            self.log.emit(str(e))
            self._status("WhatsApp sayfası okunamadı: "+str(e)[:120])

    def _on_snapshot(self,snapshot):
        self._read_pending=False
        if not self.running: return
        if not isinstance(snapshot,dict):
            self._status("Max dinleyici açık - WhatsApp'ta bir sohbet açın")
            return

        d=snapshot.get("diagnostics") or {}
        result=self.router.process(snapshot)
        if result.status:
            self._status(result.status+f" | mesaj:{d.get('msgContainers',0)}")
        for reply in result.replies:
            self._send(reply)

    @staticmethod
    def _inject(script:str,token:str,value:str)->str:
        return script.replace(token,json.dumps(str(value),ensure_ascii=False))

    def _send(self,text:str):
        msg=str(text or "").strip()
        if not msg or not self.page: return False
        if msg in self._outbox: return True
        self._outbox.append(msg)
        if not self._send_busy: self._begin_send()
        return True

    def _begin_send(self):
        if self._send_busy or not self._outbox or not self.page: return
        self._send_busy=True
        msg=self._outbox[0]
        script=self._inject(self.COMPOSE_MESSAGE_JS,"__MESSAGE_JSON__",msg)

        def composed(ok):
            if not ok:
                self._fail_send("Mesaj kutusu bulunamadı veya metin yazılamadı")
                return
            self._schedule(120,self._click_send)

        try:
            self.page.runJavaScript(script,composed)
        except Exception as e:
            self._fail_send(str(e))

    def _click_send(self):
        def clicked(ok):
            if ok: self._schedule(180,self._confirm_send)
            else: self._fail_send("Gönder düğmesi ve Enter gönderimi başarısız")
        try:
            self.page.runJavaScript(self.CLICK_SEND_JS,clicked)
        except Exception as e:
            self._fail_send(str(e))

    def _confirm_send(self):
        def confirmed(empty):
            if empty:
                msg=self._outbox.popleft()
                self._send_busy=False
                self.sent.emit("WhatsApp",msg)
                self._begin_send()
            else:
                self._fail_send("Mesaj taslakta kaldı")
        try:
            self.page.runJavaScript(self.COMPOSER_EMPTY_JS,confirmed)
        except Exception as e:
            self._fail_send(str(e))

    def _fail_send(self,reason:str):
        self._status("Max mesajı gönderemedi: "+str(reason)[:120])
        def cleared(_ok=None):
            if self._outbox: self._outbox.popleft()
            self._send_busy=False
            self._begin_send()
        try:
            self.page.runJavaScript(self.CLEAR_COMPOSER_JS,cleared)
        except Exception:
            cleared(False)
