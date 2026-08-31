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
            self.running = False

        def setInterval(self, _milliseconds):
            pass

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

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


class MessageRouter:
    """Routes commands from whichever WhatsApp conversation is currently open."""

    def __init__(self, response_fn: Callable[[str], str]):
        self.response_fn = response_fn
        self.active = False
        self.seen = set()
        self._seen_order = deque()
        self.primed_chats = set()

    def reset(self):
        self.active = False
        self.seen.clear()
        self._seen_order.clear()
        self.primed_chats.clear()

    def _remember(self, message_id: str):
        if not message_id or message_id in self.seen:
            return
        self.seen.add(message_id)
        self._seen_order.append(message_id)
        while len(self._seen_order) > 2500:
            old = self._seen_order.popleft()
            self.seen.discard(old)

    def process(self, snapshot: dict | None) -> RouteResult:
        result = RouteResult()
        if not isinstance(snapshot, dict):
            return result

        chat = snapshot.get("chat") or {}
        title = " ".join(str(chat.get("title") or "").split())
        chat_id = str(chat.get("id") or "").strip() or title.casefold()
        if not title or not chat_id:
            return result

        messages = snapshot.get("messages") or []

        # First sight of a chat only records history. This stops an old #Max command
        # from reactivating Max when the user changes conversations.
        if chat_id not in self.primed_chats:
            for message in messages:
                self._remember(str((message or {}).get("id") or "").strip())
            self.primed_chats.add(chat_id)
            result.status = f"Max dinleyici hazır - {title} içinde #Max başla yazın"
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
                self.active = True
                result.replies.append(MAX_INTRO)
                result.status = f"Max aktif - {title} dinleniyor"
                continue

            if action == "stop":
                if self.active:
                    result.replies.append(MAX_STOPPED)
                self.active = False
                result.status = f"Max dinleyici hazır - {title} içinde #Max başla yazın"
                continue

            if action != "query" or not self.active:
                continue

            answer = self.response_fn(text)
            if answer:
                answer = str(answer).strip()
                result.replies.append(
                    answer if answer.startswith("Max:") else "Max: " + answer
                )

        return result


class EmbeddedWhatsAppBot(QObject):
    """Reads and writes the WhatsApp Web page already visible in the app."""

    status = Signal(str)
    log = Signal(str)
    sent = Signal(str, str)

    SNAPSHOT_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return null;

      const clean=value=>String(value || '').replace(/\s+/g,' ').trim();

      const header=root.querySelector('header');
      const titleNode=
        header?.querySelector('span[title]') ||
        header?.querySelector('[title]') ||
        header?.querySelector('span[dir="auto"]');

      const title=clean(
        titleNode?.getAttribute?.('title') ||
        titleNode?.innerText ||
        titleNode?.textContent
      );
      if(!title) return null;

      const candidates=[
        ...root.querySelectorAll('[data-testid="msg-container"]'),
        ...root.querySelectorAll('.message-in,.message-out'),
        ...root.querySelectorAll('[data-pre-plain-text]')
      ];

      const rows=[];
      const seenRows=new Set();

      for(const candidate of candidates.slice(-300)){
        const row=
          candidate.closest?.('[data-testid="msg-container"],.message-in,.message-out,[data-id]') ||
          candidate;

        if(!row || seenRows.has(row)) continue;
        seenRows.add(row);

        let dataNode=row;
        while(dataNode && !dataNode.getAttribute?.('data-id')){
          dataNode=dataNode.parentElement;
        }

        const meta=
          (candidate.matches?.('[data-pre-plain-text]') ? candidate : null) ||
          row.querySelector?.('[data-pre-plain-text]');

        const textNode=
          row.querySelector?.('[data-testid="msg-text"]') ||
          row.querySelector?.('span.selectable-text.copyable-text') ||
          row.querySelector?.('span[class*="selectable-text"]') ||
          row.querySelector?.('[class*="copyable-text"] span[dir]');

        const text=clean(
          textNode?.innerText ||
          meta?.innerText ||
          row.innerText ||
          ''
        );

        if(!text || !text.startsWith('#')) continue;

        const pre=meta?.getAttribute?.('data-pre-plain-text') || '';
        const dataId=dataNode?.getAttribute?.('data-id') || '';
        const id=dataId || `${pre}::${text}`;

        if(!id) continue;
        rows.push({id,text});
      }

      return {
        chat:{
          id:clean(title).toLocaleLowerCase('tr-TR'),
          title
        },
        messages:rows.slice(-120)
      };
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
        'footer div[contenteditable="true"][data-lexical-editor="true"]',
        'footer div[contenteditable="true"]'
      ];

      let box=null;
      for(const selector of selectors){
        const matches=Array.from(root.querySelectorAll(selector)).filter(visible);
        if(matches.length){
          box=matches[matches.length-1];
          break;
        }
      }
      if(!box) return false;

      box.focus();

      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);

      // Important: remove any stale draft first. This prevents
      // "Bot denemeBot deneme" and duplicate Max responses.
      document.execCommand('delete',false,null);
      if(String(box.textContent || '').trim()){
        box.textContent='';
      }
      box.dispatchEvent(new InputEvent('input',{
        bubbles:true,
        inputType:'deleteContentBackward',
        data:null
      }));

      box.focus();
      const freshRange=document.createRange();
      freshRange.selectNodeContents(box);
      freshRange.collapse(false);
      selection.removeAllRanges();
      selection.addRange(freshRange);

      document.execCommand('insertText',false,message);
      box.dispatchEvent(new InputEvent('input',{
        bubbles:true,
        inputType:'insertText',
        data:message
      }));

      return String(box.innerText || box.textContent || '').trim()===String(message).trim();
    })()
    """

    CLICK_SEND_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return false;

      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);

      const buttons=Array.from(root.querySelectorAll('button,[role="button"]')).filter(visible);
      const send=buttons.find(button=>{
        if(button.disabled || button.getAttribute('aria-disabled')==='true') return false;

        const label=String(button.getAttribute('aria-label') || '')
          .trim().toLocaleLowerCase('tr-TR');

        const testid=String(button.getAttribute('data-testid') || '');

        const icon=button.querySelector(
          '[data-icon="send"],[data-testid="send"],[data-testid="compose-btn-send"]'
        );

        return (
          label==='gönder' ||
          label==='send' ||
          testid==='send' ||
          testid==='compose-btn-send' ||
          !!icon
        );
      });

      if(send){
        send.click();
        return true;
      }

      // WhatsApp sometimes exposes the send icon only after keyboard input.
      // Enter is a safe fallback for the normal text composer.
      const box=
        root.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
        root.querySelector('footer div[contenteditable="true"][data-lexical-editor="true"]') ||
        root.querySelector('footer div[contenteditable="true"]');

      if(!box) return false;

      box.focus();
      box.dispatchEvent(new KeyboardEvent('keydown',{
        bubbles:true,
        cancelable:true,
        key:'Enter',
        code:'Enter',
        keyCode:13,
        which:13
      }));
      box.dispatchEvent(new KeyboardEvent('keyup',{
        bubbles:true,
        cancelable:true,
        key:'Enter',
        code:'Enter',
        keyCode:13,
        which:13
      }));
      return true;
    })()
    """

    COMPOSER_EMPTY_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return false;

      const box=
        root.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
        root.querySelector('footer div[contenteditable="true"][data-lexical-editor="true"]') ||
        root.querySelector('footer div[contenteditable="true"]');

      if(!box) return false;
      return String(box.innerText || box.textContent || '').trim()==='';
    })()
    """

    CLEAR_COMPOSER_JS = r"""
    (() => {
      const root=document.querySelector('#main');
      if(!root) return false;

      const box=
        root.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
        root.querySelector('footer div[contenteditable="true"][data-lexical-editor="true"]') ||
        root.querySelector('footer div[contenteditable="true"]');

      if(!box) return false;

      box.focus();

      const selection=window.getSelection();
      const range=document.createRange();
      range.selectNodeContents(box);
      selection.removeAllRanges();
      selection.addRange(range);

      document.execCommand('delete',false,null);
      if(String(box.textContent || '').trim()){
        box.textContent='';
      }

      box.dispatchEvent(new InputEvent('input',{
        bubbles:true,
        inputType:'deleteContentBackward',
        data:null
      }));

      return true;
    })()
    """

    def __init__(
        self,
        response_fn: Callable[[str], str],
        page=None,
        poll_ms: int = 900,
        schedule: Optional[Callable[[int, Callable], None]] = None,
    ):
        super().__init__()
        self.router = MessageRouter(response_fn)
        self.page = page
        self.running = False
        self._read_pending = False
        self._outbox = deque()
        self._send_busy = False
        self._send_attempts = 0
        self._confirm_attempts = 0
        self._last_status = ""
        self._schedule = schedule or (
            lambda milliseconds, callback: QTimer.singleShot(milliseconds, callback)
        )

        self._timer = QTimer(self)
        self._timer.setInterval(max(500, int(poll_ms)))
        self._timer.timeout.connect(self.poll_once)

        # No sidebar button is required. The reader starts by itself and waits
        # for #Max başla inside whichever conversation the user opens.
        self._schedule(700, self._auto_start_when_ready)

    @property
    def active(self):
        return self.router.active

    def attach_page(self, page):
        self.page = page
        self._auto_start_when_ready()

    def _status(self, text: str):
        if text and text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def _auto_start_when_ready(self):
        if not self.running:
            self.start()

    def start(self, group: str = ""):
        # group is intentionally ignored. Max listens to the conversation
        # the human actually has open; it never types a saved chat name.
        if not self.running:
            self.running = True
            self._timer.start()
        self._status("Max dinleyici açık - WhatsApp sohbetinde #Max başla yazın")
        self._schedule(300, self.poll_once)
        return True

    def stop(self):
        # Keep the lightweight reader alive so #Max başla can activate Max again.
        self.router.active = False
        self._status("Max pasif - tekrar başlatmak için sohbete #Max başla yazın")

    def set_group(self, group: str):
        # Kept for app compatibility. Saved group names are no longer typed
        # into WhatsApp because that caused chat names to land in the composer.
        self._status("Max açık sohbeti kullanır - #Max başla yazın")
        return True

    def shutdown(self):
        self.running = False
        self.router.active = False
        self._timer.stop()

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
                self._status("Max dinleyici açık - WhatsApp'ta bir sohbet açın")
                return

            result = self.router.process(snapshot)

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

    def _send(self, text: str):
        message = str(text or "").strip()
        if not message or not self.page:
            return False

        # Do not enqueue the same pending text twice.
        if message in self._outbox:
            return True

        self._outbox.append(message)
        if not self._send_busy:
            self._begin_send()
        return True

    def _begin_send(self):
        if self._send_busy or not self._outbox or not self.page:
            return

        self._send_busy = True
        message = self._outbox[0]
        compose_script = self._inject(
            self.COMPOSE_MESSAGE_JS,
            "__MESSAGE_JSON__",
            message,
        )

        def composed(ok):
            if not ok:
                self._fail_send("Mesaj kutusu bulunamadı veya metin doğru yazılamadı")
                return

            self._send_attempts = 0
            self._schedule(120, self._click_send)

        try:
            self.page.runJavaScript(compose_script, composed)
        except Exception as error:
            self._fail_send(str(error))

    def _click_send(self):
        self._send_attempts += 1

        def clicked(ok):
            if ok:
                self._confirm_attempts = 0
                self._schedule(180, self._confirm_send)
            elif self._send_attempts < 3:
                self._schedule(150, self._click_send)
            else:
                self._fail_send("Gönder düğmesi ve Enter gönderimi başarısız")

        try:
            self.page.runJavaScript(self.CLICK_SEND_JS, clicked)
        except Exception as error:
            self._fail_send(str(error))

    def _confirm_send(self):
        self._confirm_attempts += 1

        def confirmed(empty):
            if empty:
                message = self._outbox.popleft()
                self._send_busy = False
                self.sent.emit("WhatsApp", message)
                self._begin_send()
            elif self._confirm_attempts < 5:
                self._schedule(180, self._confirm_send)
            else:
                self._fail_send("Mesaj taslakta kaldı")

        try:
            self.page.runJavaScript(self.COMPOSER_EMPTY_JS, confirmed)
        except Exception as error:
            self._fail_send(str(error))

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
