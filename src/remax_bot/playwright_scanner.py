from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    class QObject:
        pass
    class Signal:
        def __init__(self, *args, **kwargs):
            pass
        def emit(self, *args, **kwargs):
            pass

from .core import Listing, source_key

MONTHS = "Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık"


def browser_launch_options() -> dict:
    # This is intentionally the same launch path that was manually verified on macOS.
    return {
    "headless": False,
    "channel": "chrome",
    "args": ["--start-maximized"],
}

def is_listing_row_text(text: str) -> bool:
    value = text or ""
    has_price = bool(re.search(r"\b[\d.]+\s*TL\b", value, re.I))
    has_date = bool(re.search(rf"\b\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}\b", value, re.I))
    has_location = bool(re.search(r"\b(?:Kocaeli|İstanbul|Ankara|İzmir)\s*/", value, re.I))
    return has_price and (has_date or has_location)




def candidate_title_from_row_text(text: str) -> str:
    lines=[re.sub(r"\s+"," ",line).strip() for line in (text or "").splitlines()]
    for line in lines:
        if len(line) < 8 or len(line) > 220:
            continue
        if re.search(r"\b[\d.]+\s*TL\b", line, re.I):
            continue
        if re.search(rf"^\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}$", line, re.I):
            continue
        if re.search(r"^(?:Kocaeli|İstanbul|Ankara|İzmir)\s*/", line, re.I):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        return line
    return ""

def normalize_listing_url(url: str) -> str:
    p = urlsplit((url or "").strip())
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))



def extract_remax_portfolio_links(hrefs: list[str], base_url: str) -> list[str]:
    out=[]; seen=set()
    for href in hrefs:
        url=normalize_listing_url(urljoin(base_url, href or ""))
        if not re.search(r"/tr/portfoy/P\d{6,}$", url, re.I):
            continue
        key=url.casefold()
        if key not in seen:
            seen.add(key); out.append(url)
    return out

def extract_emlakjet_listing_links(hrefs: list[str], base_url: str) -> list[str]:
    out=[]; seen=set()
    for href in hrefs:
        url=normalize_listing_url(urljoin(base_url,href or ""))
        path=urlsplit(url).path.rstrip("/")
        if not re.fullmatch(r"/ilan/[^/]+-\d{6,}",path,re.I):
            continue
        key=url.casefold()
        if key not in seen:
            seen.add(key); out.append(url)
    return out

def extract_sahibinden_listing_links(hrefs: list[str], base_url: str) -> list[str]:
    out=[]; seen=set()
    for href in hrefs:
        url=normalize_listing_url(urljoin(base_url,href or ""))
        path=urlsplit(url).path.rstrip("/")
        if not re.fullmatch(r"/ilan/[^/]+-\d{8,}/detay",path,re.I):
            continue
        key=url.casefold()
        if key not in seen:
            seen.add(key); out.append(url)
    return out

def source_platform(url: str) -> str:
    host=urlsplit((url or "").strip()).netloc.lower().split(":")[0]
    if host=="remax.com.tr" or host.endswith(".remax.com.tr"): return "remax"
    if host=="emlakjet.com" or host.endswith(".emlakjet.com"): return "emlakjet"
    if host=="sahibinden.com" or host.endswith(".sahibinden.com"): return "sahibinden"
    return "unknown"

def _label_value(lines: list[str], *labels: str) -> str:
    folded=[x.casefold() for x in lines]
    for label in labels:
        try:
            i=folded.index(label.casefold())
            if i+1 < len(lines): return lines[i+1].strip()
        except ValueError:
            pass
    return ""

def parse_remax_detail(*, text: str, url: str, source_url: str) -> Listing:
    lines=[re.sub(r"\s+", " ", x).strip() for x in (text or "").splitlines() if x.strip()]
    lid=_label_value(lines,"Portföy No")
    if not lid:
        m=re.search(r"/portfoy/(P\d{6,})",url,re.I); lid=m.group(1).upper() if m else normalize_listing_url(url)
    title=""
    try:
        i=next(i for i,x in enumerate(lines) if x.casefold()=="ilan detayı")
        if i+1<len(lines): title=lines[i+1]
    except StopIteration: pass
    if not title:
        title=next((x for x in lines if len(x)>10 and x.upper()==x and not re.search(r"\d+[.]?\d*\s*₺",x)), f"Portföy {lid}")
    price=next((m.group(1)+" ₺" for x in lines if (m:=re.search(r"^([\d.]+)\s*₺$",x))),"")
    emlak=_label_value(lines,"Emlak Tipi")
    parts=[x.strip() for x in emlak.split("/")]
    ptype=parts[0] if parts else ""; trans=parts[1] if len(parts)>1 else ""
    rooms=_label_value(lines,"Oda Sayısı","Bölüm & Oda Sayısı")
    gross=_label_value(lines,"m2 (Brüt)","m² (Brüt)","m²","m2")
    date=_label_value(lines,"Yayınlanma Tarihi")
    phone=_extract_phone(text)
    advisor=""
    if phone:
        phone_digits=re.sub(r"\D","",phone)[-10:]
        for i,x in enumerate(lines):
            if phone_digits and phone_digits in re.sub(r"\D","",x):
                for cand in reversed(lines[max(0,i-7):i]):
                    if 4<=len(cand)<=80 and not re.search(r"\d|/",cand) and not re.search(r"iletişim|sertifika|re/max|emlak endeksi|oda sayısı",cand,re.I):
                        advisor=re.sub(r"\s+Çarşı(?:\s+2)?$","",cand,flags=re.I).strip(); break
                break
    location=""
    for x in lines:
        if re.search(r"Kocaeli\s*/|İzmit\s*/|Başiskele\s*/|Kartepe\s*/|Kandıra\s*/|Gölcük\s*/|Derince\s*/|Körfez\s*/",x,re.I): location=x; break
    return Listing(str(lid),title,normalize_listing_url(url),advisor,phone,price,location,rooms,trans,ptype,(gross+" m²") if gross else "",date,source_key(source_url))

def extract_emlakjet_total_count(text: str) -> int:
    for pattern in (r"İlan Sayısı\s*:\s*([\d.]+)",r"Tüm İlanlar\s+([\d.]+)"):
        match=re.search(pattern,text or "",re.I)
        if match:
            return int(match.group(1).replace(".",""))
    return 0

def _value_before_label(lines: list[str], label: str) -> str:
    for i,line in enumerate(lines):
        if line.casefold()==label.casefold() and i:
            return lines[i-1]
    return ""

def parse_emlakjet_detail(*,text:str,url:str,source_url:str,title:str="",price:str="",advisor:str="",phone:str="") -> Listing:
    text=text or ""
    lines=[re.sub(r"\s+"," ",line).strip() for line in text.splitlines() if line.strip()]
    clean_url=normalize_listing_url(url)
    match=re.search(r"İlan Numarası\s*[:#]?\s*(\d+)",text,re.I)
    if match:
        listing_id=match.group(1)
    else:
        ids=re.findall(r"-(\d{6,})(?:/)?$",urlsplit(clean_url).path)
        listing_id=ids[-1] if ids else clean_url

    if not title:
        ignored={"paylaş","ilan bilgileri","genel bakış","özellikler","açıklama"}
        title=next((line for line in lines if len(line)>=12 and line.casefold() not in ignored and not re.fullmatch(r"[\d.]+\s*₺",line)),"")
    if not price:
        price=next((line for line in lines if re.fullmatch(r"[\d.]+\s*₺",line)),"")
    rooms=_value_before_label(lines,"Oda Sayısı")
    sqm=_value_before_label(lines,"Brüt")
    if sqm and not re.search(r"m(?:²|2)",sqm,re.I):
        sqm=f"{sqm} m²"
    date_match=re.search(r"İlan Güncelleme Tarihi\s+([^\n]+)",text,re.I)
    listing_date=date_match.group(1).strip() if date_match else ""
    category_match=re.search(r"Kategori\s+([^\n]+)",text,re.I)
    category=category_match.group(1).strip() if category_match else ""
    transaction_type=next((value for value in ("Devren","Kiralık","Satılık") if value.casefold() in category.casefold()),"")
    property_type=re.sub(r"^(?:Devren|Kiralık|Satılık)\s+","",category,flags=re.I).strip()

    location=""
    location_match=re.search(r"([^,\n]+),\s*([^,\n]+),\s*([^\n-]+)\s*-\s*Haritada",text,re.I)
    if location_match:
        neighborhood,district,province=(part.strip() for part in location_match.groups())
        location=" / ".join((province,district,neighborhood))
    if not advisor:
        advisor_match=re.search(r"^([^\n|]{5,70})\s*\|\s*RE/MAX\s+ÇARŞI(?:\s+2)?\s*$",text,re.I|re.M)
        advisor=advisor_match.group(1).strip() if advisor_match else ""
    if not phone:
        phone=_extract_phone(text)
    return Listing(
        str(listing_id),title or f"İlan {listing_id}",clean_url,advisor,phone,price,location,
        rooms,transaction_type,property_type,sqm,listing_date,source_key(source_url)
    )

def extract_total_count(text: str) -> int:
    patterns = [
        r"seçimlerinize uygun\s+([\d.]+)\s+ilan listeleniyor",
        r"portföyümüz[\s\S]{0,120}?([\d.]+)\s+ilan",
        r"([\d.]+)\s+ilan\s+listeleniyor",
    ]
    for pattern in patterns:
        m = re.search(pattern, text or "", re.I)
        if m:
            try:
                return int(m.group(1).replace(".", ""))
            except ValueError:
                pass
    return 0


def is_human_verification(text: str) -> bool:
    value = (text or "").casefold()
    markers = [
        "robot olmadığınızı", "robot değilim", "captcha", "güvenlik kontrolü",
        "doğrulama gerekiyor", "olağandışı trafik", "verify you are human",
    ]
    return any(marker in value for marker in markers)


def _extract_phone(text: str) -> str:
    m = re.search(
        r"(?:\+90\s*)?(?:0\s*)?(5\d{2})[\s\-().]*(\d{3})[\s\-()]*(\d{2})[\s\-()]*(\d{2})",
        text or "",
    )
    return f"0{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)}" if m else ""


def parse_listing_detail(*, text: str, url: str, source_url: str, title: str = "", price: str = "", advisor: str = "", phone: str = "") -> Listing:
    text = text or ""
    clean_url = normalize_listing_url(url)
    id_match = re.search(r"(?:İlan No|İlan No:)\s*[:#]?\s*(\d+)", text, re.I)
    if id_match:
        listing_id = id_match.group(1)
    else:
        digits = re.findall(r"(\d{8,})", clean_url)
        listing_id = digits[-1] if digits else clean_url

    room_match = re.search(r"\b(\d+(?:\.\d+)?\+\d+)\b", text)
    rooms = room_match.group(1) if room_match else ""
    sqm_match = re.search(r"\b([\d.]+)\s*m(?:²|2)\b", text, re.I)
    sqm = f"{sqm_match.group(1)} m²" if sqm_match else ""
    date_match = re.search(rf"\b(\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}})\b", text, re.I)
    listing_date = date_match.group(1) if date_match else ""

    advisor_is_store=bool(re.search(r"\b(?:re\s*/?\s*max|gayrimenkul|emlak)\b",advisor or "",re.I))
    if not advisor or advisor_is_store:
        adv_match = re.search(
            r"(?:Yetkili\s+(?:Gayrimenkul\s+)?Danışmanı?|Gayrimenkul\s+Danışmanı?|Danışman|İlan Sahibi)\s*[:\n]\s*([^\n]+)",
            text,re.I
        )
        if adv_match:
            advisor=adv_match.group(1).strip()
    if not phone:
        phone = _extract_phone(text)

    location = ""
    loc_match = re.search(
        r"([A-Za-zÇĞİÖŞÜçğıöşü ]+)\s*/\s*([A-Za-zÇĞİÖŞÜçğıöşü ]+)(?:\s*/\s*([A-Za-zÇĞİÖŞÜçğıöşü ]+))?",
        text,
    )
    if loc_match:
        location = " / ".join(p.strip() for p in loc_match.groups() if p and p.strip())

    low = f"{title} {text[:8000]}".casefold()
    transaction_type = "Devren Kiralık" if "devren kiralık" in low else "Kiralık" if "kiralık" in low else "Satılık" if "satılık" in low else ""
    property_type = next((c for c in ["Daire", "Villa", "Arsa", "İş Yeri", "İşyeri", "Tarla", "Dükkan", "Ofis", "Bina"] if c.casefold() in low), "")

    return Listing(
        listing_id=str(listing_id), title=(title or f"İlan {listing_id}").strip(), url=clean_url,
        advisor=(advisor or "").strip(), phone=(phone or "").strip(), price=(price or "").strip(),
        location=location, rooms=rooms, transaction_type=transaction_type, property_type=property_type,
        sqm=sqm, listing_date=listing_date, source_url=source_key(source_url),
    )

def is_valid_detail_listing(platform:str,text:str,item:Listing|None,expected_url:str)->bool:
    if item is None or not (text or "").strip():
        return False
    if source_key(item.url)!=source_key(expected_url) or source_platform(item.url)!=platform:
        return False
    placeholder_titles={f"İlan {item.listing_id}",f"Portföy {item.listing_id}"}
    if not item.listing_id or not item.title or item.title in placeholder_titles:
        return False
    required={
        "remax":("Portföy No","Emlak Tipi"),
        "emlakjet":("İlan Numarası","Kategori"),
        "sahibinden":("İlan No",),
    }.get(platform,())
    return bool(required and all(marker.casefold() in text.casefold() for marker in required))

def validate_scan_completeness(*,total:int,discovered:int,parsed:int)->None:
    if total<=0:
        raise RuntimeError("Kaynakta toplam ilan sayısı okunamadı. Eski ilanlar korundu.")
    if discovered!=total:
        raise RuntimeError(f"Kaynakta {total} ilan görünüyor; {discovered} ilan linki bulundu. Eski ilanlar korundu.")
    if parsed!=discovered:
        raise RuntimeError(f"{discovered} ilan linki bulundu; {parsed} ilan doğrulandı. Eski ilanlar korundu.")


ROW_MARK_JS = r"""() => {
  const MONTHS=/Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık/i;
  const priceRe=/\b[\d.]+\s*TL\b/i;
  const dateRe=new RegExp('\\b\\d{1,2}\\s+('+MONTHS.source+')\\s+\\d{4}\\b','i');
  const locRe=/\b(Kocaeli|İstanbul|Ankara|İzmir)\s*\//i;
  const badTitle=/^(Sonraki|Önceki|Sırala|Filtrele|Tüm İlanlar|Öne Çıkanlar|Ekibimiz|Hakkımızda|Telefonu Göster|Mesaj Gönder)$/i;

  const all=Array.from(document.querySelectorAll('tr,li,article,[class*="result"],[class*="listing"],[class*="classified"]'));
  const seenRows=new Set();
  const candidates=[];

  function qualifies(el){
    const t=(el.innerText||'').replace(/\s+/g,' ').trim();
    return t && priceRe.test(t) && (dateRe.test(t) || locRe.test(t));
  }

  function chooseTitle(row){
    const nodes=Array.from(row.querySelectorAll('a,button,[role="link"],[onclick],td,span,div'));
    let best=null;
    for(const el of nodes){
      const t=(el.innerText||'').replace(/\s+/g,' ').trim();
      if(t.length<8 || t.length>220) continue;
      if(badTitle.test(t) || /^\d+$/.test(t) || priceRe.test(t) || dateRe.test(t) || locRe.test(t)) continue;
      const score=(el.matches('a,button,[role="link"],[onclick]')?100:0) + Math.min(t.length,80);
      if(!best || score>best.score) best={el,text:t,score};
    }
    return best;
  }

  for(const row of all){
    if(!qualifies(row)) continue;
    // Prefer the smallest matching container to avoid duplicate nested wrappers.
    if(Array.from(row.children||[]).some(ch=>qualifies(ch))) continue;
    const title=chooseTitle(row);
    if(!title) continue;
    const key=title.text.toLocaleLowerCase('tr-TR');
    if(seenRows.has(key)) continue;
    seenRows.add(key);
    title.el.setAttribute('data-remax-scan-index',String(candidates.length));
    candidates.push({
      title:title.text,
      tag:title.el.tagName,
      href:title.el.getAttribute('href')||'',
      rowText:(row.innerText||'').slice(0,700)
    });
  }

  // Broad fallback: if no semantic row wrappers matched, inspect every element and
  // keep the smallest price/date/location container.
  if(!candidates.length){
    const broad=Array.from(document.querySelectorAll('body *')).filter(qualifies);
    for(const row of broad){
      if(Array.from(row.children||[]).some(ch=>qualifies(ch))) continue;
      const title=chooseTitle(row); if(!title) continue;
      const key=title.text.toLocaleLowerCase('tr-TR'); if(seenRows.has(key)) continue;
      seenRows.add(key);
      title.el.setAttribute('data-remax-scan-index',String(candidates.length));
      candidates.push({title:title.text,tag:title.el.tagName,href:title.el.getAttribute('href')||'',rowText:(row.innerText||'').slice(0,700)});
    }
  }

  const diagnostics={
    trCount:document.querySelectorAll('tr').length,
    anchorCount:document.querySelectorAll('a').length,
    priceTextCount:Array.from(document.querySelectorAll('body *')).filter(el=>priceRe.test((el.innerText||'').trim())).length,
    bodyLength:(document.body?.innerText||'').length
  };
  return {candidates,diagnostics};
}"""


class PlaywrightScanner(QObject):
    progress = Signal(str)
    status = Signal(str)
    done = Signal(str, list)
    failed = Signal(str)
    busy_changed = Signal(bool)
    verification_needed = Signal(str)

    def __init__(self, profile_dir: Path):
        super().__init__()
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.profile_dir / "storage-state.json"
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._busy = False

    @property
    def phase(self) -> str:
        return "busy" if self._busy else "idle"

    def start(self, source_url: str) -> None:
        if self._busy:
            return
        self._busy = True
        self._stop.clear(); self._resume.clear(); self.busy_changed.emit(True)
        self._thread = threading.Thread(target=self._run, args=(source_url,), daemon=True)
        self._thread.start()

    def resume(self) -> None:
        self._resume.set()

    def stop(self) -> None:
        self._stop.set(); self._resume.set(); self.status.emit("Tarama durduruluyor...")

    def _wait_for_user(self, message: str) -> bool:
        self.verification_needed.emit(message); self.status.emit(message); self._resume.clear()
        while not self._stop.is_set():
            if self._resume.wait(timeout=0.5):
                self._resume.clear(); return True
        return False

    def _body_text(self, page) -> str:
        try:
            return page.locator("body").inner_text(timeout=7000)
        except Exception:
            return ""

    def _ensure_not_blocked(self, page) -> bool:
        text = self._body_text(page)
        if is_human_verification(text):
            return self._wait_for_user(
                "İlan sitesi güvenlik doğrulaması istiyor. Açık tarayıcıda işlemi tamamlayın ve DEVAM ET'e basın."
            )
        return True

    def _save_state(self, context) -> None:
        try:
            context.storage_state(path=str(self.state_file))
        except Exception:
            pass

    def _new_context(self, browser):
        kwargs = {"viewport": None}
        if self.state_file.exists():
            kwargs["storage_state"] = str(self.state_file)
        return browser.new_context(**kwargs)

    def _open_list(self, page, source_url: str) -> None:
        sep = "&" if "?" in source_url else "?"
        url = source_url + sep + "display=list"
        self.status.emit("Sahibinden ilan listesi yükleniyor...")
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.bring_to_front()
        page.wait_for_timeout(2500)
        if not self._ensure_not_blocked(page):
            raise RuntimeError("Tarama kullanıcı tarafından durduruldu.")

    def _mark_rows_with_locators(self, page) -> tuple[list[dict], dict]:
        """Fallback that uses Playwright locators, which can pierce open Shadow DOM."""
        selectors = 'tr, li, article, [class*="result"], [class*="listing"], [class*="classified"]'
        candidates: list[dict] = []
        seen: set[str] = set()
        scanned = 0
        try:
            rows = page.locator(selectors)
            count = min(rows.count(), 2500)
            for i in range(count):
                row = rows.nth(i)
                try:
                    text = row.inner_text(timeout=250).strip()
                except Exception:
                    continue
                scanned += 1
                if not is_listing_row_text(text):
                    continue
                title = candidate_title_from_row_text(text)
                if not title:
                    continue
                key = title.casefold()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({"title": title, "href": "", "rowText": text[:700], "strategy": "text"})
            return candidates, {"locatorScanned": scanned, "locatorCandidates": len(candidates)}
        except Exception as exc:
            return [], {"locatorError": str(exc), "locatorScanned": scanned}

    def _mark_rows(self, page) -> tuple[list[dict], dict]:
        diagnostics: dict = {}
        try:
            data = page.evaluate(ROW_MARK_JS) or {}
            candidates = list(data.get("candidates") or [])
            diagnostics.update(dict(data.get("diagnostics") or {}))
            if candidates:
                for item in candidates:
                    item.setdefault("strategy", "marker")
                return candidates, diagnostics
        except Exception as exc:
            diagnostics["jsError"] = str(exc)

        fallback, fallback_diag = self._mark_rows_with_locators(page)
        diagnostics.update(fallback_diag)
        return fallback, diagnostics

    def _click_row_open_detail(self, context, page, row_index: int):
        # Markers are regenerated after each back-navigation.
        rows, _diag = self._mark_rows(page)
        if row_index >= len(rows):
            return None, None
        candidate = rows[row_index]
        if candidate.get("strategy") == "text":
            locator = page.get_by_text(candidate.get("title", ""), exact=True).first
        else:
            locator = page.locator(f'[data-remax-scan-index="{row_index}"]')
        before_url = page.url
        before_pages = list(context.pages)
        try:
            locator.scroll_into_view_if_needed(timeout=5000)
            locator.click(timeout=10000, force=True)
        except Exception:
            try:
                locator.evaluate("el => el.click()")
            except Exception:
                return None, None

        # JS-driven links can take a moment to replace the URL.
        for _ in range(30):
            if self._stop.is_set():
                return None, None
            context.pages  # refresh page list
            new_pages = [p for p in context.pages if p not in before_pages]
            if new_pages:
                detail = new_pages[-1]
                try: detail.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception: pass
                detail.bring_to_front(); return detail, "popup"
            if page.url != before_url and ("/ilan/" in page.url or "classified" in page.url.casefold()):
                try: page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception: pass
                return page, "same"
            page.wait_for_timeout(200)
        return None, None

    def _first_text(self, page, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                loc = page.locator(selector)
                if loc.count():
                    value = loc.first.inner_text(timeout=1500).strip()
                    if value:
                        return value
            except Exception:
                pass
        return ""

    def _read_detail(self, page, source_url: str) -> tuple[Listing | None,str]:
        page.wait_for_timeout(800)
        if not self._ensure_not_blocked(page):
            return None,""
        title = self._first_text(page, ["h1", ".classifiedDetailTitle h1", '[data-testid="classified-title"]'])
        price = self._first_text(page, [".classifiedInfo h3", ".classifiedInfo .price", '[data-testid="classified-price"]'])
        advisor = self._first_text(page, [".userInfoStoreName", ".classifiedUserInfo .username-info-area", ".user-info-store-name"])
        phone = ""
        try:
            tel = page.locator('a[href^="tel:"]')
            if tel.count(): phone = (tel.first.get_attribute("href") or "").removeprefix("tel:").strip()
        except Exception: pass
        if not phone:
            try:
                show = page.get_by_text(re.compile(r"Telefonu Göster|Telefon Göster", re.I))
                if show.count() and show.first.is_visible():
                    show.first.click(); page.wait_for_timeout(800)
                    tel = page.locator('a[href^="tel:"]')
                    if tel.count(): phone = (tel.first.get_attribute("href") or "").removeprefix("tel:").strip()
            except Exception: pass
        body = self._body_text(page)
        item=parse_listing_detail(text=body, url=page.url, source_url=source_url, title=title, price=price, advisor=advisor, phone=phone)
        return item,body

    def _go_back_to_list(self, page, list_url: str) -> None:
        try:
            page.go_back(wait_until="domcontentloaded", timeout=30000)
        except Exception:
            page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(1200)
        page.bring_to_front()

    def _next_page(self, page) -> bool:
        selectors = ['a[rel="next"]', 'a[title*="Sonraki"]', 'a:has-text("Sonraki")', 'button:has-text("Sonraki")']
        for selector in selectors:
            try:
                loc = page.locator(selector)
                if loc.count() and loc.first.is_visible():
                    before = page.url
                    loc.first.click(timeout=10000)
                    try: page.wait_for_load_state("domcontentloaded", timeout=30000)
                    except Exception: pass
                    page.wait_for_timeout(1200)
                    return page.url != before or True
            except Exception:
                continue
        return False

    def _collect_remax_links(self, page) -> list[str]:
        # Kartlar aşağı kaydırıldıkça yüklenebildiği için sayfayı birkaç kez tarıyoruz.
        hrefs=[]
        last=-1
        for _ in range(12):
            try:
                hrefs = page.locator('a[href*="/tr/portfoy/P"]').evaluate_all("els => els.map(e => e.href || e.getAttribute('href'))")
            except Exception:
                hrefs=[]
            links=extract_remax_portfolio_links(hrefs,page.url)
            if len(links)==last: break
            last=len(links)
            try: page.mouse.wheel(0,1400); page.wait_for_timeout(250)
            except Exception: pass
        return links

    def _collect_emlakjet_links(self,page) -> list[str]:
        links=[]; stable=0; previous=-1
        for _ in range(40):
            try:
                hrefs=page.locator('a[href*="/ilan/"]').evaluate_all("els => els.map(e => e.href || e.getAttribute('href'))")
            except Exception:
                hrefs=[]
            links=extract_emlakjet_listing_links(hrefs,page.url)
            stable=stable+1 if len(links)==previous else 0
            previous=len(links)
            if stable>=3: break
            clicked=False
            for label in ("Daha Fazla","Daha fazla","Daha Fazla Göster"):
                try:
                    button=page.get_by_text(label,exact=True)
                    if button.count() and button.last.is_visible():
                        button.last.click(timeout=5000); clicked=True; page.wait_for_timeout(900); break
                except Exception: pass
            try:
                page.mouse.wheel(0,1800); page.wait_for_timeout(500 if clicked else 350)
            except Exception: pass
        return links

    def _collect_sahibinden_links(self,page) -> list[str]:
        try:
            hrefs=page.locator('a[href*="/ilan/"]').evaluate_all("els => els.map(e => e.href || e.getAttribute('href'))")
        except Exception:
            hrefs=[]
        return extract_sahibinden_listing_links(hrefs,page.url)

    def _open_remax_source(self,page,source_url):
        self.status.emit("RE/MAX portföyleri yükleniyor...")
        page.goto(source_url,wait_until="domcontentloaded",timeout=90000)
        page.bring_to_front(); page.wait_for_timeout(3500)
        if not self._ensure_not_blocked(page): raise RuntimeError("Tarama kullanıcı tarafından durduruldu.")

    def _next_remax_page(self,page,current_no:int) -> bool:
        # Önce Sonraki, yoksa bir sonraki sayfa numarası.
        for loc in [page.get_by_text("Sonraki",exact=True), page.get_by_role("button",name="Sonraki"), page.get_by_text(str(current_no+1),exact=True)]:
            try:
                if loc.count() and loc.last.is_visible():
                    before=page.url; loc.last.scroll_into_view_if_needed(); loc.last.click(timeout=10000); page.wait_for_timeout(1800)
                    return True
            except Exception: pass
        return False

    def _scan_remax_source(self, context, page, source_url: str) -> tuple[int, list[Listing]]:
        self._open_remax_source(page,source_url)
        total=extract_total_count(self._body_text(page))
        if not total:
            m=re.search(r"(\d+)\s*sonuç bulundu",self._body_text(page),re.I); total=int(m.group(1)) if m else 0
        all_links=[]; seen_links=set(); page_no=1
        while page_no<=100 and not self._stop.is_set():
            links=self._collect_remax_links(page)
            fresh=[u for u in links if u not in seen_links]
            for u in fresh: seen_links.add(u); all_links.append(u)
            self.status.emit(f"Sayfa {page_no}: {len(links)} portföy bulundu. Toplam {len(all_links)} link toplandı.")
            self.progress.emit(f"{len(all_links)} / {total or '?'}")
            if total and len(all_links)>=total: break
            if not self._next_remax_page(page,page_no): break
            page_no+=1
        if not all_links:
            raise RuntimeError("RE/MAX sayfasında portföy linki bulunamadı. Tarayıcı penceresi açık bırakıldı.")
        validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(all_links))

        rows=[]; seen_ids=set()
        for i,url in enumerate(all_links,1):
            if self._stop.is_set(): break
            self.status.emit(f"Portföy detayı okunuyor: {i} / {len(all_links)}")
            page.goto(url,wait_until="domcontentloaded",timeout=90000); page.wait_for_timeout(900)
            if not self._ensure_not_blocked(page): break
            text=self._body_text(page)
            item=parse_remax_detail(text=text,url=page.url,source_url=source_url)
            if not is_valid_detail_listing("remax",text,item,url):
                raise RuntimeError(f"MyRE/MAX ilan ayrıntısı doğrulanamadı ({i}/{len(all_links)}). Eski ilanlar korundu.")
            if item.listing_id not in seen_ids:
                seen_ids.add(item.listing_id); rows.append(item)
            self.progress.emit(f"{len(rows)} / {total or len(all_links)}")
        if not self._stop.is_set():
            validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(rows))
        return total,rows

    def _scan_emlakjet_source(self,context,page,source_url:str) -> tuple[int,list[Listing]]:
        self.status.emit("Emlakjet ofis ilanları yükleniyor...")
        page.goto(source_url,wait_until="domcontentloaded",timeout=90000)
        page.bring_to_front(); page.wait_for_timeout(3000)
        if not self._ensure_not_blocked(page): raise RuntimeError("Tarama kullanıcı tarafından durduruldu.")
        total=extract_emlakjet_total_count(self._body_text(page))
        all_links=[]; seen=set(); page_no=1
        while page_no<=20 and not self._stop.is_set():
            links=self._collect_emlakjet_links(page)
            for item in links:
                if item not in seen: seen.add(item); all_links.append(item)
            self.status.emit(f"Emlakjet: {len(all_links)} ilan linki bulundu.")
            self.progress.emit(f"{len(all_links)} / {total or '?'}")
            if total and len(all_links)>=total: break
            if not self._next_page(page): break
            page_no+=1
        if not all_links:
            raise RuntimeError("Emlakjet ofis sayfasında ilan linki bulunamadı.")
        validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(all_links))
        rows=[]; seen_ids=set()
        for i,listing_url in enumerate(all_links,1):
            if self._stop.is_set(): break
            self.status.emit(f"Emlakjet ilanı okunuyor: {i} / {len(all_links)}")
            page.goto(listing_url,wait_until="domcontentloaded",timeout=90000); page.wait_for_timeout(700)
            if not self._ensure_not_blocked(page): break
            title=self._first_text(page,["h1",'[class*="title"] h1'])
            text=self._body_text(page)
            item=parse_emlakjet_detail(text=text,url=page.url,source_url=source_url,title=title)
            if not is_valid_detail_listing("emlakjet",text,item,listing_url):
                raise RuntimeError(f"Emlakjet ilan ayrıntısı doğrulanamadı ({i}/{len(all_links)}). Eski ilanlar korundu.")
            if item.listing_id not in seen_ids:
                seen_ids.add(item.listing_id); rows.append(item)
            self.progress.emit(f"{len(rows)} / {total or len(all_links)}")
        if not self._stop.is_set():
            validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(rows))
        return total,rows

    def _scan_sahibinden_source(self,context,page,source_url:str) -> tuple[int,list[Listing]]:
        self._open_list(page,source_url)
        total=extract_total_count(self._body_text(page))
        all_links=[]; seen=set(); page_no=1
        while page_no<=100 and not self._stop.is_set():
            links=self._collect_sahibinden_links(page)
            for item in links:
                if item not in seen: seen.add(item); all_links.append(item)
            self.status.emit(f"Sahibinden sayfa {page_no}: toplam {len(all_links)} ilan linki bulundu.")
            self.progress.emit(f"{len(all_links)} / {total or '?'}")
            if total and len(all_links)>=total: break
            if not self._next_page(page): break
            page_no+=1
        if not all_links:
            raise RuntimeError("Sahibinden mağaza sayfasında ilan linki bulunamadı.")
        validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(all_links))
        rows=[]; seen_ids=set()
        for i,listing_url in enumerate(all_links,1):
            if self._stop.is_set(): break
            self.status.emit(f"Sahibinden ilanı okunuyor: {i} / {len(all_links)}")
            page.goto(listing_url,wait_until="domcontentloaded",timeout=90000); page.wait_for_timeout(700)
            if not self._ensure_not_blocked(page): break
            item,text=self._read_detail(page,source_url)
            if self._stop.is_set(): break
            if not is_valid_detail_listing("sahibinden",text,item,listing_url):
                raise RuntimeError(f"Sahibinden ilan ayrıntısı doğrulanamadı ({i}/{len(all_links)}). Eski ilanlar korundu.")
            if item and item.listing_id not in seen_ids:
                seen_ids.add(item.listing_id); rows.append(item)
            self.progress.emit(f"{len(rows)} / {total or len(all_links)}")
        if not self._stop.is_set():
            validate_scan_completeness(total=total,discovered=len(all_links),parsed=len(rows))
        return total,rows

    def _scan_source(self,context,page,source_url:str) -> tuple[int,list[Listing]]:
        platform=source_platform(source_url)
        if platform=="remax": return self._scan_remax_source(context,page,source_url)
        if platform=="emlakjet": return self._scan_emlakjet_source(context,page,source_url)
        if platform=="sahibinden": return self._scan_sahibinden_source(context,page,source_url)
        raise RuntimeError("Bu ilan kaynağı desteklenmiyor.")

    def _run(self, source_url: str) -> None:
        browser = None
        context = None
        try:
            from playwright.sync_api import sync_playwright
            source = source_key(source_url)
            with sync_playwright() as playwright:
                self.status.emit("Google Chrome for Testing açılıyor...")
                browser = playwright.chromium.launch(**browser_launch_options())
                context = self._new_context(browser)
                page = context.new_page()
                page.bring_to_front()
                time.sleep(1.0)  # Keep the visible window on screen before navigation begins.
                total, rows = self._scan_source(context, page, source_url)

                if self._stop.is_set():
                    self.status.emit("Tarama durduruldu. Eski ilanlar korundu.")
                    return
                validate_scan_completeness(total=total,discovered=total,parsed=len(rows))

                self._save_state(context)
                self.status.emit("Güncelleme tamamlandı.")
                self.done.emit(source, rows)
        except Exception as exc:
            self.failed.emit(str(exc))
            # Keep Chrome visible briefly on failure so the user can see what page caused it.
            if context is not None:
                try: time.sleep(8)
                except Exception: pass
        finally:
            if context is not None:
                try: self._save_state(context)
                except Exception: pass
                try: context.close()
                except Exception: pass
            if browser is not None:
                try: browser.close()
                except Exception: pass
            self._busy = False; self.busy_changed.emit(False)
