from __future__ import annotations

from collections import deque


AUTO_SCAN_SOURCE_LABELS=("MyRE/MAX ÇARŞI","MyRE/MAX ÇARŞI 2","Emlakjet ÇARŞI")


class AutoScanQueue:
    def __init__(self,sources):
        self.sources=dict(sources)
        self.pending=deque()
        self.current=None
        self.results=[]

    def start(self,labels):
        selected=[]
        for label in labels or []:
            if label in AUTO_SCAN_SOURCE_LABELS and label in self.sources and label not in selected:
                selected.append(label)
        self.pending=deque(selected)
        self.current=None
        self.results=[]

    def next_item(self):
        if self.current is not None or not self.pending:
            return None
        label=self.pending.popleft()
        self.current=(label,self.sources[label])
        return self.current

    def complete(self,success):
        if self.current is None:
            return None
        label,url=self.current
        self.results.append((label,bool(success)))
        self.current=None
        return label,url

    @property
    def finished(self):
        return self.current is None and not self.pending
