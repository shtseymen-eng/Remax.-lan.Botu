from __future__ import annotations
import re
from dataclasses import dataclass
TR=str.maketrans("çÇğĞıİöÖşŞüÜ","ccggiioossuu")
def norm(s:str)->str:
    return re.sub(r"\s+"," ",(s or "").translate(TR).casefold()).strip()
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
def source_label(url): return url or ''
def search(items,query):
    ts=[t for t in norm(query).split() if t]
    if not ts:return items
    out=[]
    for x in items:
        hay=norm(' '.join([x.title,x.advisor,x.phone,x.price,x.location,x.rooms,x.transaction_type,x.property_type,x.sqm,x.listing_date,source_label(x.source_url)]))
        if all(t in hay for t in ts): out.append(x)
    return out
