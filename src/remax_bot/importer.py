from __future__ import annotations
import csv, re
from pathlib import Path
from .core import Listing, norm, source_site, listing_identity
from .listing_details import details_text, display_address, normalize_details
from .settings_schema import (
    DEFAULT_SEARCH_FIELDS,
    DEFAULT_SEARCH_SOURCES,
    normalize_command_prefix,
    normalize_search_fields,
    normalize_search_sources,
)

FIELD_ALIASES={
 "listing_id":["ilan no","ilan numarasi","portfoy no","portfoy numarasi","id"],
 "advisor":["danisman","danisman adi","ilan sahibi","temsilci"],
 "phone":["telefon","cep telefonu","danisman telefonu","gsm"],
 "title":["baslik","ilan basligi","portfoy basligi","aciklama"],
 "price":["fiyat","ilan fiyati","bedel"],
 "location":["bolge","konum","lokasyon","il ilce mahalle"],
 "rooms":["oda","oda sayisi"],
 "transaction_type":["satilik kiralik","islem tipi","durum","ilan tipi"],
 "property_type":["emlak turu","gayrimenkul turu","kategori","tip"],
 "sqm":["m2","metrekare","brut m2"],
 "net_sqm":["net m2","net metrekare"],
 "listing_date":["ilan tarihi","tarih","yayin tarihi"],
 "url":["ilan linki","link","url","portfoy linki"],
 "source_url":["kaynak","ofis","kaynak linki"],
 "province":["il","sehir"],
 "district":["ilce"],
 "neighborhood":["mahalle","semt"],
 "street":["sokak/cadde","sokak cadde","sokak","cadde"],
 "complex_name":["site/proje","site proje","site adi","proje adi"],
 "full_address":["acik adres","tam adres","adres"],
 "description":["ilan aciklamasi","detayli aciklama"],
}
FIXED_EXPORT_FIELDS=[
    ("listing_id","İlan No"),("title","Başlık"),("advisor","Danışman"),("phone","Telefon"),
    ("price","Fiyat"),("location","Bölge"),("province","İl"),("district","İlçe"),
    ("neighborhood","Mahalle"),("street","Sokak/Cadde"),("complex_name","Site/Proje"),
    ("full_address","Açık Adres"),("rooms","Oda"),("transaction_type","Satılık Kiralık"),
    ("property_type","Emlak Türü"),("sqm","Brüt m²"),("net_sqm","Net m²"),
    ("listing_date","İlan Tarihi"),("description","İlan Açıklaması"),("url","İlan Linki"),
    ("source_url","Kaynak"),
]
COMMON_DETAIL_HEADERS=[
    "Bina Yaşı","Bulunduğu Kat","Kat Sayısı","Isıtma","Banyo Sayısı","Balkon","Eşyalı",
    "Kullanım Durumu","Site İçerisinde","Aidat","Tapu Durumu","Krediye Uygun","Takas",
    "Cephe","Otopark","Asansör",
]
NOISE_ADVISOR_TOKENS={
    "portfoy","konum","kocaeli","izmit","detayli","gayrimen","re/max","remax",
    "satilik","kiralik","telefon","iletisim","ada","parsel","mahalle","ilce",
    "fiyat","aciklama","m2","metrekare","ilan no","ilan numarasi",
    "portfoy no","portfoy numarasi","yetki belgesi","tum ilanlari"
}
LINK_SOURCES=("Sahibinden","Emlakjet","MyRE/MAX")
COMMAND_SOURCE_PREFIXES={
    "sahibinden":"Sahibinden",
    "emlakjet":"Emlakjet",
    "myremax":"MyRE/MAX",
    "myre/max":"MyRE/MAX",
}
def _h(s): return norm(str(s or "")).replace("²","2")
def _map_headers(headers):
    out={}; nh={_h(h):h for h in headers if h is not None}
    for field,aliases in FIELD_ALIASES.items():
        for a in aliases:
            if _h(a) in nh:
                out[field]=nh[_h(a)]; break
    return out
def _row_to_listing(row,mapping,default_source="excel://import"):
    g=lambda f: str(row.get(mapping.get(f,""),"") or "").strip()
    url=g("url"); lid=g("listing_id")
    if not lid:
        m=re.search(r"(?:P)?(\d{5,})",url)
        lid=m.group(1) if m else str(abs(hash((g("title"),url,g("advisor")))))
    src=g("source_url") or default_source
    mapped_headers=set(mapping.values())
    details=normalize_details({
        str(header):value for header,value in row.items()
        if header not in mapped_headers and str(header or "").strip() and str(value or "").strip()
    })
    return Listing(
        listing_id=lid,title=g("title") or f"İlan {lid}",url=url,advisor=g("advisor"),
        phone=g("phone"),price=g("price"),location=g("location"),rooms=g("rooms"),
        transaction_type=g("transaction_type"),property_type=g("property_type"),sqm=g("sqm"),
        listing_date=g("listing_date"),source_url=src,province=g("province"),district=g("district"),
        neighborhood=g("neighborhood"),street=g("street"),complex_name=g("complex_name"),
        full_address=g("full_address"),description=g("description"),net_sqm=g("net_sqm"),details=details,
    )
def read_list_file(path):
    path=Path(path); ext=path.suffix.lower(); rows=[]
    if ext==".csv":
        raw=path.read_text(encoding="utf-8-sig",errors="replace")
        try: dialect=csv.Sniffer().sniff(raw[:4096],delimiters=";,\t,")
        except Exception: dialect=csv.excel
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

def _export_headers(items):
    fixed=[header for _field,header in FIXED_EXPORT_FIELDS]
    fixed_keys={_h(header) for header in fixed}
    dynamic=sorted({
        key for item in items for key in normalize_details(item.details)
        if _h(key) not in fixed_keys
    },key=lambda value:_h(value))
    return fixed+dynamic

def _export_row(item,headers):
    row={header:getattr(item,field) for field,header in FIXED_EXPORT_FIELDS}
    row.update(normalize_details(item.details))
    return [row.get(header,"") for header in headers]

def _style_xlsx_headers(ws,headers):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill
    from openpyxl.utils import get_column_letter

    for cell in ws[1]:
        cell.font=Font(color="FFFFFF",bold=True)
        cell.fill=PatternFill("solid",fgColor="0B4DB8")
        cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
    widths={
        "İlan No":14,"Başlık":42,"Danışman":26,"Telefon":18,"Fiyat":18,"Bölge":28,
        "İl":16,"İlçe":18,"Mahalle":24,"Sokak/Cadde":28,"Site/Proje":26,"Açık Adres":46,
        "Oda":12,"Satılık Kiralık":18,"Emlak Türü":20,"Brüt m²":14,"Net m²":14,
        "İlan Tarihi":18,"İlan Açıklaması":60,"İlan Linki":48,"Kaynak":48,
    }
    for index,header in enumerate(headers,1):
        ws.column_dimensions[get_column_letter(index)].width=widths.get(header,20)
    ws.freeze_panes="A2"
    ws.auto_filter.ref=ws.dimensions

def write_list_file(path,items):
    from openpyxl import Workbook

    path=Path(path)
    rows=list(items)
    headers=_export_headers(rows)
    if path.suffix.lower()==".csv":
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",encoding="utf-8-sig",newline="") as stream:
            writer=csv.writer(stream,delimiter=";")
            writer.writerow(headers)
            writer.writerows(_export_row(item,headers) for item in rows)
        return path
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Dışa aktarma dosyası .xlsx veya .csv uzantılı olmalıdır.")
    wb=Workbook(); ws=wb.active; ws.title="İlan Listesi"
    ws.append(headers)
    link_column=headers.index("İlan Linki")+1
    for item in rows:
        ws.append(_export_row(item,headers))
        if item.url:
            cell=ws.cell(ws.max_row,link_column); cell.hyperlink=item.url; cell.style="Hyperlink"
    _style_xlsx_headers(ws,headers)
    path.parent.mkdir(parents=True,exist_ok=True)
    wb.save(path)
    return path

def write_ai_template(path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill

    path=Path(path)
    if path.suffix.lower()!=".xlsx":
        raise ValueError("Yapay zekâ şablonu .xlsx uzantılı olmalıdır.")
    headers=[header for _field,header in FIXED_EXPORT_FIELDS]+COMMON_DETAIL_HEADERS
    wb=Workbook(); ws=wb.active; ws.title="İlanlar"
    ws.append(headers)
    _style_xlsx_headers(ws,headers)
    notes=wb.create_sheet("Alan Açıklamaları")
    notes.append(["Kural","Açıklama"])
    notes.append(["Zorunlu alan","yalnızca İlan Linki zorunludur."])
    notes.append(["Eksik bilgi","Kaynakta görünmeyen bilgileri tahmin etmeyin; boş bırakın."])
    notes.append(["Ek alanlar","İlan sayfasındaki başka özellikleri yeni sütunlar olarak ekleyebilirsiniz."])
    notes.append(["Bir satır bir ilan","Her ilanı ayrı satıra yazın ve başlıkları değiştirmeyin."])
    for cell in notes[1]:
        cell.font=Font(color="FFFFFF",bold=True)
        cell.fill=PatternFill("solid",fgColor="0B4DB8")
        cell.alignment=Alignment(horizontal="center",vertical="center")
    notes.column_dimensions["A"].width=24
    notes.column_dimensions["B"].width=90
    notes.freeze_panes="A2"
    notes.sheet_view.showGridLines=False
    ws.sheet_view.showGridLines=False
    path.parent.mkdir(parents=True,exist_ok=True)
    wb.save(path)
    return path
def price_number(s):
    digits=re.sub(r"[^0-9]","",str(s or "")); return int(digits) if digits else None
def is_valid_advisor(name):
    raw=(name or "").strip()
    if not raw or len(raw)<5 or len(raw)>70 or any(ch.isdigit() for ch in raw): return False
    n=norm(raw)
    if any(tok in n for tok in NOISE_ADVISOR_TOKENS): return False
    words=[w for w in re.split(r"\s+",raw) if w]
    if len(words)<2:return False
    letters=sum(ch.isalpha() for ch in raw)
    return letters >= max(4,int(len(raw)*0.55))
def advisor_display_name(name):
    raw=" ".join(str(name or "").split())
    return raw if is_valid_advisor(raw) else "Belirtilmemiş"
def advisor_names(items):
    names={x.advisor.strip() for x in items if is_valid_advisor(x.advisor)}
    return sorted(names,key=norm)
def filter_listings(items,advisor="",transaction="",property_type="",location="",min_price=None,max_price=None,query=""):
    rows=list(items)
    if advisor: rows=[x for x in rows if norm(x.advisor)==norm(advisor)]
    if transaction: rows=[x for x in rows if norm(transaction) in norm(x.transaction_type)]
    if property_type: rows=[x for x in rows if norm(property_type) in norm(x.property_type)]
    if location: rows=[x for x in rows if norm(location) in norm(x.location)]
    if min_price is not None: rows=[x for x in rows if price_number(x.price) is not None and price_number(x.price)>=int(min_price)]
    if max_price is not None: rows=[x for x in rows if price_number(x.price) is not None and price_number(x.price)<=int(max_price)]
    if query:
        from .core import search
        rows=search(rows,query)
    return rows
def command_help(prefix="#"):
    p=normalize_command_prefix(prefix)
    return f"""RE/MAX ÇARŞI İLAN BOTU KOMUTLARI

{p}Max başla / {p}Max başlat
Max ilan arama botunu aktif eder.

{p}Max durdur
Max ilan arama botunu durdurur.

{p}?
Komut listesini gösterir.

{p}danışmanlar
Gerçek danışmanları mevcut ilan adetleriyle listeler.

{p}yahya kaptan kiralık 3+1
Uygun ilanların linklerini danışman adıyla gönderir.

{p}yahya kaptan kiralık 3+1 link
Eski kullanım biçimidir; link kelimesi artık zorunlu değildir.

{p}izmit kiralık dükkan-ofis
Dükkan veya ofis türündeki kiralık ilanların linklerini gönderir.

{p}izmit satılık ev-daire
Ev veya daire türündeki satılık ilanların linklerini gönderir.

{p}izmit kiralık 55 bin
55.000 TL ve altındaki uygun ilanları linkleriyle gönderir.

{p}izmit satılık daire 4 milyon
4.000.000 TL ve altındaki uygun ilanları linkleriyle gönderir.

{p}danışman ayşe
Danışman adına göre ilanları bulur.

{p}emlakjet izmit kiralık
Yalnızca Emlakjet listesindeki uygun ilanların linklerini gönderir.

{p}sahibinden izmit satılık
Yalnızca Sahibinden listesindeki uygun ilanların linklerini gönderir.

{p}myremax yahya kaptan kiralık
Yalnızca MyRE/MAX listesindeki uygun ilanların linklerini gönderir.

Komutta site adı yoksa Ayarlar bölümünde kayıtlı ilan linki kaynağı kullanılır.
{p}danışmanlar komutu her zaman üç sitenin tamamını sayar.
İlan aramalarında link kelimesi yazmanız gerekmez; sonuçlar doğrudan linkleriyle gönderilir.

Komutun yalnızca başında # olması yeterlidir.
Eski {p}komut{p} biçimi de desteklenir.

Eski biçim örnekleri:
{p}danışmanlar{p}
{p}yahya kaptan kiralık 3+1{p}
{p}izmit kiralık 55 bin{p}
{p}izmit satılık daire 4 milyon{p}""".replace("Komutun yalnızca başında #",f"Komutun yalnızca başında {p}")
def _command_body(text,prefix="#"):
    p=normalize_command_prefix(prefix)
    t=(text or "").strip()
    if t==p+"?": return "?",True
    if len(t)<2 or not t.startswith(p): return "",False
    body=t[1:]
    if body.endswith(p): body=body[:-1]
    return body.strip(),True
def parse_command(text,prefix="#"):
    body,ok=_command_body(text,prefix)
    if not ok:return {"type":"ignore"}
    if body=="?":return {"type":"help"}
    if not body:return {"type":"ignore"}
    if norm(body)=="danismanlar":return {"type":"advisors"}
    parts=body.split(maxsplit=1)
    source=COMMAND_SOURCE_PREFIXES.get(norm(parts[0]))
    if source:
        body=parts[1].strip() if len(parts)>1 else ""
    link=True; body=re.sub(r"(?i)\blink\b"," ",body).strip()
    m=re.match(r"(?i)danışman\s+(.+)$",body)
    if not m:m=re.match(r"(?i)danisman\s+(.+)$",norm(body))
    if m:return {"type":"search","query":m.group(1).strip(),"links":link,"advisor_only":True,"target_price":None,"source":source}
    target=None; normalized=norm(body)
    suffix_matches=list(re.finditer(r"(?<![\d+])(\d+(?:[.,]\d+)?)\s*(bin|k|milyon|mn)(?:\s*(?:tl|₺))?(?!\w)",normalized))
    if suffix_matches:
        pm=suffix_matches[-1]; number=float(pm.group(1).replace(",","."))
        multiplier=1_000_000 if pm.group(2) in {"milyon","mn"} else 1_000
        target=int(number*multiplier)
        body=re.sub(r"(?i)(?<![\d+])\d+(?:[.,]\d+)?\s*(?:bin|k|milyon|mn)(?:\s*(?:tl|₺))?(?!\w)"," ",body,count=1).strip()
    else:
        direct=list(re.finditer(r"(?<![\d+])(?:\d{1,3}(?:[.\s]\d{3})+|\d{4,9})(?:\s*(?:tl|₺))?(?![\d+])",body,re.I))
        if direct:
            raw=direct[-1].group(0); target=int(re.sub(r"[^0-9]","",raw))
            body=(body[:direct[-1].start()]+" "+body[direct[-1].end():]).strip()
    return {"type":"search","query":body,"links":link,"target_price":target,"source":source}
def _relevance_score(item,query,fields):
    selected=set(fields)
    values={
        "title":item.title,
        "advisor":item.advisor,
        "location":" ".join([
            item.location,item.province,item.district,item.neighborhood,item.street,
            item.complex_name,item.full_address,
        ]),
        "phone":item.phone,"price":item.price,"rooms":item.rooms,
        "transaction_type":item.transaction_type,"property_type":item.property_type,
        "sqm":" ".join([item.sqm,item.net_sqm]),"listing_date":item.listing_date,
        "description":item.description,"details":details_text(item.details),
    }
    weights={"location":8,"title":7,"advisor":7,"rooms":4,"transaction_type":4,"property_type":4}
    tokens=[token for token in norm(query).split() if token]
    score=0
    normalized_query=norm(query)
    for name,value in values.items():
        if name not in selected: continue
        hay=norm(value); weight=weights.get(name,1)
        score+=sum(weight for token in tokens if token in hay)
        if normalized_query and normalized_query in hay: score+=weight*4
    return score

def command_response(items,text,limit=12,link_source=None,prefix="#",search_sources=None,search_fields=None):
    from .core import search
    p=normalize_command_prefix(prefix)
    cmd=parse_command(text,prefix=p)
    if cmd["type"]=="ignore":return None
    if cmd["type"]=="help":return command_help(prefix=p)
    if cmd["type"]=="advisors":
        unique_rows={}
        for x in items:
            site=source_site(x.source_url,x.url)
            unique_key=(site,listing_identity(x))
            current=unique_rows.get(unique_key)
            if current is None or (not is_valid_advisor(current.advisor) and is_valid_advisor(x.advisor)):
                unique_rows[unique_key]=x
        groups={}
        for unique_key,x in unique_rows.items():
            site=unique_key[0]
            if is_valid_advisor(x.advisor):
                name=x.advisor.strip()
                advisor_key=norm(name)
                group=groups.get(advisor_key)
                if group is None:
                    group={"name":name,"counts":{"MyRE/MAX":0,"Emlakjet":0,"Sahibinden":0,"Diğer":0}}
                    groups[advisor_key]=group
                elif group["name"].isupper() and not name.isupper():
                    group["name"]=name
                counts=group["counts"]
                counts[site]+=1
        if not groups:return "İlan havuzunda geçerli danışman bilgisi bulunamadı."
        lines=["DANIŞMAN İLAN DAĞILIMI",""]
        ordered=sorted(groups.values(),key=lambda g:(-sum(g["counts"].values()),norm(g["name"])))
        for group in ordered:
            name=group["name"]; counts=group["counts"]
            total=sum(counts.values())
            lines += [
                f"{name} — Toplam {total} ilan",
                f"MyRE/MAX: {counts['MyRE/MAX']} | Emlakjet: {counts['Emlakjet']} | Sahibinden: {counts['Sahibinden']}",
            ]
            if counts["Diğer"]:
                lines.append(f"Diğer: {counts['Diğer']}")
            lines.append("")
        lines += ["",f"Toplam ilan: {len(unique_rows)}",f"Toplam danışman: {len(groups)}"]
        return "\n".join(lines)
    configured_source=(link_source if link_source in LINK_SOURCES else ("MyRE/MAX" if link_source is not None else None))
    allowed_sources=None if search_sources is None else set(normalize_search_sources(search_sources))
    requested_source=cmd.get("source")
    selected_source=requested_source or (configured_source if allowed_sources is None else None)
    searchable=list(items)
    if requested_source and allowed_sources is not None and requested_source not in allowed_sources:
        searchable=[]
    elif selected_source:
        searchable=[x for x in searchable if source_site(x.source_url,x.url)==selected_source]
    elif allowed_sources is not None:
        searchable=[x for x in searchable if source_site(x.source_url,x.url) in allowed_sources]
    fields=normalize_search_fields(search_fields) if search_fields is not None else list(DEFAULT_SEARCH_FIELDS)
    query=cmd.get("query","")
    matches=search(searchable,query,fields=fields)
    matches=sorted(matches,key=lambda item:(-_relevance_score(item,query,fields),norm(item.title),str(item.listing_id)))
    target=cmd.get("target_price")
    if target is not None:
        priced=[(price_number(x.price),x) for x in matches]; priced=[p for p in priced if p[0] is not None and p[0]<=target]
        matches=[x for _,x in sorted(priced,key=lambda p:p[0],reverse=True)]
    if not matches:
        if selected_source:return f"{selected_source} listesinde aramanıza uygun ilan bulunamadı."
        if allowed_sources is not None:return "Seçili kaynaklarda aramanıza uygun ilan bulunamadı."
        if target is not None:return f"{target:,.0f} TL ve altında aramanıza uygun ilan bulunamadı.".replace(",",".")
        return "Aramanıza uygun ilan bulunamadı."
    if cmd.get("links") or target is not None:
        lines=[f"{target:,.0f} TL ve altında {len(matches)} uygun ilan bulundu:".replace(",",".")] if target is not None else [f"{len(matches)} uygun ilan bulundu:"]
        for x in (matches if target is not None else matches[:limit]):
            advisor=advisor_display_name(x.advisor)
            address=display_address(x) or x.location
            lines += ["",x.title,f"{x.price} | {address}",f"Danışman: {advisor}",x.url or "(link yok)"]
        return "\n".join(lines)
    by={}
    for x in matches:
        name=advisor_display_name(x.advisor); by[name]=by.get(name,0)+1
    return "\n".join([f"{len(matches)} uygun ilan bulundu:"]+[f"{k}: {v} ilan" for k,v in sorted(by.items(),key=lambda kv:(-kv[1],norm(kv[0])))]+["","Linkleri görmek için aynı komuta link ekleyin."])
