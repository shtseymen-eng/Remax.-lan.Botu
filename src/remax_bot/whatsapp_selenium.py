from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    class QObject:
        pass

    class _DummySignal:
        def connect(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

    def Signal(*args, **kwargs):
        return _DummySignal()

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None
    Options = None
    WebDriverWait = None


MAX_INTRO = (
    "Max: Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. "
    "Komut listesini görmek için #? yazabilirsiniz."
)


def classify_command(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("#") and value.endswith("#") and len(value) > 1:
        value = value[:-1].rstrip()
    lowered = value.casefold()
    if lowered == "#max başla":
        return "start"
    if lowered in {"#max dur", "#max durdur"}:
        return "stop"
    if value == "#?" or (len(value) >= 2 and value.startswith("#")):
        return "query"
    return "ignore"


def _app_data() -> Path:
    home = Path.home()
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA", home)) / "RemaxIlanBotu"
    return home / "Library" / "Application Support" / "RemaxIlanBotu"


class SeleniumWhatsAppBot(QObject):
    status = Signal(str)
    log = Signal(str)
    sent = Signal(str, str)

    SEARCH_GROUP_JS = r"""
    const wanted=String(arguments[0] || '').trim();
    const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
    const selectors=[
      '[data-testid="chat-list-search"]',
      '#side div[contenteditable="true"][role="textbox"]',
      '#side [contenteditable="true"][data-tab]',
      'div[contenteditable="true"][aria-label*="Sohbet"]',
      'div[contenteditable="true"][aria-label*="sohbet"]',
      'div[contenteditable="true"][aria-label*="Search"]',
      'div[contenteditable="true"][aria-label*="search"]'
    ];
    let box=null;
    for(const selector of selectors){
      box=Array.from(document.querySelectorAll(selector)).find(visible);
      if(box) break;
    }
    if(!box) return false;
    box.focus();
    if(box.isContentEditable){
      document.execCommand('selectAll',false,null);
      document.execCommand('insertText',false,wanted);
    }else{
      const proto=box.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
      if(setter) setter.call(box,wanted); else box.value=wanted;
    }
    box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:wanted}));
    box.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
    """

    OPEN_GROUP_JS = r"""
    const wanted=String(arguments[0] || '').trim();
    const normalized=value=>String(value || '').replace(/\s+/g,' ').trim().toLocaleLowerCase('tr-TR');
    const target=normalized(wanted);
    const side=document.querySelector('#pane-side') || document.querySelector('#side');
    if(!side) return false;
    const nodes=Array.from(side.querySelectorAll('[title],span[dir="auto"],span[dir="ltr"],[role="gridcell"] span'));
    for(const node of nodes){
      const label=normalized(node.getAttribute('title') || node.innerText || node.textContent);
      if(label!==target) continue;
      const row=node.closest('[data-testid="cell-frame-container"],[role="listitem"],[role="row"]') || node;
      row.scrollIntoView({block:'center'});
      row.click();
      return true;
    }
    return false;
    """

    JS_READ = r"""
    const root=document.querySelector('#main');
    if(!root) return [];
    const clean=value=>String(value || '').replace(/\s+/g,' ').trim();
    const candidates=[...new Set([
      ...root.querySelectorAll('[data-testid="msg-container"]'),
      ...root.querySelectorAll('.message-in,.message-out,[class*="message-in"],[class*="message-out"]'),
      ...root.querySelectorAll('[data-pre-plain-text]'),
      ...root.querySelectorAll('[data-id]')
    ])];
    const messages=[];
    const seenRows=new Set();
    for(const candidate of candidates.slice(-300)){
      const row=candidate.closest?.('[data-testid="msg-container"],.message-in,.message-out,[class*="message-in"],[class*="message-out"],[data-id]') || candidate;
      if(!row || seenRows.has(row)) continue;
      seenRows.add(row);
      let dataNode=row;
      while(dataNode && !dataNode.getAttribute?.('data-id')) dataNode=dataNode.parentElement;
      const dataId=dataNode?.getAttribute?.('data-id') || '';
      const outgoing=!!row.closest?.('.message-out,[class*="message-out"]') || dataId.startsWith('true_');
      const meta=(row.matches?.('[data-pre-plain-text]') ? row : null) || row.querySelector?.('[data-pre-plain-text]');
      const pre=meta?.getAttribute?.('data-pre-plain-text') || '';
      const textNode=
        row.querySelector?.('[data-testid="msg-text"]') ||
        row.querySelector?.('span.selectable-text.copyable-text') ||
        row.querySelector?.('span[class*="selectable-text"]') ||
        row.querySelector?.('[class*="copyable-text"] span[dir]');
      const fullText=clean(textNode?.innerText || meta?.innerText || row.innerText || '');
      if(!fullText) continue;
      let commands=fullText.match(/#[^#\n]+#/g) || [];
      if(!commands.length && fullText.startsWith('#')) commands=[fullText];
      if(!commands.length) continue;
      const senderMatch=pre.match(/\]\s*([^:]+):\s*$/);
      const sender=clean(senderMatch?.[1]) || (outgoing ? 'Siz' : 'Kullanıcı');
      commands.forEach((command,index)=>messages.push({
        id:dataId ? dataId+'::'+index : pre+'::'+index+'::'+clean(command),
        text:clean(command),
        sender,
        outgoing,
        pre
      }));
    }
    return messages.slice(-80);
    """

    SEND_MESSAGE_JS = r"""
    const message=String(arguments[0] || '');
    const root=document.querySelector('#main');
    if(!root) return false;
    const selectors=[
      'footer div[contenteditable="true"][role="textbox"]',
      'footer div[contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"]',
      '[contenteditable="true"][data-lexical-editor="true"]',
      '[contenteditable="true"][data-tab]'
    ];
    let box=null;
    for(const selector of selectors){
      const found=Array.from(root.querySelectorAll(selector));
      box=found.find(el=>el.offsetParent!==null || el.getClientRects().length>0);
      if(box) break;
    }
    if(!box) return false;
    box.focus();
    document.execCommand('selectAll',false,null);
    document.execCommand('insertText',false,message);
    box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message}));
    const send=
      root.querySelector('[data-testid="send"]')?.closest('button,[role="button"]') ||
      root.querySelector('[data-testid="compose-btn-send"]') ||
      root.querySelector('button[aria-label="Gönder"]') ||
      root.querySelector('button[aria-label="Send"]') ||
      root.querySelector('[data-icon="send"]')?.closest('button,[role="button"]');
    if(send){ send.click(); return true; }
    box.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));
    box.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));
    return true;
    """

    def __init__(
        self,
        response_fn: Callable[[str], str],
        profile_dir: Optional[Path] = None,
        poll_seconds: float = 2.0,
    ):
        super().__init__()
        self.response_fn = response_fn
        self.profile_dir = Path(profile_dir or (_app_data() / "selenium-whatsapp-profile"))
        self.poll_seconds = poll_seconds
        self.group = ""
        self.running = False
        self.active = False
        self.driver = None
        self.seen = set()
        self._thread = None
        self._last_status = ""

    def _status(self, text):
        if text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def start(self, group=""):
        if self.running:
            return True
        self.group = (group or "").strip()
        self.running = True
        self.active = False
        self.seen.clear()
        self._thread = threading.Thread(target=self._run, name="MaxWhatsApp", daemon=True)
        self._thread.start()
        self._status("Max başlatılıyor - Chrome WhatsApp Web açılacak")
        return True

    def stop(self):
        self.running = False
        self.active = False
        self._status("Max durduruldu")
        driver = self.driver
        self.driver = None
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    def _chrome(self):
        if webdriver is None:
            raise RuntimeError("Selenium kurulmamış")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options = Options()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--profile-directory=MaxBot")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        return webdriver.Chrome(options=options)

    def _open_group(self, group: str, timeout_seconds: float = 12) -> bool:
        name = (group or "").strip()
        if not name:
            return True
        self._status(f"WhatsApp grubu aranıyor: {name}")
        if not self.driver.execute_script(self.SEARCH_GROUP_JS, name):
            self._status("WhatsApp arama kutusu bulunamadı; grubu Chrome'da manuel açın")
            return False
        deadline = time.monotonic() + max(0, timeout_seconds)
        while True:
            if self.driver.execute_script(self.OPEN_GROUP_JS, name):
                self._status(f"WhatsApp grubu açıldı: {name}")
                return True
            if time.monotonic() >= deadline:
                break
            time.sleep(0.35)
        self._status(f"'{name}' bulunamadı; grubu Chrome'da manuel açın")
        return False

    def _run(self):
        try:
            self.driver = self._chrome()
            self.driver.get("https://web.whatsapp.com")
            self._status("WhatsApp Web açıldı - ilk kullanımda QR kodu okutun")
            WebDriverWait(self.driver, 180).until(
                lambda driver: driver.execute_script(
                    "return document.querySelector('[data-testid=\"chat-list\"],"
                    "[aria-label*=\"Sohbet\"],[aria-label*=\"Chat\"],#pane-side') !== null"
                )
            )
            if self.group:
                self._open_group(self.group)
            else:
                self._status("Max okuyucu hazır - Chrome'da sohbeti açıp #Max başla yazın")
            self._prime_seen()
            while self.running:
                self._poll()
                time.sleep(self.poll_seconds)
        except Exception as error:
            if self.running:
                self._status("Max WhatsApp hatası: " + str(error)[:180])
                self.log.emit(str(error))
        finally:
            driver = self.driver
            self.driver = None
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _prime_seen(self):
        try:
            rows = self.driver.execute_script(self.JS_READ) or []
            for message in rows:
                message_id = message.get("id")
                if message_id:
                    self.seen.add(message_id)
        except Exception:
            pass

    def _poll(self):
        rows = self.driver.execute_script(self.JS_READ) or []
        for message in rows:
            message_id = (message.get("id") or "").strip()
            text = (message.get("text") or "").strip()
            if not message_id or message_id in self.seen:
                continue
            self.seen.add(message_id)
            if len(self.seen) > 1500:
                self.seen = set(list(self.seen)[-700:])
            action = classify_command(text)
            if action == "start":
                self.active = True
                self._send(MAX_INTRO)
                self._status("Max aktif - WhatsApp mesajları dinleniyor")
                continue
            if action == "stop":
                if self.active:
                    self._send(
                        "Max: İlan arama botu durduruldu. "
                        "Yeniden başlatmak için #Max başla yazabilirsiniz."
                    )
                self.active = False
                self._status("Max okuyucu hazır - #Max başla bekleniyor")
                continue
            if action != "query" or not self.active:
                continue
            answer = self.response_fn(text)
            if answer:
                answer = str(answer).strip()
                if not answer.startswith("Max:"):
                    answer = "Max: " + answer
                self._send(answer)

    def _send(self, text):
        if not text or not self.driver:
            return False
        try:
            sent = bool(self.driver.execute_script(self.SEND_MESSAGE_JS, str(text)))
            if not sent:
                self._status("Max mesaj kutusunu bulamadı; Chrome'da bir sohbet açın")
                return False
            self.sent.emit("WhatsApp", str(text))
            return True
        except Exception as error:
            self.log.emit(str(error))
            self._status("Max mesajı gönderemedi: " + str(error)[:120])
            return False
