from __future__ import annotations

def _clean(text):
    t=(text or "").strip()
    if t.endswith("#") and t.startswith("#") and len(t)>1:
        t=t[:-1].rstrip()
    return t.casefold()

class ActivationGate:
    START={"#max başla"}
    STOP={"#max dur","#max durdur"}

    def __init__(self):
        self.active=False

    def handle(self,text:str):
        t=_clean(text)
        if t in self.START:
            self.active=True
            return ("started",None)
        if t in self.STOP:
            self.active=False
            return ("stopped",None)
        if not self.active:
            return ("ignore",None)
        if t=="#?" or (len(t)>=2 and t.startswith("#")):
            return ("query",text.strip())
        return ("ignore",None)
