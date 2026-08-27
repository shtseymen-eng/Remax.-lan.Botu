from __future__ import annotations
import re, sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

TR=str.maketrans("çÇğĞıİöÖşŞüÜ","ccggiioossuu")

def norm(s:str)->str:
    return re.sub(r"\s+"," ",(s or "").translate(TR).casefold()).strip()

def source_key(url:str)->str:
    p=urlsplit((url or "").strip())
    path=p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),path,"",""))

def source_label(url:str)->str:
    host=urlsplit(url).netloc.lower().split(":")[0]
    host=host.removesuffix(".sahibinden.com")
    if "remax.com.tr" in host and "/carsi-2" in (url or ""): return "RE/MAX ÇARŞI 2"
    if "remax.com.tr" in host and "/carsi" in (url or ""): return "RE/MAX ÇARŞI"
    labels={"carsigayrimenkulkocaeli":"RE/MAX ÇARŞI","remaxcarsi2":"RE/MAX ÇARŞI 2","remax.com.tr":"RE/MAX WEB"}
    if (url or "").startswith("excel://"): return "EXCEL / LİSTE"
    if (url or "").startswith("manual://"): return "MANUEL"
    return labels.get(host,host or url)

@dataclass(frozen=True)
class Listing:
    listing_id:str
    title:str
    url:str
    advisor:str=""
    phone:str=""
    price:str=""
    location:str=""
    rooms:str=""
    transaction_type:str=""
    property_type:str=""
    sqm:str=""
    listing_date:str=""
    source_url:str=""

class DB:
    def __init__(self,path):
        self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def connect(self): return sqlite3.connect(self.path)
    def _init(self):
        with self.connect() as c:
            cols=[r[1] for r in c.execute("pragma table_info(listings)").fetchall()]
            if cols and ("source_url" not in cols or "phone" not in cols): c.execute("alter table listings rename to listings_legacy")
            c.execute("""create table if not exists listings(
                source_url text not null,id text not null,title text not null,url text not null,
                advisor text not null default '',phone text not null default '',price text not null default '',
                location text not null default '',rooms text not null default '',trans text not null default '',
                ptype text not null default '',sqm text not null default '',listing_date text not null default '',
                primary key(source_url,id))""")
            c.execute("create table if not exists meta(k text primary key,v text)")
            legacy=c.execute("select name from sqlite_master where type='table' and name='listings_legacy'").fetchone()
            if legacy:
                oldcols=[r[1] for r in c.execute("pragma table_info(listings_legacy)").fetchall()]
                try:
                    rows=c.execute("select * from listings_legacy").fetchall()
                    for row in rows:
                        d=dict(zip(oldcols,row)); src=d.get('source_url','legacy'); lid=str(d.get('id',d.get('listing_id','')))
                        if not lid: continue
                        c.execute("""insert or ignore into listings
                            (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                            values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                            src,lid,d.get('title',''),d.get('url',''),d.get('advisor',''),d.get('phone',''),
                            d.get('price',''),d.get('location',''),d.get('rooms',''),d.get('trans',d.get('transaction_type','')),
                            d.get('ptype',d.get('property_type','')),d.get('sqm',''),d.get('listing_date','')))
                except Exception: pass
                c.execute("drop table listings_legacy")
    def replace_source(self,source_url,items):
        key=source_key(source_url)
        with self.connect() as c:
            c.execute('begin'); c.execute('delete from listings where source_url=?',(key,))
            c.executemany("""insert into listings
                (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                (key,x.listing_id,x.title,x.url,x.advisor,x.phone,x.price,x.location,x.rooms,x.transaction_type,x.property_type,x.sqm,x.listing_date)
                for x in items]); c.commit()
    def upsert(self,items,default_source="excel://import"):
        with self.connect() as c:
            for x in items:
                key=source_key(x.source_url or default_source)
                c.execute("""insert into listings (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date) values(?,?,?,?,?,?,?,?,?,?,?,?,?) on conflict(source_url,id) do update set title=excluded.title,url=excluded.url,advisor=excluded.advisor,phone=excluded.phone,price=excluded.price,location=excluded.location,rooms=excluded.rooms,trans=excluded.trans,ptype=excluded.ptype,sqm=excluded.sqm,listing_date=excluded.listing_date""",(key,x.listing_id,x.title,x.url,x.advisor,x.phone,x.price,x.location,x.rooms,x.transaction_type,x.property_type,x.sqm,x.listing_date))
    def add_one(self,x): self.upsert([x],x.source_url or "manual://entry")
    def all(self):
        with self.connect() as c:
            rows=c.execute("select id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date,source_url from listings order by title").fetchall()
        return [Listing(*r) for r in rows]
    def source_count(self,source_url):
        with self.connect() as c: return int(c.execute('select count(*) from listings where source_url=?',(source_key(source_url),)).fetchone()[0])
    def count(self):
        with self.connect() as c: return int(c.execute('select count(*) from listings').fetchone()[0])
    def meta(self,k,d='-'):
        with self.connect() as c: r=c.execute('select v from meta where k=?',(k,)).fetchone()
        return r[0] if r else d
    def setmeta(self,k,v):
        with self.connect() as c: c.execute('insert into meta values(?,?) on conflict(k) do update set v=excluded.v',(k,v))

def search(items,query):
    ts=[t for t in norm(query).split() if t]
    if not ts:return items
    out=[]
    for x in items:
        hay=norm(' '.join([x.title,x.advisor,x.phone,x.price,x.location,x.rooms,x.transaction_type,x.property_type,x.sqm,x.listing_date,source_label(x.source_url)]))
        if all(t in hay for t in ts): out.append(x)
    return out
