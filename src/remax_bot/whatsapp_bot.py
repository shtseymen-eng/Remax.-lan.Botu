from __future__ import annotations
import json
from PySide6.QtCore import QObject,QTimer,Signal
from .whatsapp_logic import command_key
from .whatsapp_state import ActivationGate

# WhatsApp'ın çalışan eski Selenium uygulamasında güvenilir olan ana mesaj
# seçicisi msg-container idi. Gömülü QWebEngine okuyucu da aynı yapıyı esas alır.
POLL_JS=r"""(() => {
 const clean=s=>String(s||'').replace(/\s+/g,' ').trim();

 const msgContainers=Array.from(document.querySelectorAll('[data-testid="msg-container"]'));
 const inputBox=
   document.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
   document.querySelector('footer [contenteditable="true"]') ||
   document.querySelector('[contenteditable="true"][role="textbox"]') ||
   document.querySelector('[contenteditable="true"][data-tab]');

 // Sohbet açık olduğunu yalnız #main veya footer'a bağlamıyoruz.
 // Mesaj kutusu veya gerçek WhatsApp mesaj kapsayıcısı varsa açık sohbet vardır.
 const isOpen=msgContainers.length>0 || !!inputBox;
 if(!isOpen){
   return {isOpen:false,messages:[],reason:'no-message-container-or-input'};
 }

 let conversationRoot=document.querySelector('#main') || document.body;
 const rows=msgContainers.length
   ? msgContainers
   : [
       ...Array.from(conversationRoot.querySelectorAll('.message-in,.message-out')),
       ...Array.from(conversationRoot.querySelectorAll('[data-id]')),
       ...Array.from(conversationRoot.querySelectorAll('[data-pre-plain-text]'))
     ];

 const messages=[];
 const seenRows=new Set();

 for(const el of rows.slice(-240)){
   const row=el.closest?.('.message-in,.message-out,[data-id]') || el;
   if(!row || seenRows.has(row)) continue;
   seenRows.add(row);

   const outNode=el.closest?.('[class*="message-out"]') || row.closest?.('[class*="message-out"]');
   const inNode=el.closest?.('[class*="message-in"]') || row.closest?.('[class*="message-in"]');
   const direction=outNode ? 'out' : (inNode ? 'in' : 'in');

   const meta=el.querySelector?.('[data-pre-plain-text]') ||
              row.querySelector?.('[data-pre-plain-text]');
   const pre=meta?.getAttribute('data-pre-plain-text') || '';

   const copyable=el.querySelector?.('[class*="copyable-text"]') ||
                  row.querySelector?.('[class*="copyable-text"]');
   const selectable=el.querySelector?.('span.selectable-text') ||
                    row.querySelector?.('span.selectable-text');

   let fullText=clean(
       selectable?.innerText ||
       copyable?.innerText ||
       meta?.innerText ||
       el.innerText ||
       row.innerText ||
       ''
   );
   if(!fullText) continue;

   // Eski #komut# biçimi ve yeni tek # biçimi birlikte desteklenir.
   let commands=fullText.match(/#[^#\n]+#/g) || [];
   if(!commands.length && fullText.startsWith('#')) commands=[fullText];
   if(!commands.length) continue;

   let sender='',stamp='';
   const m=pre.match(/^\[([^\]]+)\]\s*([^:]+):/);
   if(m){stamp=clean(m[1]);sender=clean(m[2]);}
   if(!sender) sender=direction==='out' ? 'Siz' : 'Kullanıcı';

   let dataNode=row;
   while(dataNode && !dataNode.getAttribute?.('data-id')){
       dataNode=dataNode.parentElement;
   }
   const id=dataNode?.getAttribute?.('data-id') || '';

   commands.forEach((cmd,idx)=>messages.push({
      sender,
      text:clean(cmd),
      stamp,
      pre,
      id:id ? id+':'+idx : direction+':'+stamp+':'+clean(cmd),
      direction
   }));
 }

 return {isOpen:true,messages,count:messages.length};
})()"""

SEND_JS=r"""((message)=>{
  const root=document.querySelector('#main') || document.body;
  const box=
    root.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
    root.querySelector('footer [contenteditable="true"]') ||
    document.querySelector('[contenteditable="true"][role="textbox"]') ||
    document.querySelector('[contenteditable="true"][data-tab]');
  if(!box) return {ok:false,error:'WhatsApp mesaj kutusu bulunamadı'};

  box.focus();
  document.execCommand('selectAll',false,null);
  document.execCommand('insertText',false,String(message));
  box.dispatchEvent(new InputEvent('input',{
      bubbles:true,
      inputType:'insertText',
      data:String(message)
  }));

  const send=
    root.querySelector('button[aria-label="Gönder"]') ||
    root.querySelector('button[aria-label="Send"]') ||
    root.querySelector('[data-testid="send"]')?.closest('button,[role="button"]') ||
    root.querySelector('[data-icon="send"]')?.closest('button,[role="button"]');

  if(send){
    send.click();
    return {ok:true};
  }

  box.dispatchEvent(new KeyboardEvent('keydown',{
      bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13
  }));
  box.dispatchEvent(new KeyboardEvent('keyup',{
      bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13
  }));
  return {ok:true};
})"""

class WhatsAppBot(QObject):
    status=Signal(str)
    log=Signal(str)
    sent=Signal(str,str)

    def __init__(self,view,response_fn,interval_ms=1500):
        super().__init__()
        self.view=view
        self.response_fn=response_fn
        self.group=''
        self.running=False
        self.seen=set()
        self.last_status=''
        self.gate=ActivationGate()
        self.timer=QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.poll)

    def _status(self,text):
        if text!=self.last_status:
            self.last_status=text
            self.status.emit(text)

    def _max_message(self,message):
        text=str(message or '').strip()
        if text.startswith('Max:'):
            return text
        return f'Max: {text}'

    def start(self,group=''):
        self.group=(group or '').strip()
        self.running=True
        self.seen.clear()
        self.gate=ActivationGate()
        self.timer.start()
        self._status('Max okuyucu aktif - açık sohbete #Max başla yazın')
        QTimer.singleShot(400,self.poll)
        return True

    def stop(self):
        self.running=False
        self.gate.active=False
        self.timer.stop()
        self._status('Max durduruldu')

    def poll(self):
        if self.running:
            self.view.page().runJavaScript(POLL_JS,self._polled)

    def _polled(self,result):
        if not self.running:
            return
        result=result or {}
        if not result.get('isOpen'):
            self._status('WhatsApp açık sohbeti bulunamadı')
            return

        if self.gate.active:
            self._status('Max aktif - açık sohbet dinleniyor')
        else:
            self._status('Max okuyucu açık - #Max başla komutu bekleniyor')

        for m in result.get('messages') or []:
            text=(m.get('text') or '').strip()
            sender=(m.get('sender') or ('Siz' if m.get('direction')=='out' else 'Kullanıcı')).strip()
            stamp=(m.get('id') or m.get('stamp') or m.get('pre') or (m.get('direction','')+text)).strip()
            key=command_key(sender,text,stamp)

            if not text or key in self.seen:
                continue
            self.seen.add(key)
            if len(self.seen)>800:
                self.seen=set(list(self.seen)[-400:])

            action,payload=self.gate.handle(text)

            if action=='started':
                self._send(
                    'Merhaba, ben Max. İlan arama konusunda size yardımcı olacağım. '
                    'Komut listesini görmek için #? yazabilirsiniz.',
                    sender
                )
                self._status('Max aktif - açık sohbet dinleniyor')
                continue

            if action=='stopped':
                self._send(
                    'Max ilan arama botu durduruldu. Yeniden başlatmak için #Max başla yazabilirsiniz.',
                    sender
                )
                self._status('Max okuyucu açık - #Max başla komutu bekleniyor')
                continue

            if action!='query':
                continue

            response=self.response_fn(payload)
            if response:
                self._send(response,sender)

    def _send(self,message,sender='WhatsApp'):
        message=self._max_message(message)
        js=SEND_JS+'('+json.dumps(str(message),ensure_ascii=False)+')'
        self.view.page().runJavaScript(
            js,
            lambda r:self._sent_result(r,sender,message)
        )

    def _sent_result(self,result,sender,message):
        if result and result.get('ok'):
            self.sent.emit(sender,message)
        else:
            self._status((result or {}).get('error','Max mesajı gönderemedi'))
