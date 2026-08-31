from __future__ import annotations
import json
from PySide6.QtCore import QObject,QTimer,Signal
from .whatsapp_logic import command_key
from .whatsapp_state import ActivationGate

# Eski biçim #bot başlat# da ActivationGate tarafından desteklenir.
POLL_JS=r"""(() => {
 const clean=s=>String(s||'').replace(/\s+/g,' ').trim();

 const inputBox=
   document.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
   document.querySelector('footer [contenteditable="true"]') ||
   document.querySelector('div[contenteditable="true"][role="textbox"]');

 let conversationRoot=document.querySelector('#main');

 // WhatsApp zaman zaman #main kimliğini değiştirdiği için açık konuşmayı
 // mesaj kutusundan yukarı doğru bularak yedekliyoruz.
 if(!conversationRoot && inputBox){
   let root=inputBox.closest('footer') || inputBox.parentElement;
   while(root && root!==document.body){
     const count=root.querySelectorAll('.message-in,.message-out,[data-id],[data-pre-plain-text]').length;
     if(count>0){
       conversationRoot=root;
       break;
     }
     root=root.parentElement;
   }
 }

 if(!conversationRoot){
   return {isOpen:false,messages:[],reason:inputBox?'conversation-root-not-found':'message-box-not-found'};
 }

 const messages=[],seenRows=new Set();
 const rows=[
   ...Array.from(conversationRoot.querySelectorAll('.message-in,.message-out')),
   ...Array.from(conversationRoot.querySelectorAll('[data-id]')),
   ...Array.from(conversationRoot.querySelectorAll('[data-pre-plain-text]')).map(x=>x.closest('[data-id],.message-in,.message-out')||x.parentElement)
 ].filter(Boolean);

 for(const row0 of rows.slice(-220)){
   const row=row0.closest?.('.message-in,.message-out,[data-id]')||row0;
   if(!row||seenRows.has(row))continue;
   seenRows.add(row);

   const direction=row.classList?.contains('message-out')?'out':'in';
   const meta=row.querySelector?.('[data-pre-plain-text]');
   const pre=meta?.getAttribute('data-pre-plain-text')||'';

   const copyable=row.querySelector?.('[class*="copyable-text"]');
   let fullText=clean(copyable?.innerText||row.innerText||'');
   if(!fullText)continue;

   let commands=fullText.match(/#[^#\n]+#/g)||[];
   if(!commands.length && fullText.startsWith('#'))commands=[fullText];
   if(!commands.length)continue;

   let sender='',stamp='';
   const m=pre.match(/^\[([^\]]+)\]\s*([^:]+):/);
   if(m){stamp=clean(m[1]);sender=clean(m[2]);}
   if(!sender)sender=direction==='out'?'Siz':'Kullanıcı';

   const id=row.getAttribute?.('data-id')||row.closest?.('[data-id]')?.getAttribute('data-id')||'';
   commands.forEach((cmd,idx)=>messages.push({
     sender,
     text:clean(cmd),
     stamp,
     pre,
     id:id?id+':'+idx:'',
     direction
   }));
 }

 return {isOpen:true,messages};
})()"""
SEND_JS=r"""((message)=>{const main=document.querySelector('#main');if(!main)return {ok:false,error:'Açık WhatsApp sohbeti bulunamadı'};const box=main.querySelector('footer div[contenteditable="true"][role="textbox"]')||main.querySelector('footer [contenteditable="true"]')||main.querySelector('div[contenteditable="true"][role="textbox"]');if(!box)return {ok:false,error:'Mesaj kutusu bulunamadı'};box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,String(message));box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:String(message)}));const send=main.querySelector('button[aria-label="Gönder"],button[aria-label="Send"],[data-testid="send"],[data-icon="send"]')?.closest('button,[role="button"]')||main.querySelector('button[aria-label="Gönder"],button[aria-label="Send"],[data-testid="send"]');if(send){send.click();return {ok:true};}box.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));box.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,cancelable:true,key:'Enter',code:'Enter',keyCode:13,which:13}));return {ok:true};})"""
class WhatsAppBot(QObject):
    status=Signal(str); log=Signal(str); sent=Signal(str,str)
    def __init__(self,view,response_fn,interval_ms=2200):
        super().__init__(); self.view=view; self.response_fn=response_fn; self.group=''; self.running=False; self.seen=set(); self.last_status=''; self.gate=ActivationGate(); self.timer=QTimer(self); self.timer.setInterval(interval_ms); self.timer.timeout.connect(self.poll)
    def _status(self,text):
        if text!=self.last_status:self.last_status=text; self.status.emit(text)
    def start(self,group=''):
        self.group=(group or '').strip(); self.running=True; self.seen.clear(); self.gate=ActivationGate(); self.timer.start(); self._status('Aktif - uygulama içi WhatsApp açık sohbetinde #bot başlat bekleniyor'); QTimer.singleShot(500,self.poll); return True
    def stop(self):self.running=False; self.gate.active=False; self.timer.stop(); self._status('Durduruldu')
    def poll(self):
        if self.running:self.view.page().runJavaScript(POLL_JS,self._polled)
    def _polled(self,result):
        if not self.running:return
        result=result or {}
        if not result.get('isOpen'):self._status('WhatsApp açık - uygulama içinden bir sohbet açın'); return
        self._status('Dinleniyor: uygulama içi WhatsApp açık sohbeti')
        for m in result.get('messages') or []:
            text=(m.get('text') or '').strip(); sender=(m.get('sender') or ('Siz' if m.get('direction')=='out' else 'Kullanıcı')).strip(); stamp=(m.get('id') or m.get('stamp') or m.get('pre') or (m.get('direction','')+text)).strip(); key=command_key(sender,text,stamp)
            if not text or key in self.seen:continue
            self.seen.add(key); action,payload=self.gate.handle(text)
            if action=='started':self._send('RE/MAX ilan botu aktif. Komut listesi için #? yazın.',sender); self._status('Aktif - ilan komutları dinleniyor'); continue
            if action=='stopped':self._send('RE/MAX ilan botu durduruldu. Yeniden başlatmak için #bot başlat yazın.',sender); self._status('Bağlandı - #bot başlat komutu bekleniyor'); continue
            if action!='query':continue
            response=self.response_fn(payload)
            if response:self._send(response,sender)
    def _send(self,message,sender='WhatsApp'):
        js=SEND_JS+'('+json.dumps(str(message),ensure_ascii=False)+')'; self.view.page().runJavaScript(js,lambda r:self._sent_result(r,sender,message))
    def _sent_result(self,result,sender,message):
        if result and result.get('ok'):self.sent.emit(sender,message)
        else:self._status((result or {}).get('error','WhatsApp mesajı gönderilemedi'))
