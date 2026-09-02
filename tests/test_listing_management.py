import pytest

from remax_bot.core import DB, Listing, split_listings_by_site
from remax_bot import core, importer


def test_excel_export_round_trip_keeps_both_offices_in_the_selected_platform(tmp_path):
    rows = [
        Listing(
            "P1", "Çarşı ilanı", "https://remax.com.tr/tr/portfoy/P1",
            "Ali Rıza Akıllı", "0532 111 22 33", "4.000.000 TL", "İzmit",
            "3+1", "Satılık", "Daire", "120 m²", "01.09.2026",
            "https://remax.com.tr/tr/ofis/detay/carsi",
        ),
        Listing(
            "P2", "Çarşı 2 ilanı", "https://remax.com.tr/tr/portfoy/P2",
            "Ayşe Şen", "", "35.000 TL", "Başiskele", "2+1", "Kiralık",
            "Daire", "90 m²", "02.09.2026",
            "https://remax.com.tr/tr/ofis/detay/carsi-2",
        ),
        Listing(
            "E1", "Emlakjet ilanı", "https://www.emlakjet.com/ilan/e-1",
            source_url="https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566",
        ),
    ]
    selected = split_listings_by_site(rows)["MyRE/MAX"]
    output = tmp_path / "myremax.xlsx"

    assert hasattr(importer, "write_list_file"), "Excel dışa aktarma henüz yok"
    importer.write_list_file(output, selected)
    imported = importer.read_list_file(output)

    assert [(x.listing_id, x.title, x.advisor, x.source_url) for x in imported] == [
        ("P1", "Çarşı ilanı", "Ali Rıza Akıllı", "https://remax.com.tr/tr/ofis/detay/carsi"),
        ("P2", "Çarşı 2 ilanı", "Ayşe Şen", "https://remax.com.tr/tr/ofis/detay/carsi-2"),
    ]


def test_listing_update_can_correct_fields_and_identity_without_leaving_a_duplicate(tmp_path):
    db = DB(tmp_path / "edit.sqlite")
    source = "https://remax.com.tr/tr/ofis/detay/carsi"
    db.add_one(Listing("old", "Yanlış başlık", "https://x/old", advisor="Yanlış İsim", source_url=source))
    corrected = Listing(
        "new", "Doğru başlık", "https://x/new", advisor="Doğru İsim",
        price="5.000.000 TL", source_url=source,
    )

    db.update_listing(source, "old", corrected)

    assert db.count() == 1
    assert db.all() == [corrected]


def test_listing_update_rejects_an_identity_collision_without_losing_either_row(tmp_path):
    db = DB(tmp_path / "edit-collision.sqlite")
    source = "https://remax.com.tr/tr/ofis/detay/carsi"
    first = Listing("a", "Birinci", "https://x/a", source_url=source)
    second = Listing("b", "İkinci", "https://x/b", source_url=source)
    db.upsert([first, second])

    with pytest.raises(ValueError, match="başka bir ilan"):
        db.update_listing(source, "a", Listing("b", "Düzeltilen", "https://x/a", source_url=source))

    assert db.count() == 2
    assert {(x.listing_id, x.title) for x in db.all()} == {("a", "Birinci"), ("b", "İkinci")}


def test_editing_an_unrelated_field_keeps_raw_advisor_for_later_unmerge(tmp_path):
    db = DB(tmp_path / "edit-alias.sqlite")
    source = "https://remax.com.tr/tr/ofis/detay/carsi"
    db.add_one(Listing("1", "Eski başlık", "https://x/1", advisor="Rıza Akıllı", source_url=source))
    db.merge_advisors(["Ali Rıza Akıllı", "Rıza Akıllı"], "Ali Rıza Akıllı")

    raw = db.raw_listing(source, "1")
    db.update_listing(source, "1", core.update_listing_fields(raw, {"title": "Yeni başlık"}))
    db.unmerge_advisor("Ali Rıza Akıllı")

    assert db.all()[0].title == "Yeni başlık"
    assert db.all()[0].advisor == "Rıza Akıllı"


def test_listing_editor_returns_all_corrected_fields():
    assert hasattr(core, "update_listing_fields"), "İlan düzenleme modeli henüz yok"
    original = Listing(
        "1", "Yanlış", "https://x/1", "Yanlış İsim", "0500", "100 TL",
        "İzmit", "1+1", "Kiralık", "Daire", "50 m²", "01.01.2026",
        "https://remax.com.tr/tr/ofis/detay/carsi",
    )
    edited = core.update_listing_fields(original, {
        "title": " Doğru Başlık ",
        "advisor": "Doğru İsim",
        "property_type": "Ofis",
    })

    assert edited.title == "Doğru Başlık"
    assert edited.advisor == "Doğru İsim"
    assert edited.property_type == "Ofis"
    assert edited.listing_id == "1"
    assert edited.source_url == "https://remax.com.tr/tr/ofis/detay/carsi"
