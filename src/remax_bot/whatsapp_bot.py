from __future__ import annotations
import json
from PySide6.QtCore import QObject, QTimer, Signal

from .whatsapp_logic import should_process, decorate_response, command_key

# V24: Grup araması / grup başlığı eşleştirmesi yok.
# Bot yalnızca WhatsApp Web'de o anda açık olan sohbet panelini (#main) dinler.
POLL_JS = r'''(() => {
  const clean=s => String(s||'').replace(/\s+/g,' ').trim();
  const main=document.querySelector('#main');
  if(!main) return {isOpen:false,messages:[]};

  const messages=[];
  const seenRows=new Set();
  const candidateRows=[
    ...Array.from(main.querySelectorAll('.message-in,.message-out')),
    ...Array.from(main.querySelectorAll('[data-id]')),
    ...Array.from(main.querySelectorAll('[data-pre-plain-text]')).map(x=>x.closest('[data-id],.message-in,.message-out')||x.parentElement),
    ...Array.from(main.querySelectorAll('[class*="copyable-text"]')).map(x=>x.closest('[data-id],.message-in,.message-out')||x.parentElement)
  ].filter(Boolean);

  for(const row0 of candidateRows.slice(-220)){
    const row=row0.closest?.('.message-in,.message-out,[data-id]') || row0;
    if(!row || seenRows.has(row)) continue;
    seenRows.add(row);

    const direction=row.classList?.contains('message-out') ? 'out' : 'in';
    const meta=row.querySelector?.('[data-pre-plain-text]');
    const pre=meta?.getAttribute('data-pre-plain-text') || '';

    // Görünen mesaj metnini birkaç güncel WhatsApp yapısından toplamaya çalış.
    const textParts=[];
    const copyable=row.querySelector?.('[class*="copyable-text"]');
    if(copyable?.innerText) textParts.push(copyable.innerText);
    for(const el of Array.from(row.querySelectorAll?.('span[dir="ltr"],span[dir="auto"],div[dir="auto"]')||[])){
      if(el.innerText) textParts.push(el.innerText);
    }
    if(row.innerText) textParts.push(row.innerText);
    const fullText=clean(textParts.join(' '));
    if(!fullText) continue;

    const commands=fullText.match(/#[^#\n]+#/g) || [];
    if(!commands.length) continue;

    let sender='',stamp='';
    const m=pre.match(/^\[([^\]]+)\]\s*([^:]+):/);
    if(m){ stamp=clean(m[1]); sender=clean(m[2]); }
    if(!sender) sender=direction==='out' ? 'Siz' : 'Kullanıcı';

    const id=row.getAttribute?.('data-id') || row.closest?.('[data-id]')?.getAttribute('data-id') || '';
    commands.forEach((cmd,idx)=>messages.push({
      sender,
      text:clean(cmd),
      stamp,
      pre,
      id:id ? id+':'+idx : '',
      direction
    }));
  }

  return {isOpen:true,messages};
})()'''

SEND_JS = r'''((message) => {
  const main=document.querySelector('#main');
  if(!main) return {ok:false,error:'Açık WhatsApp sohbeti bulunamadı'};
  const box=main.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
            main.querySelector('footer [contenteditable="true"]') ||
            main.querySelector('div[contenteditable="true"][role="textbox"]');
  if(!box) return {ok:false,error:'Mesaj kutusu bulunamadı'};

  box.focus();
  document.execCommand('selectAll',false,null);
  document.execCommand('insertText',false,String(message));
  box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:String(message)}));

  const send=main.querySelector('button[aria-label="Gönder"],button[aria-label="Send"],[data-testid="send"],[data-icon="send"]')?.closest('button,[role="button"]') ||
             main.querySelector('button[aria-label="Gönder"],button[aria-label="Send"],[data-testid="send"]');
  if(send){ send.click(); return {ok:true}; }

  box.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));
  box.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));
  return {ok:true};
})'''


class WhatsAppBot(QObject):
    status=Signal(str)
    log=Signal(str)
    sent=Signal(str,str)

    def __init__(self, view, response_fn, interval_ms=2200):
        super().__init__()
        self.view=view
        self.response_fn=response_fn
        self.group=''
        self.running=False
        self.seen=set()
        self.last_status=''
        self.timer=QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.poll)

    def _status(self, text: str):
        if text != self.last_status:
            self.last_status=text
            self.status.emit(text)

    def start(self, group: str=''):
        # Grup adı V24'te yalnızca bilgi/etiket amaçlıdır; çalışma koşulu değildir.
        self.group=(group or '').strip()
        self.running=True
        self.seen.clear()
        self.last_status=''
        self.timer.start()
        self._status('Aktif - WhatsApp sekmesinde açık sohbet bekleniyor')
        QTimer.singleShot(500,self.poll)
        return True

    def stop(self):
        self.running=False
        self.timer.stop()
        self._status('Durduruldu')

    def poll(self):
        if not self.running:
            return
        self.view.page().runJavaScript(POLL_JS,self._polled)

    def _polled(self, result):
        if not self.running:
            return
        result=result or {}
        if not result.get('isOpen'):
            self._status('WhatsApp açık - bir sohbet açın')
            return

        self._status('Dinleniyor: açık WhatsApp sohbeti')
        for m in result.get('messages') or []:
            text=(m.get('text') or '').strip()
            if not should_process(text):
                continue
            sender=(m.get('sender') or ('Siz' if m.get('direction')=='out' else 'Kullanıcı')).strip()
            stamp=(m.get('id') or m.get('stamp') or m.get('pre') or (m.get('direction','')+text)).strip()
            key=command_key(sender,text,stamp)
            if key in self.seen:
                continue
            self.seen.add(key)
            if len(self.seen)>500:
                self.seen=set(list(self.seen)[-250:])
            response=self.response_fn(text)
            if not response:
                continue
            reply=decorate_response(sender,response)
            self._send(reply,sender)

    def _send(self, message: str, sender: str):
        js=SEND_JS + '(' + json.dumps(message,ensure_ascii=False) + ')'
        self.view.page().runJavaScript(js,lambda r:self._sent_result(r,sender,message))

    def _sent_result(self,result,sender,message):
        if result and result.get('ok'):
            self.sent.emit(sender,message)
        else:
            err=(result or {}).get('error','WhatsApp mesajı gönderilemedi')
            self._status(err)
