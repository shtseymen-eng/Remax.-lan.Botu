from __future__ import annotations
import csv, re
from pathlib import Path
from .core import Listing, norm

FIELD_ALIASES={
 "listing_id":["ilan no","ilan numarasi","portfoy no","portfoy numarasi","id"],
 "advisor":["danisman","danisman adi","ilan sahibi","temsilci"],
 "phone":["telefon","cep telefonu","danisman telefonu","gsm"],
 "title":["baslik","ilan basligi","portfoy basligi","aciklama"],
 "price":["fiyat","ilan fiyati","bedel"],
 "location":["bolge","konum","lokasyon","il ilce mahalle","adres"],
 "rooms":["oda","oda sayisi"],
 "transaction_type":["satilik kiralik","islem tipi","durum","ilan tipi"],
 "property_type":["emlak turu","gayrimenkul turu","kategori","tip"],
 "sqm":["m2","metrekare","brut m2","net m2"],
 "listing_date":["ilan tarihi","tarih","yayin tarihi"],
 "url":["ilan linki","link","url","portfoy linki"],
 "source_url":["kaynak","ofis","kaynak linki"]
}
def _h(s): return norm(str(s or "")).replace("²","2")
def _map_headers(headers):
    out={}; nh={_h(h):h for h in headers if h is not None}
    for field,aliases in FIELD_ALIASES.items():
        for a in aliases:
            if _h(a) in nh: out[field]=nh[_h(a)]; break
    return out
def _row_to_listing(row,mapping,default_source="excel://import"):
    g=lambda f: str(row.get(mapping.get(f,""),"") or "").strip()
    url=g("url"); lid=g("listing_id")
    if not lid:
        m=re.search(r"(?:P)?(\d{5,})",url); lid=m.group(1) if m else str(abs(hash((g("title"),url,g("advisor")))))
    src=g("source_url") or default_source
    return Listing(lid,g("title") or f"İlan {lid}",url,g("advisor"),g("phone"),g("price"),g("location"),g("rooms"),g("transaction_type"),g("property_type"),g("sqm"),g("listing_date"),src)
def read_list_file(path):
    path=Path(path); ext=path.suffix.lower(); rows=[]
    if ext==".csv":
        raw=path.read_text(encoding="utf-8-sig",errors="replace")
        try: dialect=csv.Sniffer().sniff(raw[:4096],delimiters=";,\t,")
        except: dialect=csv.excel
        rows=list(csv.DictReader(raw.splitlines(),dialect=dialect))
    elif ext==".xlsx":
        from openpyxl import load_workbook
        wb=load_workbook(path,read_only=True,data_only=True); ws=wb.active; vals=ws.iter_rows(values_only=True)
        headers=[str(x or "").strip() for x in next(vals,[])]; rows=[dict(zip(headers,r)) for r in vals]
    else: raise ValueError("Yalnızca .xlsx ve .csv destekleniyor.")
    if not rows:return []
    mapping=_map_headers(rows[0].keys())
    if "title" not in mapping and "url" not in mapping: raise ValueError("Başlık veya İlan Linki sütunu bulunamadı.")
    return [_row_to_listing(r,mapping) for r in rows if any(str(v or "").strip() for v in r.values())]
def price_number(s):
    digits=re.sub(r"[^0-9]","",str(s or "")); return int(digits) if digits else None
def command_help():
    return """RE/MAX ÇARŞI İLAN BOTU KOMUTLARI

#bot başlat#
WhatsApp ilan sorgu modunu aktif eder.

#bot durdur#
WhatsApp ilan sorgu modunu durdurur.

#?
Komut listesini gösterir.

#danışmanlar#
Tüm danışmanları mevcut ilan adetleriyle listeler.

#yahya kaptan kiralık 3+1#
Uygun ilanları danışman bazında sayar.

#yahya kaptan kiralık 3+1 link#
Uygun ilanların linklerini danışman adıyla gönderir.

#izmit satılık daire 2+1#
Bölge + satış tipi + emlak türü + oda ile arar.

#izmit kiralık 50000#
50.000 TL ve altındaki uygun ilanları önceliklendirir; yoksa en yakın fiyatı getirir.

#danışman ayşe#
Danışman adına göre ilanları bulur.

Bot yalnızca başı ve sonu # olan komutları işler. Normal grup konuşmalarına cevap vermez."""
def parse_command(text):
    t=(text or "").strip()
    if t=="#?": return {"type":"help"}
    if len(t)<3 or not (t.startswith("#") and t.endswith("#")): return {"type":"ignore"}
    body=t[1:-1].strip()
    if norm(body)=="danismanlar":
        return {"type":"advisors"}
    link=bool(re.search(r"\blink\b",norm(body))); body=re.sub(r"(?i)\blink\b"," ",body).strip()
    m=re.match(r"(?i)danışman\s+(.+)$",body)
    if not m:
        m=re.match(r"(?i)danisman\s+(.+)$",norm(body))
    if m:return {"type":"search","query":m.group(1).strip(),"links":link,"advisor_only":True}
    nums=re.findall(r"(?<![+\d])(\d{4,9})(?![+\d])",body); target=int(nums[-1]) if nums else None
    if target: body=re.sub(r"(?<![+\d])"+re.escape(nums[-1])+r"(?![+\d])"," ",body).strip()
    return {"type":"search","query":body,"links":link,"target_price":target}
def command_response(items,text,limit=12):
    from .core import search
    cmd=parse_command(text)
    if cmd["type"]=="ignore":return None
    if cmd["type"]=="help":return command_help()
    if cmd["type"]=="advisors":
        by={}
        unspecified="Danışman belirtilmemiş"
        for x in items:
            name=(x.advisor or "").strip() or unspecified
            by[name]=by.get(name,0)+1
        if not by:
            return "İlan havuzunda danışman bilgisi bulunamadı."
        named_count=sum(1 for k in by if k != unspecified)
        lines=["DANIŞMAN İLAN DAĞILIMI",""]
        lines += [f"{k}: {v} ilan" for k,v in sorted(by.items(),key=lambda kv:(-kv[1],norm(kv[0])))]
        lines += ["",f"Toplam ilan: {len(items)}",f"Toplam danışman: {named_count}"]
        return "\n".join(lines)
    matches=search(items,cmd.get("query","")); target=cmd.get("target_price")
    if target:
        priced=[(price_number(x.price),x) for x in matches]; priced=[p for p in priced if p[0] is not None]; under=[p for p in priced if p[0]<=target]
        if under: matches=[x for _,x in sorted(under,key=lambda p:p[0],reverse=True)[:limit]]
        elif priced: matches=[min(priced,key=lambda p:abs(p[0]-target))[1]]
    if not matches:return "Aramanıza uygun ilan bulunamadı."
    if cmd.get("links"):
        lines=[f"{len(matches)} uygun ilan bulundu:"]
        for x in matches[:limit]: lines += ["",x.title,f"{x.price} | {x.location}",f"Danışman: {x.advisor or 'Belirtilmemiş'}",x.url or "(link yok)"]
        return "\n".join(lines)
    by={}
    for x in matches: by[x.advisor or "Danışman belirtilmemiş"]=by.get(x.advisor or "Danışman belirtilmemiş",0)+1
    return "\n".join([f"{len(matches)} uygun ilan bulundu:"]+[f"{k}: {v} ilan" for k,v in sorted(by.items(),key=lambda kv:(-kv[1],kv[0]))]+["","Linkleri görmek için aynı komuta link ekleyin."])
