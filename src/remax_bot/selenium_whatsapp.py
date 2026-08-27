from __future__ import annotations
import os, sys, time, threading, subprocess, tempfile
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .whatsapp_state import ActivationGate

READ_JS = r"""
const out=[];
const rows=[...document.querySelectorAll('[data-testid="msg-container"], .message-in, .message-out')];
rows.slice(-60).forEach((el,idx)=>{
  const parent=el.closest('[data-id],.message-in,.message-out') || el;
  const dir=(parent.classList && parent.classList.contains('message-out')) ? 'out' : 'in';
  let text='';
  for(const sel of ['[data-testid="msg-text"]','span.selectable-text.copyable-text','span[class*="selectable-text"]','div[class*="copyable-text"] span[dir]']){
    const n=el.querySelector(sel) || parent.querySelector(sel);
    if(n && n.innerText){ text=n.innerText.trim(); break; }
  }
  if(!text) text=(el.innerText||'').trim();
  const c=(el.querySelector('[data-pre-plain-text]') || parent.querySelector('[data-pre-plain-text]'));
  const pre=c ? (c.getAttribute('data-pre-plain-text')||'') : '';
  let sender=dir==='out' ? 'Siz' : 'Kullanıcı';
  const m=pre.match(/] (.+?):\s*$/); if(m) sender=m[1].trim();
  const did=(parent.getAttribute('data-id')||el.getAttribute('data-id')||'');
  const id=did || (pre+'::'+text+'::'+idx);
  if(text) out.push({id,text,sender,direction:dir});
});
return out;
"""

class SeleniumWhatsAppBot(QObject):
    status=Signal(str)
    log=Signal(str)
    sent=Signal(str,str)

    def __init__(self, profile_dir: Path, response_fn):
        super().__init__()
        self.profile_dir=Path(profile_dir)
        self.profile_dir.mkdir(parents=True,exist_ok=True)
        self.response_fn=response_fn
        self.group=''
        self.running=False
        self.driver=None
        self.thread=None
        self.seen=set()
        self.gate=ActivationGate()
        self.started_at=0.0

    def start(self, group=''):
        if self.running:
            self.status.emit('WhatsApp botu zaten açık')
            return True
        self.group=(group or '').strip()
        self.running=True
        self.gate=ActivationGate()
        self.seen.clear()
        self.started_at=time.time()
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()
        self.status.emit('Chrome WhatsApp başlatılıyor...')
        return True

    def stop(self):
        self.running=False
        self.gate.active=False
        try:
            if self.driver: self.driver.quit()
        except Exception: pass
        self.driver=None
        self.status.emit('Durduruldu')

    def _run(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            opts=Options()
            opts.add_argument(f'--user-data-dir={self.profile_dir}')
            opts.add_argument('--profile-directory=RemaxBot')
            opts.add_argument('--no-first-run')
            opts.add_argument('--no-default-browser-check')
            opts.add_argument('--disable-notifications')
            opts.add_argument('--disable-popup-blocking')
            opts.add_argument('--disable-background-timer-throttling')
            opts.add_argument('--disable-backgrounding-occluded-windows')
            opts.add_argument('--disable-renderer-backgrounding')
            opts.add_experimental_option('excludeSwitches',['enable-automation'])
            opts.add_experimental_option('useAutomationExtension',False)
            self.driver=webdriver.Chrome(options=opts)
            self.driver.get('https://web.whatsapp.com')
            self.status.emit('WhatsApp QR / giriş bekleniyor')
            WebDriverWait(self.driver,180).until(lambda d: d.execute_script(
                "return document.querySelector('[data-testid=\"chat-list\"],[aria-label*=\"Sohbet\"],[aria-label*=\"Chat\"]')!==null"))
            self.status.emit('WhatsApp bağlandı')
            if self.group:
                self._open_group(self.group)
            self._prime_seen()
            self.status.emit('Bağlandı - #bot başlat# komutu bekleniyor')
            while self.running:
                self._poll_once()
                time.sleep(2.0)
        except Exception as e:
            self.status.emit('WhatsApp hata: '+str(e)[:120])
            self.log.emit(str(e))
            self.running=False
        finally:
            if not self.running:
                try:
                    if self.driver: self.driver.quit()
                except Exception: pass
                self.driver=None

    def _open_group(self, group):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        try:
            box=None
            for sel in ['[data-testid="chat-list-search"]','[aria-label="Sohbet veya kişi ara"]','[aria-label="Search or start new chat"]']:
                try:
                    box=WebDriverWait(self.driver,4).until(EC.presence_of_element_located((By.CSS_SELECTOR,sel))); break
                except Exception: pass
            if box:
                box.click(); time.sleep(.3)
                try: box.clear()
                except Exception: pass
                box.send_keys(group); time.sleep(1.5)
                for sel in [f'[title="{group}"]','[data-testid="cell-frame-container"]','div[role="listitem"]']:
                    try:
                        el=WebDriverWait(self.driver,4).until(EC.element_to_be_clickable((By.CSS_SELECTOR,sel)))
                        el.click(); time.sleep(1); return
                    except Exception: pass
        except Exception: pass
        self.status.emit('Grubu manuel açın; bot açık sohbeti dinleyecek')

    def _prime_seen(self):
        try:
            for m in self.driver.execute_script(READ_JS) or []:
                if m.get('id'): self.seen.add(m['id'])
        except Exception: pass

    def _poll_once(self):
        if not self.driver: return
        msgs=self.driver.execute_script(READ_JS) or []
        for m in msgs:
            mid=str(m.get('id') or '')
            text=str(m.get('text') or '').strip()
            if not mid or mid in self.seen or not text: continue
            self.seen.add(mid)
            action,payload=self.gate.handle(text)
            if action=='started':
                self._send('RE/MAX ilan botu aktif. Komut listesi için #? yazın.')
                self.status.emit('Aktif - ilan komutları dinleniyor')
                continue
            if action=='stopped':
                self._send('RE/MAX ilan botu sorgu modu durduruldu. Yeniden başlatmak için #bot başlat# yazın.')
                self.status.emit('Bağlandı - #bot başlat# komutu bekleniyor')
                continue
            if action!='query': continue
            response=self.response_fn(payload)
            if response:
                self._send(response)

    def _clipboard_set(self,text):
        try:
            if sys.platform=='darwin':
                subprocess.run(['pbcopy'],input=text,text=True,check=True); return True
            if os.name=='nt':
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',suffix='.txt',delete=False) as f:
                    f.write(text); p=f.name
                subprocess.run(['powershell','-NoProfile','-Command',f'[System.IO.File]::ReadAllText("{p}",[System.Text.Encoding]::UTF8) | Set-Clipboard'],check=True,capture_output=True)
                os.unlink(p); return True
            subprocess.run(['xclip','-selection','clipboard'],input=text,text=True,check=True); return True
        except Exception: return False

    def _send(self,text):
        if not text or not self.driver: return False
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            box=None
            for sel in ['[data-testid="conversation-compose-box-input"]','div[contenteditable="true"][data-tab="10"]','footer div[contenteditable="true"]','div[role="textbox"][contenteditable="true"]']:
                try:
                    cand=WebDriverWait(self.driver,3).until(EC.element_to_be_clickable((By.CSS_SELECTOR,sel)))
                    aria=(cand.get_attribute('aria-label') or '').lower()
                    if 'ara' in aria or 'search' in aria: continue
                    box=cand; break
                except Exception: pass
            if not box: return False
            box.click(); time.sleep(.15)
            if self._clipboard_set(text):
                box.send_keys((Keys.COMMAND if sys.platform=='darwin' else Keys.CONTROL)+'v')
            else:
                self.driver.execute_script("arguments[0].focus();document.execCommand('insertText',false,arguments[1]);",box,text)
            time.sleep(.25)
            for sel in ['[data-testid="send"]','[data-testid="compose-btn-send"]','button[aria-label="Gönder"]','button[aria-label="Send"]']:
                try:
                    WebDriverWait(self.driver,2).until(EC.element_to_be_clickable((By.CSS_SELECTOR,sel))).click()
                    self.sent.emit('WhatsApp',text); return True
                except Exception: pass
            box.send_keys(Keys.ENTER)
            self.sent.emit('WhatsApp',text); return True
        except Exception as e:
            self.log.emit(str(e)); return False
