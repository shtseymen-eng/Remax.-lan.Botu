from __future__ import annotations


DEFAULT_SEARCH_SOURCES=("Sahibinden","Emlakjet","MyRE/MAX")
DEFAULT_SEARCH_FIELDS=(
    "title","advisor","phone","price","location","rooms","transaction_type",
    "property_type","sqm","listing_date","description","details",
)
SEARCH_FIELD_LABELS={
    "title":"Başlık",
    "advisor":"Danışman",
    "phone":"Telefon",
    "price":"Fiyat",
    "location":"Adres / Konum",
    "rooms":"Oda",
    "transaction_type":"Satılık / Kiralık",
    "property_type":"Emlak Türü",
    "sqm":"Brüt / Net m²",
    "listing_date":"İlan Tarihi",
    "description":"İlan Açıklaması",
    "details":"Ek Özellikler",
}


def normalize_command_prefix(value) -> str:
    prefix=str(value or "").strip()
    return prefix if len(prefix)==1 and not prefix.isspace() and prefix.isprintable() else "#"


def _normalize_selected(value,allowed,default):
    if not isinstance(value,(list,tuple,set)):
        return list(default)
    selected=[]
    for item in value:
        if item in allowed and item not in selected:
            selected.append(item)
    return selected


def normalize_search_sources(value):
    return _normalize_selected(value,DEFAULT_SEARCH_SOURCES,DEFAULT_SEARCH_SOURCES)


def normalize_search_fields(value):
    return _normalize_selected(value,DEFAULT_SEARCH_FIELDS,DEFAULT_SEARCH_FIELDS)
