from __future__ import annotations
import os, sys, time, threading, queue
from pathlib import Path
from typing import Callable, Optional

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    class QObject:
        pass
    class _DummySignal:
        def connect(self,*a,**k): pass
        def emit(self,*a,**k): pass
    def Signal(*a,**k): return _DummySignal()

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver=None
    Options=None
    By=None
    Keys=None
    WebDriverWait=None

MAX_INTRO = (
    "Max: Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. "
    "Komut listesini görmek için #? yazabilirsiniz."
)

def classify_command(text: str) -> str:
    t=(text or "").strip()
    if t.startswith("#") and t.endswith("#") and len(t)>1:
        t=t[:-1].rstrip()
    low=t.casefold()
    if low=="#max başla":
        return "start"
    if low in {"#max dur","#max durdur"}:
        return "stop"
    if t=="#?" or (len(t)>=2 and t.startswith("#")):
        return "query"
    return "ignore"

def _app_data() -> Path:
    h=Path.home()
    if os.name=="nt":
        return Path(os.getenv("LOCALAPPDATA",h))/"RemaxIlanBotu"
    return h/"Library"/"Application Support"/"RemaxIlanBotu"

class SeleniumWhatsAppBot(QObject):
    status=Signal(str)
    log=Signal(str)
    sent=Signal(str,str)

    JS_READ = r"""
    const messages=[];
    const rows=document.querySelectorAll('[data-testid="msg-container"]');
    rows.forEach((el,idx)=>{
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
        const x=el.querySelector(sel);
        if(x && x.innerText){ text=x.innerText.trim(); break; }
      }
      if(!text) text=(el.innerText || '').trim();

      let sender='';
      const copyable=el.querySelector('[data-pre-plain-text]');
      const pre=copyable ? (copyable.getAttribute('data-pre-plain-text') || '') : '';
      const m=pre.match(/] (.+?):\s*$/);
      if(m) sender=m[1].trim();

      messages.push({
        id:dataId || (pre+'::'+idx+'::'+text),
        text:text,
        sender:sender || (outgoing ? 'Siz' : 'Kullanıcı'),
        outgoing:outgoing,
        pre:pre
      });
    });
    return messages.slice(-60);
    """

    def __init__(self,response_fn:Callable[[str],str],profile_dir:Optional[Path]=None,poll_seconds:float=2.0):
        super().__init__()
        self.response_fn=response_fn
        self.profile_dir=Path(profile_dir or (_app_data()/"selenium-whatsapp-profile"))
        self.poll_seconds=poll_seconds
        self.running=False
        self.active=False
        self.driver=None
        self.seen=set()
        self._thread=None
        self._last_status=""
        self._send_queue=queue.Queue()

    def _status(self,text):
        if text!=self._last_status:
            self._last_status=text
            self.status.emit(text)

    def start(self,group=""):
        if self.running:
            return True
        self.running=True
        self.active=False
        self.seen.clear()
        self._thread=threading.Thread(target=self._run,name="MaxWhatsApp",daemon=True)
        self._thread.start()
        self._status("Max başlatılıyor - Chrome WhatsApp Web açılacak")
        return True

    def stop(self):
        self.running=False
        self.active=False
        self._status("Max durduruldu")
        drv=self.driver
        self.driver=None
        if drv:
            try: drv.quit()
            except Exception: pass

    def _chrome(self):
        if webdriver is None:
            raise RuntimeError('Selenium kurulmamış')
        self.profile_dir.mkdir(parents=True,exist_ok=True)
        opts=Options()
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--profile-directory=MaxBot")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-popup-blocking")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_experimental_option("excludeSwitches",["enable-automation"])
        opts.add_experimental_option("useAutomationExtension",False)
        # Selenium Manager resolves a matching driver for installed Chrome.
        return webdriver.Chrome(options=opts)

    def _run(self):
        try:
            self.driver=self._chrome()
            self.driver.get("https://web.whatsapp.com")
            self._status("WhatsApp Web açıldı - ilk kullanımda QR kodu okutun")
            WebDriverWait(self.driver,180).until(
                lambda d: d.execute_script(
                    'return document.querySelector(\'[data-testid="chat-list"],'
                    '[aria-label*="Sohbet"],[aria-label*="Chat"],#pane-side\') !== null'
                )
            )
            self._status("Max okuyucu hazır - istediğiniz sohbeti açıp #Max başla yazın")
            self._prime_seen()
            while self.running:
                self._poll()
                time.sleep(self.poll_seconds)
        except Exception as e:
            if self.running:
                self._status("Max WhatsApp hatası: "+str(e)[:140])
                self.log.emit(str(e))
        finally:
            drv=self.driver
            self.driver=None
            if drv:
                try: drv.quit()
                except Exception: pass

    def _prime_seen(self):
        try:
            rows=self.driver.execute_script(self.JS_READ) or []
            for m in rows:
                mid=m.get("id")
                if mid: self.seen.add(mid)
        except Exception:
            pass

    def _poll(self):
        rows=self.driver.execute_script(self.JS_READ) or []
        for m in rows:
            mid=(m.get("id") or "").strip()
            text=(m.get("text") or "").strip()
            if not mid or mid in self.seen:
                continue
            self.seen.add(mid)
            if len(self.seen)>1500:
                self.seen=set(list(self.seen)[-700:])
            if not text.startswith("#"):
                continue

            action=classify_command(text)
            if action=="start":
                self.active=True
                self._send(MAX_INTRO)
                self._status("Max aktif - açık WhatsApp sohbeti dinleniyor")
                continue
            if action=="stop":
                if self.active:
                    self._send("Max: İlan arama botu durduruldu. Yeniden başlatmak için #Max başla yazabilirsiniz.")
                self.active=False
                self._status("Max okuyucu hazır - #Max başla bekleniyor")
                continue
            if action!="query" or not self.active:
                continue

            answer=self.response_fn(text)
            if answer:
                answer=str(answer).strip()
                if not answer.startswith("Max:"):
                    answer="Max: "+answer
                self._send(answer)

    def _find_composer(self):
        selectors=[
            'footer div[contenteditable="true"][role="textbox"]',
            'footer div[contenteditable="true"]',
            'div[contenteditable="true"][role="textbox"]',
            '[contenteditable="true"][data-tab]'
        ]
        for sel in selectors:
            els=self.driver.find_elements(By.CSS_SELECTOR,sel)
            for el in reversed(els):
                try:
                    if el.is_displayed() and el.is_enabled():
                        return el
                except Exception:
                    pass
        return None

    def _send(self,text):
        box=self._find_composer()
        if box is None:
            self._status("Max mesaj kutusunu bulamadı - WhatsApp'ta bir sohbet açın")
            return False
        box.click()
        box.send_keys(str(text))
        box.send_keys(Keys.ENTER)
        self.sent.emit("WhatsApp",str(text))
        return True
