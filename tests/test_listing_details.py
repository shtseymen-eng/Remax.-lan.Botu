import sqlite3

from remax_bot.core import DB, Listing, search
from remax_bot.listing_details import display_address, normalize_details


def test_display_address_uses_only_known_components_and_prefers_explicit_address():
    partial = Listing(
        "1",
        "Daire",
        "https://example.test/1",
        province="Kocaeli",
        district="İzmit",
        neighborhood="Yahya Kaptan",
        complex_name="Zeray Sitesi",
    )
    explicit = Listing(
        "2",
        "Villa",
        "https://example.test/2",
        province="Kocaeli",
        district="Başiskele",
        full_address="Fatih Mah. Gülümser Sok. No: 4",
    )

    assert display_address(partial) == "Kocaeli / İzmit / Yahya Kaptan / Zeray Sitesi"
    assert "Sokak" not in display_address(partial)
    assert display_address(explicit) == "Fatih Mah. Gülümser Sok. No: 4"


def test_normalize_details_cleans_whitespace_and_drops_empty_entries():
    assert normalize_details({" Isıtma ": " Doğalgaz  Kombi ", "Boş": "", "": "değer"}) == {
        "Isıtma": "Doğalgaz Kombi"
    }
    assert normalize_details('{"Bulunduğu Kat": " 3 ", "Otopark": " Açık "}') == {
        "Bulunduğu Kat": "3",
        "Otopark": "Açık",
    }
    assert normalize_details("{bozuk") == {}


def test_search_uses_description_and_dynamic_details_only_when_enabled():
    rows = [
        Listing(
            "1",
            "Satılık Daire",
            "https://example.test/1",
            description="Kesintisiz deniz manzaralı",
            details={"Isıtma": "Doğalgaz Kombi", "Bulunduğu Kat": "3"},
        )
    ]

    assert search(rows, "deniz") == rows
    assert search(rows, "doğalgaz") == rows
    assert search(rows, "deniz", fields={"title"}) == []
    assert search(rows, "doğalgaz", fields={"description"}) == []
    assert search(rows, "doğalgaz", fields={"details"}) == rows


def test_existing_database_schema_is_extended_without_losing_rows(tmp_path):
    path = tmp_path / "legacy-current.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """create table listings(
                source_url text not null,id text not null,title text not null,url text not null,
                advisor text not null default '',phone text not null default '',price text not null default '',
                location text not null default '',rooms text not null default '',trans text not null default '',
                ptype text not null default '',sqm text not null default '',listing_date text not null default '',
                primary key(source_url,id))"""
        )
        connection.execute(
            "insert into listings values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "https://shop.sahibinden.com/",
                "123",
                "Eski İlan",
                "https://www.sahibinden.com/ilan/x-123/detay",
                "Ayşe Yılmaz",
                "0532 111 22 33",
                "5.000.000 TL",
                "Kocaeli / İzmit",
                "3+1",
                "Satılık",
                "Daire",
                "145 m²",
                "26 Ağustos 2026",
            ),
        )

    db = DB(path)
    [item] = db.all()

    assert item.title == "Eski İlan"
    assert item.advisor == "Ayşe Yılmaz"
    assert item.province == ""
    assert item.details == {}


def test_database_round_trip_preserves_new_fields_and_tolerates_bad_details_json(tmp_path):
    path = tmp_path / "details.sqlite"
    db = DB(path)
    source = "https://carsigayrimenkulkocaeli.sahibinden.com/"
    item = Listing(
        "1234567890",
        "Site İçinde Daire",
        "https://www.sahibinden.com/ilan/x-1234567890/detay",
        location="Kocaeli / İzmit / Yahya Kaptan",
        sqm="145 m²",
        source_url=source,
        province="Kocaeli",
        district="İzmit",
        neighborhood="Yahya Kaptan",
        street="Akasyalar Caddesi",
        complex_name="Zeray Sitesi",
        full_address="Yahya Kaptan Mah. Akasyalar Cad. No: 10",
        description="Ara kat satılık daire",
        net_sqm="130 m²",
        details={"Isıtma": "Doğalgaz Kombi", "Otopark": "Kapalı"},
    )

    db.upsert([item])

    assert db.all() == [item]
    with db.connect() as connection:
        connection.execute(
            "update listings set details_json=? where source_url=? and id=?",
            ("{bozuk", source, item.listing_id),
        )

    [recovered] = db.all()
    assert recovered.title == item.title
    assert recovered.province == "Kocaeli"
    assert recovered.details == {}
