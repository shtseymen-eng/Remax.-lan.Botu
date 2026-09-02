from __future__ import annotations
import re, sqlite3
from dataclasses import dataclass,replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

TR=str.maketrans("çÇğĞıİöÖşŞüÜ","ccggiioossuu")

def norm(s:str)->str:
    return re.sub(r"\s+"," ",(s or "").translate(TR).casefold()).strip()

def source_key(url:str)->str:
    p=urlsplit((url or "").strip())
    path=p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),path,"",""))

def source_site(source_url:str,listing_url:str="")->str:
    for value in (source_url,listing_url):
        host=urlsplit((value or "").strip()).netloc.lower().split(":")[0]
        if host=="remax.com.tr" or host.endswith(".remax.com.tr"):
            return "MyRE/MAX"
        if host=="emlakjet.com" or host.endswith(".emlakjet.com"):
            return "Emlakjet"
        if host=="sahibinden.com" or host.endswith(".sahibinden.com"):
            return "Sahibinden"
    return "Diğer"

def source_label(url:str)->str:
    host=urlsplit(url).netloc.lower().split(":")[0]
    if (host=="remax.com.tr" or host.endswith(".remax.com.tr")) and "/carsi-2" in (url or ""): return "MyRE/MAX ÇARŞI 2"
    if host=="remax.com.tr" or host.endswith(".remax.com.tr"): return "MyRE/MAX ÇARŞI"
    if host=="emlakjet.com" or host.endswith(".emlakjet.com"): return "Emlakjet ÇARŞI"
    labels={
        "carsigayrimenkulkocaeli.sahibinden.com":"Sahibinden ÇARŞI",
        "remaxcarsi2.sahibinden.com":"Sahibinden ÇARŞI 2",
    }
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

def listing_identity(item:Listing)->str:
    if (item.url or "").strip():
        return source_key(item.url)
    return str(item.listing_id or "").strip()

def update_listing_fields(item:Listing,values:dict)->Listing:
    editable={
        "listing_id","title","url","advisor","phone","price","location","rooms",
        "transaction_type","property_type","sqm","listing_date","source_url",
    }
    changes={
        key:" ".join(str(value or "").split())
        for key,value in values.items() if key in editable
    }
    updated=replace(item,**changes)
    if not updated.listing_id:
        updated=replace(updated,listing_id=item.listing_id)
    if not updated.title:
        updated=replace(updated,title=item.title or f"İlan {updated.listing_id}")
    if not updated.source_url:
        updated=replace(updated,source_url=item.source_url or "manual://entry")
    return updated

def split_listings_by_site(items)->dict[str,list[Listing]]:
    buckets={"Sahibinden":[],"Emlakjet":[],"MyRE/MAX":[],"Diğer":[]}
    for item in items:
        buckets[source_site(item.source_url,item.url)].append(item)
    return buckets

class DB:
    def __init__(self,path):
        self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True); self._init()

    def connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self.connect() as c:
            cols=[r[1] for r in c.execute("pragma table_info(listings)").fetchall()]
            if cols and ("source_url" not in cols or "phone" not in cols):
                c.execute("alter table listings rename to listings_legacy")
            c.execute("""create table if not exists listings(
                source_url text not null,id text not null,title text not null,url text not null,
                advisor text not null default '',phone text not null default '',price text not null default '',
                location text not null default '',rooms text not null default '',trans text not null default '',
                ptype text not null default '',sqm text not null default '',listing_date text not null default '',
                primary key(source_url,id))""")
            c.execute("create table if not exists meta(k text primary key,v text)")
            c.execute("""create table if not exists advisor_aliases(
                alias_key text primary key,alias_name text not null,canonical_name text not null
            )""")
            legacy=c.execute("select name from sqlite_master where type='table' and name='listings_legacy'").fetchone()
            if legacy:
                oldcols=[r[1] for r in c.execute("pragma table_info(listings_legacy)").fetchall()]
                try:
                    rows=c.execute("select * from listings_legacy").fetchall()
                    for row in rows:
                        d=dict(zip(oldcols,row))
                        src=d.get('source_url','legacy')
                        lid=str(d.get('id',d.get('listing_id','')))
                        if not lid: continue
                        c.execute("""insert or ignore into listings
                            (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                            values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                            src,lid,d.get('title',''),d.get('url',''),d.get('advisor',''),d.get('phone',''),
                            d.get('price',''),d.get('location',''),d.get('rooms',''),
                            d.get('trans',d.get('transaction_type','')),
                            d.get('ptype',d.get('property_type','')),d.get('sqm',''),d.get('listing_date','')))
                except Exception:
                    pass
                c.execute("drop table listings_legacy")

    def replace_source(self,source_url,items):
        key=source_key(source_url)
        with self.connect() as c:
            c.execute('begin')
            c.execute('delete from listings where source_url=?',(key,))
            c.executemany("""insert into listings
                (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                (key,x.listing_id,x.title,x.url,x.advisor,x.phone,x.price,x.location,x.rooms,
                 x.transaction_type,x.property_type,x.sqm,x.listing_date)
                for x in items])
            c.commit()

    def upsert(self,items,default_source="excel://import"):
        with self.connect() as c:
            for x in items:
                key=source_key(x.source_url or default_source)
                c.execute("""insert into listings
                    (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                    values(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    on conflict(source_url,id) do update set
                    title=excluded.title,url=excluded.url,advisor=excluded.advisor,phone=excluded.phone,
                    price=excluded.price,location=excluded.location,rooms=excluded.rooms,trans=excluded.trans,
                    ptype=excluded.ptype,sqm=excluded.sqm,listing_date=excluded.listing_date""",
                    (key,x.listing_id,x.title,x.url,x.advisor,x.phone,x.price,x.location,x.rooms,
                     x.transaction_type,x.property_type,x.sqm,x.listing_date))

    def add_one(self,x):
        self.upsert([x],x.source_url or "manual://entry")

    def update_listing(self,original_source,original_id,item):
        new_source=source_key(item.source_url or original_source or "manual://entry")
        original_key=(source_key(original_source),str(original_id))
        destination_key=(new_source,str(item.listing_id))
        with self.connect() as c:
            if destination_key != original_key and c.execute(
                "select 1 from listings where source_url=? and id=?",destination_key
            ).fetchone():
                raise ValueError("Bu kaynak ve ilan numarasıyla başka bir ilan zaten kayıtlı.")
            c.execute("delete from listings where source_url=? and id=?",original_key)
            c.execute("""insert into listings
                (source_url,id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                new_source,item.listing_id,item.title,item.url,item.advisor,item.phone,item.price,
                item.location,item.rooms,item.transaction_type,item.property_type,item.sqm,item.listing_date,
            ))

    def raw_listing(self,source_url,listing_id):
        with self.connect() as c:
            row=c.execute("""select id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date,source_url
                from listings where source_url=? and id=?""",(
                source_key(source_url),str(listing_id),
            )).fetchone()
        return Listing(*row) if row else None

    @staticmethod
    def _resolve_advisor(name,mapping):
        current=" ".join(str(name or "").split())
        seen=set()
        while current and norm(current) in mapping and norm(current) not in seen:
            key=norm(current); seen.add(key)
            target=mapping[key]
            if norm(target)==key:
                return target
            current=target
        return current

    def _advisor_alias_map(self):
        with self.connect() as c:
            rows=c.execute("select alias_key,canonical_name from advisor_aliases").fetchall()
        return dict(rows)

    def merge_advisors(self,names,canonical_name):
        canonical=" ".join(str(canonical_name or "").split())
        aliases={norm(name):" ".join(str(name or "").split()) for name in names if norm(name)}
        if not canonical or not aliases:
            raise ValueError("Birleştirilecek danışmanlar ve kullanılacak isim gereklidir.")
        aliases.setdefault(norm(canonical),canonical)
        with self.connect() as c:
            c.executemany("""insert into advisor_aliases(alias_key,alias_name,canonical_name)
                values(?,?,?) on conflict(alias_key) do update set
                alias_name=excluded.alias_name,canonical_name=excluded.canonical_name""",[
                (key,name,canonical) for key,name in aliases.items()
            ])

    def unmerge_advisor(self,canonical_name):
        target=norm(canonical_name)
        mapping=self._advisor_alias_map()
        with self.connect() as c:
            rows=c.execute("select alias_key,alias_name from advisor_aliases").fetchall()
            keys=[key for key,name in rows if norm(self._resolve_advisor(name,mapping))==target]
            c.executemany("delete from advisor_aliases where alias_key=?",[(key,) for key in keys])

    def raw_advisor_names(self):
        with self.connect() as c:
            rows=c.execute("select distinct advisor from listings where trim(advisor)<>''").fetchall()
        return sorted((row[0] for row in rows),key=norm)

    def advisor_aliases(self):
        mapping=self._advisor_alias_map()
        with self.connect() as c:
            rows=c.execute("select alias_name from advisor_aliases").fetchall()
        return sorted(
            ((name,self._resolve_advisor(name,mapping)) for (name,) in rows),
            key=lambda pair:(norm(pair[1]),norm(pair[0])),
        )

    def all(self):
        with self.connect() as c:
            rows=c.execute("""select id,title,url,advisor,phone,price,location,rooms,trans,ptype,sqm,listing_date,source_url
                              from listings order by title""").fetchall()
        mapping=self._advisor_alias_map()
        return [
            replace(item,advisor=self._resolve_advisor(item.advisor,mapping))
            for item in (Listing(*r) for r in rows)
        ]

    def source_count(self,source_url):
        with self.connect() as c:
            return int(c.execute('select count(*) from listings where source_url=?',(source_key(source_url),)).fetchone()[0])

    def count(self):
        with self.connect() as c:
            return int(c.execute('select count(*) from listings').fetchone()[0])

    def meta(self,k,d='-'):
        with self.connect() as c:
            r=c.execute('select v from meta where k=?',(k,)).fetchone()
        return r[0] if r else d

    def setmeta(self,k,v):
        with self.connect() as c:
            c.execute('insert into meta values(?,?) on conflict(k) do update set v=excluded.v',(k,v))

def search(items,query):
    tokens=[token for token in norm(query).split() if token]
    groups=[]
    for token in tokens:
        if re.fullmatch(r"[a-z]+(?:-[a-z]+)+",token):
            groups.append(token.split("-"))
        else:
            groups.append([token])
    if not groups:
        return items
    out=[]
    for x in items:
        hay=norm(' '.join([
            x.title,x.advisor,x.phone,x.price,x.location,x.rooms,
            x.transaction_type,x.property_type,x.sqm,x.listing_date,source_label(x.source_url)
        ]))
        matches=lambda term:bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",hay))
        if all(any(matches(term) for term in alternatives) for alternatives in groups):
            out.append(x)
    return out
