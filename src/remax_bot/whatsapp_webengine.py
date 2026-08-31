from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    from PySide6.QtCore import QObject, QTimer, Signal
except ImportError:
    class QObject:
        def __init__(self, *_args, **_kwargs):
            pass

    class _DummySignal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args):
            for callback in list(self._callbacks):
                callback(*args)

    def Signal(*_args, **_kwargs):
        return _DummySignal()

    class QTimer:
        def __init__(self, *_args, **_kwargs):
            self.timeout = _DummySignal()

        def setInterval(self, _milliseconds):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        @staticmethod
        def singleShot(_milliseconds, callback):
            callback()


MAX_INTRO = (
    "Max: Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. "
    "Komut listesini görmek için #? yazabilirsiniz."
)

MAX_STOPPED = (
    "Max: İlan arama botu durduruldu. "
    "Yeniden başlatmak için #Max başla yazabilirsiniz."
)


def _normalized(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def classify_command(text: str) -> str:
    value = str(text or "").strip()
    if not value.startswith("#"):
        return "ignore"
    if value.endswith("#") and len(value) > 1:
        value = value[:-1].rstrip()
    lowered = value.casefold()
    if lowered in {"#max başla", "#max başlat"}:
        return "start"
    if lowered in {"#max dur", "#max durdur"}:
        return "stop"
    return "query" if len(value) >= 2 else "ignore"


@dataclass
class RouteResult:
    replies: list[str] = field(default_factory=list)
    status: str = ""
    open_group: str = ""


class MessageRouter:
    """Routes stable WhatsApp message snapshots without touching the browser."""

    def __init__(self, response_fn: Callable[[str], str]):
        self.response_fn = response_fn
        self.configured_group = ""
        self.locked_chat_id = ""
        self.locked_chat_title = ""
        self.active = False
        self.seen = set()
        self._seen_order = deque()
        self.primed_chats = set()

    def set_group(self, group: str):
        self.configured_group = " ".join(str(group or "").split())
        self.locked_chat_id = ""
        self.locked_chat_title = ""
        self.active = False
        self.seen.clear()
        self._seen_order.clear()
        self.primed_chats.clear()

    def _remember(self, message_id: str):
        if not message_id or message_id in self.seen:
            return
        self.seen.add(message_id)
        self._seen_order.append(message_id)
        while len(self._seen_order) > 2000:
            old = self._seen_order.popleft()
            self.seen.discard(old)

    def process(self, snapshot: dict | None) -> RouteResult:
        result = RouteResult()
        if not isinstance(snapshot, dict):
            return result

        chat = snapshot.get("chat") or {}
        title = " ".join(str(chat.get("title") or "").split())
        chat_id = str(chat.get("id") or "").strip() or _normalized(title)
        if not title or not chat_id:
            return result

        target = self.configured_group or self.locked_chat_title
        if target and _normalized(title) != _normalized(target):
            result.open_group = target
            return result

        messages = snapshot.get("messages") or []
        if chat_id not in self.primed_chats:
            for message in messages:
                self._remember(str((message or {}).get("id") or "").strip())
            self.primed_chats.add(chat_id)
            result.status = f"{title} hazır - yeni #Max başla komutu bekleniyor"
            return result

        for message in messages:
            if not isinstance(message, dict):
                continue
            message_id = str(message.get("id") or "").strip()
            text = str(message.get("text") or "").strip()
            if not message_id or message_id in self.seen:
                continue
            self._remember(message_id)

            action = classify_command(text)
            if action == "start":
                if not self.configured_group and not self.locked_chat_id:
                    self.locked_chat_id = chat_id
                    self.locked_chat_title = title
                self.active = True
                result.replies.append(MAX_INTRO)
                result.status = f"Max aktif - {title} dinleniyor"
                continue

            if action == "stop":
                if self.active:
                    result.replies.append(MAX_STOPPED)
                self.active = False
                result.status = f"{title} hazır - #Max başla bekleniyor"
                continue

            if action != "query" or not self.active:
                continue

            answer = self.response_fn(text)
            if answer:
                answer = str(answer).strip()
                result.replies.append(answer if answer.startswith("Max:") else "Max: " + answer)

        return result


class EmbeddedWhatsAppBot(QObject):
    """Controls the WhatsApp Web page already displayed inside the application."""

    status = Signal(str)
    log = Signal(str)
    sent = Signal(str, str)

    SNAPSHOT_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return null;
      const clean=value=>String(value || '').replace(/\s+/g,' ').trim();
      const header=root.querySelector('header');
      const titleNode=header?.querySelector('span[title]') || header?.querySelector('[title]') || header?.querySelector('span[dir="auto"]');
      const title=clean(titleNode?.getAttribute?.('title') || titleNode?.innerText || titleNode?.textContent);
      if(!title) return null;
      const candidates=[
        ...root.querySelectorAll('[data-testid="msg-container"]'),
        ...root.querySelectorAll('.message-in,.message-out')
      ];
      const rows=[];
      const seenRows=new Set();
      for(const candidate of candidates.slice(-250)){
        const row=candidate.closest?.('[data-testid="msg-container"],.message-in,.message-out') || candidate;
        if(!row || seenRows.has(row)) continue;
        seenRows.add(row);
        const dataNode=(row.matches?.('[data-id]') ? row : null) || row.querySelector?.('[data-id]') || row.closest?.('[data-id]');
        const meta=(row.matches?.('[data-pre-plain-text]') ? row : null) || row.querySelector?.('[data-pre-plain-text]');
        const textNode=
          row.querySelector?.('[data-testid="msg-text"]') ||
          row.querySelector?.('span.selectable-text.copyable-text') ||
          row.querySelector?.('span[class*="selectable-text"]') ||
          row.querySelector?.('[class*="copyable-text"] span[dir]');
        const text=clean(textNode?.innerText || meta?.innerText || '');
        if(!text || !text.startsWith('#')) continue;
        const pre=meta?.getAttribute?.('data-pre-plain-text') || '';
        const dataId=dataNode?.getAttribute?.('data-id') || '';
        const id=dataId || `${pre}::${text}`;
        if(!id) continue;
        rows.push({id,text});
      }
      return {chat:{id:clean(title).toLocaleLowerCase('tr-TR'),title},messages:rows.slice(-100)};
    })()
    """

    SEARCH_GROUP_JS = r"""
    (() => {
      const wanted=__GROUP_JSON__;
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
      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand('insertText',false,wanted);
      box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:wanted}));
      return true;
    })()
    """

    OPEN_GROUP_JS = r"""
    (() => {
      const wanted=__GROUP_JSON__;
      const normalized=value=>String(value || '').replace(/\s+/g,' ').trim().toLocaleLowerCase('tr-TR');
      const target=normalized(wanted);
      const side=document.querySelector('#pane-side') || document.querySelector('#side');
      if(!side) return false;
      const nodes=Array.from(side.querySelectorAll('[title],span[dir="auto"],span[dir="ltr"],[role="gridcell"] span'));
      for(const node of nodes){
        const label=normalized(node.getAttribute?.('title') || node.innerText || node.textContent);
        if(label!==target) continue;
        const row=node.closest('[data-testid="cell-frame-container"],[role="listitem"],[role="row"]') || node;
        row.scrollIntoView({block:'center'});
        row.click();
        return true;
      }
      return false;
    })()
    """

    COMPOSE_MESSAGE_JS = r"""
    (() => {
      const message=__MESSAGE_JSON__;
      const root=document.querySelector('#main');
      if(!root) return false;
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const selectors=[
        'footer div[contenteditable="true"][role="textbox"]',
        'footer div[contenteditable="true"]',
        '[contenteditable="true"][data-lexical-editor="true"]'
      ];
      let box=null;
      for(const selector of selectors){
        box=Array.from(root.querySelectorAll(selector)).find(visible);
        if(box) break;
      }
      if(!box) return false;
      box.focus();
      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand('insertText',false,message);
      box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message}));
      return String(box.innerText || box.textContent || '').trim().length>0;
    })()
    """

    CLICK_SEND_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return false;
      const buttons=Array.from(root.querySelectorAll('button,[role="button"]'));
      const send=buttons.find(button=>{
        if(button.disabled || button.getAttribute('aria-disabled')==='true') return false;
        const label=String(button.getAttribute('aria-label') || '').trim().toLocaleLowerCase('tr-TR');
        const testid=String(button.getAttribute('data-testid') || '');
        const icon=button.querySelector('[data-icon="send"],[data-testid="send"],[data-testid="compose-btn-send"]');
        return label==='gönder' || label==='send' || testid==='send' || testid==='compose-btn-send' || !!icon;
      });
      if(!send) return false;
      send.click();
      return true;
    })()
    """

    COMPOSER_EMPTY_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      const box=root?.querySelector('footer div[contenteditable="true"][role="textbox"],footer div[contenteditable="true"],[contenteditable="true"][data-lexical-editor="true"]');
      if(!box) return false;
      return String(box.innerText || box.textContent || '').trim()==='';
    })()
    """

    CLEAR_COMPOSER_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      const box=root?.querySelector('footer div[contenteditable="true"][role="textbox"],footer div[contenteditable="true"],[contenteditable="true"][data-lexical-editor="true"]');
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

    def __init__(
        self,
        response_fn: Callable[[str], str],
        page=None,
        poll_ms: int = 1600,
        schedule: Optional[Callable[[int, Callable], None]] = None,
    ):
        super().__init__()
        self.router = MessageRouter(response_fn)
        self.page = page
        self.running = False
        self._read_pending = False
        self._opening_group = ""
        self._open_attempts = 0
        self._outbox = deque()
        self._send_busy = False
        self._send_attempts = 0
        self._confirm_attempts = 0
        self._last_status = ""
        self._schedule = schedule or (lambda milliseconds, callback: QTimer.singleShot(milliseconds, callback))
        self._timer = QTimer(self)
        self._timer.setInterval(max(500, int(poll_ms)))
        self._timer.timeout.connect(self.poll_once)

    @property
    def active(self):
        return self.router.active

    def attach_page(self, page):
        self.page = page

    def _status(self, text: str):
        if text and text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def start(self, group: str = ""):
        self.router.set_group(group)
        self.running = True
        self._timer.start()
        if self.router.configured_group:
            self._status(f"Uygulama içinde grup açılıyor: {self.router.configured_group}")
            self._open_group(self.router.configured_group)
        else:
            self._status("Max hazır - uygulama içindeki sohbette #Max başla bekleniyor")
        self._schedule(450, self.poll_once)
        return True

    def stop(self):
        self.running = False
        self.router.active = False
        self._timer.stop()
        self._status("Max durduruldu")

    def set_group(self, group: str):
        self.router.set_group(group)
        if self.router.configured_group:
            self._status(f"Kayıtlı grup uygulama içinde açılıyor: {self.router.configured_group}")
            self._open_group(self.router.configured_group)
        else:
            self._status("Grup seçimi otomatik - #Max başla yazılan sohbet kullanılacak")

    def poll_once(self):
        if not self.running or not self.page or self._read_pending:
            return
        self._read_pending = True
        try:
            self.page.runJavaScript(self.SNAPSHOT_JS, self._on_snapshot)
        except Exception as error:
            self._read_pending = False
            self.log.emit(str(error))
            self._status("WhatsApp sayfası okunamadı: " + str(error)[:120])

    def _on_snapshot(self, snapshot):
        self._read_pending = False
        if not self.running:
            return
        try:
            if not isinstance(snapshot, dict):
                if self.router.configured_group and not self._opening_group:
                    self._open_group(self.router.configured_group)
                return
            result = self.router.process(snapshot)
            if result.open_group:
                self._open_group(result.open_group)
                return
            if result.status:
                self._status(result.status)
            for reply in result.replies:
                self._send(reply)
        except Exception as error:
            self.log.emit(str(error))
            self._status("WhatsApp mesajı işlenemedi: " + str(error)[:120])

    @staticmethod
    def _inject(script: str, token: str, value: str) -> str:
        return script.replace(token, json.dumps(str(value), ensure_ascii=False))

    def _open_group(self, group: str):
        name = " ".join(str(group or "").split())
        if not name or not self.page:
            return False
        if _normalized(self._opening_group) == _normalized(name):
            return True
        self._opening_group = name
        search_script = self._inject(self.SEARCH_GROUP_JS, "__GROUP_JSON__", name)

        def searched(ok):
            if not ok:
                self._opening_group = ""
                self._status("WhatsApp arama kutusu hazır değil; sayfanın açılmasını bekliyorum")
                return
            self._open_attempts = 0
            self._schedule(350, try_open)

        def try_open():
            self._open_attempts += 1
            open_script = self._inject(self.OPEN_GROUP_JS, "__GROUP_JSON__", name)

            def opened(ok):
                if ok:
                    self._opening_group = ""
                    self._status(f"WhatsApp grubu uygulama içinde açıldı: {name}")
                    if self.running:
                        self._schedule(350, self.poll_once)
                    return
                if self._open_attempts < 12:
                    self._schedule(350, try_open)
                else:
                    self._opening_group = ""
                    self._status(f"'{name}' bulunamadı; grup adını kontrol edin")

            self.page.runJavaScript(open_script, opened)

        try:
            self.page.runJavaScript(search_script, searched)
            return True
        except Exception as error:
            self._opening_group = ""
            self.log.emit(str(error))
            self._status("Grup açılamadı: " + str(error)[:120])
            return False

    def _send(self, text: str):
        message = str(text or "").strip()
        if not message or not self.page:
            return False
        self._outbox.append(message)
        if not self._send_busy:
            self._begin_send()
        return True

    def _begin_send(self):
        if self._send_busy or not self._outbox or not self.page:
            return
        self._send_busy = True
        message = self._outbox[0]
        compose_script = self._inject(self.COMPOSE_MESSAGE_JS, "__MESSAGE_JSON__", message)

        def composed(ok):
            if not ok:
                self._fail_send("Mesaj kutusu bulunamadı")
                return
            self._send_attempts = 0
            self._schedule(140, self._click_send)

        try:
            self.page.runJavaScript(compose_script, composed)
        except Exception as error:
            self._fail_send(str(error))

    def _click_send(self):
        self._send_attempts += 1

        def clicked(ok):
            if ok:
                self._confirm_attempts = 0
                self._schedule(220, self._confirm_send)
            elif self._send_attempts < 4:
                self._schedule(140, self._click_send)
            else:
                self._fail_send("Gerçek Gönder düğmesi bulunamadı")

        self.page.runJavaScript(self.CLICK_SEND_JS, clicked)

    def _confirm_send(self):
        self._confirm_attempts += 1

        def confirmed(empty):
            if empty:
                message = self._outbox.popleft()
                self._send_busy = False
                self.sent.emit("WhatsApp", message)
                self._begin_send()
            elif self._confirm_attempts < 4:
                self._schedule(180, self._confirm_send)
            else:
                self._fail_send("Mesaj taslakta kaldı")

        self.page.runJavaScript(self.COMPOSER_EMPTY_JS, confirmed)

    def _fail_send(self, reason: str):
        self._status("Max mesajı gönderemedi: " + str(reason)[:120])

        def cleared(_ok=None):
            if self._outbox:
                self._outbox.popleft()
            self._send_busy = False
            self._begin_send()

        try:
            self.page.runJavaScript(self.CLEAR_COMPOSER_JS, cleared)
        except Exception as error:
            self.log.emit(str(error))
            cleared(False)
