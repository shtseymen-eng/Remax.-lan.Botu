from __future__ import annotations

class ActivationGate:
    START = {"#bot başlat#", "#bot baslat#"}
    STOP = {"#bot durdur#"}
    def __init__(self):
        self.active=False
    def handle(self,text:str):
        t=(text or '').strip().lower()
        if t in self.START:
            self.active=True
            return ("started", None)
        if t in self.STOP:
            self.active=False
            return ("stopped", None)
        if not self.active:
            return ("ignore", None)
        if t == '#?' or (len(t)>=3 and t.startswith('#') and t.endswith('#')):
            return ("query", text.strip())
        return ("ignore", None)
