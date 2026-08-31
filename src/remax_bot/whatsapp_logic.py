from __future__ import annotations
import hashlib

def should_process(text: str) -> bool:
    t=(text or "").strip()
    return t=="#?" or (len(t)>=2 and t.startswith("#"))

def decorate_response(sender: str, response: str) -> str:
    sender=(sender or "Kullanıcı").strip()
    return f"{sender} için sonuçlar:\n{response}"

def command_key(sender: str, text: str, stamp: str) -> str:
    raw=f"{sender}\n{text}\n{stamp}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()
