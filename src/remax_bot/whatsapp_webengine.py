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
    """Routes stable WhatsApp snapshots and keeps Max in the selected chat."""

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
        while len(self._seen_order) > 2500:
            old = self._seen_order.popleft()
            self.seen.discard(old)

    def process(self, snapshot: dict | None) -> RouteResult:
        result = RouteResult()
        if not isinstance(snapshot, dict):
            return result

        chat = snapshot.get("chat") or {}
        raw_title = " ".join(str(chat.get("title") or "").split())
        identified = bool(
            chat.get(
                "identified",
                raw_title and _normalized(raw_title) != _normalized("Açık sohbet"),
            )
        )
        title = self.configured_group if self.configured_group and not identified else raw_title
        title = title or "Açık sohbet"
        chat_id = str(chat.get("id") or "").strip() or _normalized(title)
        if not title or not chat_id:
            return result

        if self.configured_group:
            if identified and _normalized(title) != _normalized(self.configured_group):
                result.open_group = self.configured_group
                return result
        elif self.locked_chat_id and chat_id != self.locked_chat_id:
            if _normalized(self.locked_chat_title) != _normalized("Açık sohbet"):
                result.open_group = self.locked_chat_title
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
      const clean=value=>String(value || '').replace(/\s+/g,' ').trim();
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);

      const composer=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][data-lexical-editor="true"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);

      const candidates=[
        ...document.querySelectorAll('[data-testid="msg-container"]'),
        ...document.querySelectorAll('.message-in,.message-out'),
        ...document.querySelectorAll('[data-pre-plain-text]')
      ];

      if(!candidates.length && !composer) return null;

      const root=document.querySelector('#main');
      const header=
        root?.querySelector('header') ||
        document.querySelector('[data-testid="conversation-header"]');
      const titleNode=
        header?.querySelector('[data-testid="conversation-info-header-chat-title"]') ||
        header?.querySelector('[data-testid="conversation-info-header"] span[dir="auto"]') ||
        header?.querySelector('span[dir="auto"][title]') ||
        header?.querySelector('span[dir="auto"]');

      const detectedTitle=clean(
        titleNode?.getAttribute?.('title') ||
        titleNode?.innerText ||
        titleNode?.textContent
      );

      const rows=[];
      const seenRows=new Set();
      let chatToken='';

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

        const pre=meta?.getAttribute?.('data-pre-plain-text') || '';
        const dataId=dataNode?.getAttribute?.('data-id') || '';
        if(!chatToken && dataId){
          const match=dataId.match(/^(?:true|false)_([^_]+)_/);
          if(match) chatToken=match[1];
        }

        if(!text || !text.startsWith('#')) continue;

        const id=dataId || `${pre}::${text}`;
        if(!id) continue;
        rows.push({id,text});
      }

      const title=detectedTitle || 'Açık sohbet';
      return {
        chat:{
          id:chatToken || clean(title).toLocaleLowerCase('tr-TR') || 'open-chat',
          title,
          identified:!!detectedTitle
        },
        messages:rows.slice(-120),
        diagnostics:{
          messageContainers:candidates.length,
          composer:!!composer,
          main:!!root
        }
      };
    })()
    """

    SEARCH_GROUP_JS = r"""
    (() => {
      const wanted=__GROUP_JSON__;
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const side=
        document.querySelector('#side') ||
        document.querySelector('#pane-side')?.parentElement ||
        document.querySelector('[data-testid="chat-list"]')?.parentElement?.parentElement;
      if(!side || side.closest?.('#main,footer')) return false;

      const selectors=[
        '[data-testid="chat-list-search"][contenteditable="true"]',
        '[data-testid="chat-list-search"] [contenteditable="true"]',
        '[data-testid="chat-list-search"] input',
        'header div[contenteditable="true"][role="textbox"]',
        'input[placeholder*="Ara"]',
        'input[placeholder*="Search"]'
      ];

      let box=null;
      for(const selector of selectors){
        box=Array.from(side.querySelectorAll(selector)).find(el=>
          visible(el) && !el.closest?.('#main,footer') &&
          (el.isContentEditable || el.tagName==='INPUT' || el.tagName==='TEXTAREA')
        );
        if(box) break;
      }
      if(!box) return false;

      box.focus();
      if(box.isContentEditable){
        const selection=window.getSelection();
        const range=document.createRange();
        range.selectNodeContents(box);
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand('delete',false,null);
        document.execCommand('insertText',false,wanted);
      }else{
        const proto=box.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;
        if(setter) setter.call(box,wanted); else box.value=wanted;
      }
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

      const nodes=Array.from(
        side.querySelectorAll('[title],span[dir="auto"],span[dir="ltr"],[role="gridcell"] span')
      );
      for(const node of nodes){
        const label=normalized(node.getAttribute?.('title') || node.innerText || node.textContent);
        if(label!==target) continue;
        const row=node.closest('[data-testid="cell-frame-container"],[role="listitem"],[role="row"]') || node;
        row.scrollIntoView?.({block:'center'});
        row.click();
        return true;
      }
      return false;
    })()
    """

    COMPOSE_MESSAGE_JS = r"""
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
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);

      const buttons=Array.from(
        document.querySelectorAll('footer button,footer [role="button"],button,[role="button"]')
      ).filter(visible);
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
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][data-lexical-editor="true"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);

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
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][data-lexical-editor="true"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);

      if(!box) return false;
      return String(box.innerText || box.textContent || '').trim()==='';
    })()
    """

    CLEAR_COMPOSER_JS = r"""
    (() => {
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][data-lexical-editor="true"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);

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

    CLEAR_LEAKED_GROUP_DRAFT_JS = r"""
    (() => {
      const wanted=__GROUP_JSON__;
      const visible=el=>!!el && (el.offsetParent!==null || el.getClientRects().length>0);
      const box=
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][role="textbox"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"][data-lexical-editor="true"]')).find(visible) ||
        Array.from(document.querySelectorAll('footer div[contenteditable="true"]')).find(visible);

      if(!box || !wanted) return false;
      const compact=value=>String(value || '').replace(/\s+/g,'').toLocaleLowerCase('tr-TR');
      const value=compact(box.innerText || box.textContent);
      const target=compact(wanted);
      const leaked=[2,3,4].some(count=>value===target.repeat(count));
      if(!leaked) return false;

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
        poll_ms: int = 900,
        schedule: Optional[Callable[[int, Callable], None]] = None,
    ):
        super().__init__()
        self.router = MessageRouter(response_fn)
        self.page = page
        self.running = False
        self._read_pending = False
        self._opening_group = ""
        self._opened_group = ""
        self._open_attempts = 0
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
        previous = self.router.configured_group
        self.router.set_group(group)
        if _normalized(previous) != _normalized(self.router.configured_group):
            self._opened_group = ""
        if not self.running:
            self.running = True
            self._timer.start()
        if self.router.configured_group:
            self._status(f"Uygulama içinde grup açılıyor: {self.router.configured_group}")
            self._open_group(self.router.configured_group)
        else:
            self._status("Max hazır - açık sohbette #Max başla bekleniyor")
        self._schedule(350, self.poll_once)
        return True

    def stop(self):
        # Keep the lightweight reader alive so #Max başla can activate Max again.
        self.router.active = False
        self._status("Max pasif - tekrar başlatmak için sohbete #Max başla yazın")

    def set_group(self, group: str):
        previous = self.router.configured_group
        self.router.set_group(group)
        if _normalized(previous) != _normalized(self.router.configured_group):
            self._opened_group = ""
        if self.router.configured_group:
            self._status(f"Kayıtlı grup uygulama içinde açılıyor: {self.router.configured_group}")
            self._open_group(self.router.configured_group)
        else:
            self._status("Grup seçimi otomatik - #Max başla yazılan sohbet kullanılacak")
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
                if (
                    self.router.configured_group
                    and not self._opening_group
                    and _normalized(self._opened_group)
                    != _normalized(self.router.configured_group)
                ):
                    self._open_group(self.router.configured_group)
                else:
                    self._status("Max dinleyici açık - WhatsApp'ta bir sohbet açın")
                return

            result = self.router.process(snapshot)

            if result.open_group:
                self._open_group(result.open_group, force=True)
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

    def _open_group(self, group: str, force: bool = False):
        name = " ".join(str(group or "").split())
        if not name or not self.page:
            return False
        if not force and _normalized(self._opened_group) == _normalized(name):
            return True
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
                    self._opened_group = name
                    cleanup_script = self._inject(
                        self.CLEAR_LEAKED_GROUP_DRAFT_JS,
                        "__GROUP_JSON__",
                        name,
                    )
                    self.page.runJavaScript(cleanup_script)
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
