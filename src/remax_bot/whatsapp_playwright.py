from __future__ import annotations

import queue
import threading
import json
from collections import deque
from pathlib import Path
from typing import Callable

from .whatsapp_webengine import (
    EmbeddedWhatsAppBot,
    MessageRouter,
    QObject,
    RouteResult,
    Signal,
)


EXTERNAL_SNAPSHOT_JS = r"""
(() => {
  const clean=value=>String(value || '').replace(/\s+/g,' ').trim();
  const visible=element=>!!element && (element.offsetParent!==null || element.getClientRects().length>0);
  const sidebar=element=>!!element?.closest?.('#side,#pane-side,[data-testid="chat-list"]');
  const main=document.querySelector('#main');
  const composers=Array.from(document.querySelectorAll(
    'footer [contenteditable="true"],[contenteditable="true"][role="textbox"]'
  )).filter(element=>visible(element) && !sidebar(element));
  if(!main && !composers.length) return null;

  const header=main?.querySelector('header') || document.querySelector('[data-testid="conversation-header"]');
  const titleNode=
    header?.querySelector('[data-testid="conversation-info-header-chat-title"]') ||
    header?.querySelector('span[dir="auto"][title]') ||
    header?.querySelector('span[dir="auto"]');
  const detectedTitle=clean(titleNode?.getAttribute('title') || titleNode?.textContent);

  const candidates=main ? Array.from(main.querySelectorAll(
    '[data-testid="msg-container"],.message-in,.message-out,[data-id],[data-pre-plain-text]'
  )) : [];
  const messages=[];
  const seen=new Set();
  let chatToken='';
  for(const candidate of candidates.slice(-400)){
    const row=candidate.closest(
      '[data-testid="msg-container"],.message-in,.message-out,[data-id],[role="row"]'
    ) || candidate;
    if(seen.has(row) || sidebar(row)) continue;
    seen.add(row);
    const idNode=row.matches('[data-id]') ? row : row.querySelector('[data-id]');
    const meta=row.matches('[data-pre-plain-text]') ? row : row.querySelector('[data-pre-plain-text]');
    const textNode=row.querySelector(
      '[data-testid="msg-text"],span.selectable-text.copyable-text,'+
      'span[class*="selectable-text"],[data-lexical-text="true"],[data-pre-plain-text]'
    );
    const text=clean(textNode?.innerText || meta?.innerText || row.innerText);
    if(!text.startsWith('#')) continue;
    const dataId=idNode?.getAttribute('data-id') || '';
    const pre=meta?.getAttribute('data-pre-plain-text') || '';
    if(!chatToken && dataId){
      const match=dataId.match(/^(?:true|false)_([^_]+)_/);
      if(match) chatToken=match[1];
    }
    const id=dataId || `${pre}::${text}`;
    if(id) messages.push({id,text,outgoing:row.matches('.message-out') || dataId.startsWith('true_')});
  }

  const title=detectedTitle || 'Açık sohbet';
  return {
    chat:{
      id:chatToken || clean(title).toLocaleLowerCase('tr-TR') || 'open-chat',
      title,
      identified:!!detectedTitle
    },
    messages:messages.slice(-150)
  };
})()
"""


class PlaywrightWhatsAppSession:
    """Synchronous browser boundary used by the background reader thread."""

    COMPOSER_SELECTOR = (
        'footer [contenteditable="true"][role="textbox"],'
        'footer [contenteditable="true"],'
        '[contenteditable="true"][role="textbox"]'
    )

    def __init__(self, page, context=None, playwright=None):
        self.page = page
        self.context = context
        self.playwright = playwright

    @classmethod
    def launch(cls, profile_dir: str | Path, stop_event=None):
        from playwright.sync_api import sync_playwright

        profile = Path(profile_dir)
        profile.mkdir(parents=True, exist_ok=True)
        playwright = sync_playwright().start()
        common = {
            "user_data_dir": str(profile),
            "headless": False,
            "no_viewport": True,
            "locale": "tr-TR",
            "timeout": 8_000,
            "args": [
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        }
        try:
            if stop_event is not None and stop_event.is_set():
                raise RuntimeError("WhatsApp okuyucusu kapatıldı")
            try:
                context = playwright.chromium.launch_persistent_context(
                    channel="chrome", **common
                )
            except Exception as chrome_error:
                if stop_event is not None and stop_event.is_set():
                    raise RuntimeError("WhatsApp okuyucusu kapatıldı") from chrome_error
                try:
                    context = playwright.chromium.launch_persistent_context(**common)
                except Exception as bundled_error:
                    raise RuntimeError(
                        "Google Chrome ve yedek Chromium başlatılamadı: "
                        f"{chrome_error}; {bundled_error}"
                    ) from bundled_error

            page = next(
                (item for item in context.pages if "web.whatsapp.com" in item.url),
                context.pages[0] if context.pages else context.new_page(),
            )
            page.set_default_timeout(10_000)
            if "web.whatsapp.com" not in page.url:
                if stop_event is not None and stop_event.is_set():
                    raise RuntimeError("WhatsApp okuyucusu kapatıldı")
                page.goto(
                    "https://web.whatsapp.com/",
                    wait_until="commit",
                    timeout=8_000,
                )
            page.bring_to_front()
            return cls(page, context=context, playwright=playwright)
        except Exception:
            playwright.stop()
            raise

    def snapshot(self):
        try:
            primary = self.page.evaluate(EmbeddedWhatsAppBot.SNAPSHOT_JS)
        except Exception:
            primary = None
        return primary if isinstance(primary, dict) else self.page.evaluate(EXTERNAL_SNAPSHOT_JS)

    def _composer(self):
        locator = self.page.locator(self.COMPOSER_SELECTOR)
        if locator.count() < 1:
            return None
        last = locator.last
        return last() if callable(last) else last

    def send(self, message: str):
        composer = self._composer()
        if composer is None or not composer.is_visible():
            return False
        composer.fill(str(message))
        composer.press("Enter")
        return True

    @staticmethod
    def _first_or_last(locator, name):
        item = getattr(locator, name)
        return item() if callable(item) else item

    def open_group(self, group: str):
        name = " ".join(str(group or "").split())
        if not name:
            return False
        search = self.page.locator(
            '[data-testid="chat-list-search"][contenteditable="true"],'
            '[data-testid="chat-list-search"] [contenteditable="true"],'
            '[data-testid="chat-list-search"] input,'
            '#side [data-testid="chat-list-search"] [contenteditable="true"],'
            '#side [contenteditable="true"][role="textbox"],'
            '#side input[placeholder*="Ara"],'
            '#side input[placeholder*="Search"]'
        )
        try:
            if search.count() > 0:
                box = self._first_or_last(search, "first")
                if box.is_visible():
                    box.fill(name)
                    self.page.wait_for_timeout(700)
                    side = self.page.locator("#pane-side")
                    if side.count() > 0:
                        match = side.get_by_text(name, exact=True)
                        if match.count() > 0:
                            target = self._first_or_last(match, "last")
                            target.click()
                            self.page.wait_for_timeout(500)
                            return True
        except Exception:
            pass

        search_script = EmbeddedWhatsAppBot.SEARCH_GROUP_JS.replace(
            "__GROUP_JSON__", json.dumps(name, ensure_ascii=False)
        )
        if not self.page.evaluate(search_script):
            return False
        self.page.wait_for_timeout(700)
        open_script = EmbeddedWhatsAppBot.OPEN_GROUP_JS.replace(
            "__GROUP_JSON__", json.dumps(name, ensure_ascii=False)
        )
        opened = bool(self.page.evaluate(open_script))
        if opened:
            self.page.wait_for_timeout(500)
        return opened

    def bring_to_front(self):
        self.page.bring_to_front()

    def close(self):
        try:
            if self.context is not None:
                self.context.close()
        finally:
            if self.playwright is not None:
                self.playwright.stop()


class WhatsAppConversationLoop:
    """Connects a browser session to the existing command router."""

    def __init__(
        self,
        response_fn: Callable[[str], str],
        session,
        initial_group: str = "",
    ):
        self.session = session
        self.router = MessageRouter(response_fn)
        self.router.set_group(initial_group)
        self.activation_pending = False
        self.last_snapshot = None
        self.pending_replies = deque()
        self.sent_replies = []

    @property
    def active(self):
        return self.router.active

    def start(self, group: str | None = None, activate: bool = True):
        if group is not None:
            self.router.set_group(group)
        self.pending_replies.clear()
        self.router.active = False
        self.activation_pending = bool(activate)

    def tick(self):
        self.sent_replies = []
        current = self.session.snapshot()
        self.last_snapshot = current
        if not self._has_real_chat(current):
            group = self.router.configured_group
            if group:
                self.session.open_group(group)
                return RouteResult(open_group=group)
            return None
        result = self.router.process(current, prime_only=self.activation_pending)

        if result.open_group:
            self.session.open_group(result.open_group)
            return result

        if self.activation_pending and isinstance(current, dict):
            self.activation_pending = False
            self.router.active = True

        self.pending_replies.extend(result.replies)
        while self.pending_replies:
            reply = self.pending_replies[0]
            if not self.session.send(reply):
                break
            self.pending_replies.popleft()
            self.sent_replies.append(reply)
        return result

    @staticmethod
    def _has_real_chat(snapshot):
        if not isinstance(snapshot, dict):
            return False
        chat = snapshot.get("chat") or {}
        title = " ".join(str(chat.get("title") or "").split()).casefold()
        chat_id = " ".join(str(chat.get("id") or "").split()).casefold()
        return bool(
            chat.get("identified")
            or (chat_id and chat_id not in {"open-chat", "açık sohbet"})
            or (title and title != "açık sohbet")
        )


class ExternalWhatsAppBot(QObject):
    """Runs WhatsApp Web in a persistent, visible Chrome session."""

    status = Signal(str)
    log = Signal(str)
    sent = Signal(str, str)

    def __init__(
        self,
        response_fn: Callable[[str], str],
        profile_dir: str | Path,
        initial_group: str = "",
        start_active: bool = False,
        poll_seconds: float = 0.9,
        session_factory=None,
    ):
        super().__init__()
        self.response_fn = response_fn
        self.profile_dir = Path(profile_dir)
        self.group = " ".join(str(initial_group or "").split())
        self._desired_active = bool(start_active)
        self._poll_seconds = max(0.5, float(poll_seconds))
        self._session_factory = session_factory or (
            lambda stop_event: PlaywrightWhatsAppSession.launch(
                self.profile_dir, stop_event=stop_event
            )
        )
        self._commands = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._loop = None
        self._session = None
        self._last_status = ""
        self._ensure_thread()

    @property
    def active(self):
        return self._loop.active if self._loop is not None else self._desired_active

    def _status(self, message: str):
        text = str(message or "").strip()
        if text and text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def _ensure_thread(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="RemaxWhatsAppChrome",
            daemon=True,
        )
        self._thread.start()

    def start(self, group: str = "", activate: bool = True):
        self.group = " ".join(str(group or "").split())
        self._desired_active = bool(activate)
        self._commands.put(("start",))
        self._ensure_thread()
        self._status("Max hazırlanıyor - Chrome'daki eski mesajlar atlanıyor")
        return True

    def stop(self):
        self._desired_active = False
        self._commands.put(("stop",))
        self._status("Max pasif - Chrome'da #Max başla komutu bekleniyor")

    def set_group(self, group: str):
        self.group = " ".join(str(group or "").split())
        self._commands.put(("group",))
        if self.group:
            self._status(f"Kayıtlı grup Chrome'da açılıyor: {self.group}")
        else:
            self._status("Grup otomatik - #Max başla yazılan sohbet kullanılacak")
        return True

    def show_browser(self):
        self._commands.put(("show",))
        self._ensure_thread()

    def shutdown(self):
        self._stop_event.set()
        self._commands.put(("shutdown",))
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _apply_commands(self, loop, session):
        while True:
            try:
                command = self._commands.get_nowait()[0]
            except queue.Empty:
                return
            if command == "shutdown":
                return
            if command == "show":
                session.bring_to_front()
                continue
            if command == "stop":
                loop.start(self.group, activate=False)
                continue
            if command == "group":
                keep_active = loop.active or self._desired_active
                loop.start(self.group, activate=keep_active)
                continue
            if command == "start":
                loop.start(self.group, activate=True)

    def _run_session(self, session):
        loop = WhatsAppConversationLoop(
            self.response_fn,
            session,
            initial_group=self.group,
        )
        self._loop = loop
        loop.start(self.group, activate=self._desired_active)
        self._status("Google Chrome hazır - WhatsApp sohbeti bekleniyor")

        while not self._stop_event.is_set():
            self._apply_commands(loop, session)
            was_pending = loop.activation_pending
            try:
                result = loop.tick()
                if result is None:
                    self._status(
                        "WhatsApp bekleniyor - Chrome'da QR kodunu okutun veya bir sohbet açın"
                    )
                elif result.open_group:
                    self._status(f"WhatsApp grubu Chrome'da açılıyor: {result.open_group}")
                elif was_pending and not loop.activation_pending and loop.active:
                    chat = (loop.last_snapshot or {}).get("chat") or {}
                    title = chat.get("title") or self.group or "açık sohbet"
                    self._status(f"Max aktif - {title} dinleniyor")
                elif result.status:
                    self._status(result.status)
                for reply in loop.sent_replies:
                    self.sent.emit("WhatsApp", reply)
                self._desired_active = loop.active
            except Exception as error:
                self.log.emit(str(error))
                self._status("WhatsApp sayfası okunamadı; Chrome yeniden kontrol ediliyor")
            self._stop_event.wait(self._poll_seconds)

    def _run(self):
        while not self._stop_event.is_set():
            session = None
            try:
                self._status("WhatsApp için Google Chrome açılıyor...")
                session = self._session_factory(self._stop_event)
                self._session = session
                self._run_session(session)
            except Exception as error:
                self.log.emit(str(error))
                self._status("Google Chrome açılamadı; 5 saniye sonra yeniden denenecek")
                self._stop_event.wait(5)
            finally:
                self._loop = None
                self._session = None
                if session is not None:
                    try:
                        session.close()
                    except Exception as error:
                        self.log.emit(str(error))
