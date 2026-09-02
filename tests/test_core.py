from remax_bot.core import norm,source_key,source_label,source_site,split_listings_by_site,DB,Listing,search

def test_normalize():
    assert norm("İzmit Kiralık")=="izmit kiralik"

def test_source_key():
    assert source_key("https://X.sahibinden.com/?display=list")=="https://x.sahibinden.com/"

def test_labels():
    assert source_label("https://carsigayrimenkulkocaeli.sahibinden.com/")=="Sahibinden ÇARŞI"
    assert source_label("https://remaxcarsi2.sahibinden.com/")=="Sahibinden ÇARŞI 2"
    assert source_label("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566")=="Emlakjet ÇARŞI"
    assert source_label("https://remax.com.tr/tr/ofis/detay/carsi")=="MyRE/MAX ÇARŞI"

def test_source_site_uses_source_and_falls_back_to_listing_link():
    assert source_site("https://remax.com.tr/tr/ofis/detay/carsi") == "MyRE/MAX"
    assert source_site("https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566") == "Emlakjet"
    assert source_site("https://carsigayrimenkulkocaeli.sahibinden.com/") == "Sahibinden"
    assert source_site("manual://entry", "https://www.emlakjet.com/ilan/test-19754937") == "Emlakjet"

def test_split_listings_keeps_unclassified_imports_visible():
    rows=[
        Listing("1","Site ilanı","https://www.emlakjet.com/ilan/test-19754937",source_url="excel://import"),
        Listing("2","Kaynağı belirsiz","",source_url="excel://import"),
    ]
    buckets=split_listings_by_site(rows)
    assert [x.listing_id for x in buckets["Emlakjet"]] == ["1"]
    assert [x.listing_id for x in buckets["Diğer"]] == ["2"]

def test_replace_source_keeps_other(tmp_path):
    db=DB(tmp_path/"x.sqlite")
    a="https://carsigayrimenkulkocaeli.sahibinden.com/"
    b="https://remaxcarsi2.sahibinden.com/"
    db.replace_source(a,[Listing("1","A","u1",advisor="Ayşe",phone="0532 111 22 33",source_url=a)])
    db.replace_source(b,[Listing("2","B","u2",source_url=b)])
    db.replace_source(a,[Listing("3","C","u3",source_url=a)])
    assert db.count()==2 and db.source_count(a)==1 and db.source_count(b)==1

def test_search_phone():
    assert len(search([Listing("1","A","u",phone="0532 111 22 33")],"0532"))==1


def test_advisor_aliases_merge_selected_names_without_merging_the_same_surname(tmp_path):
    db=DB(tmp_path/"aliases.sqlite")
    source="https://remax.com.tr/tr/ofis/detay/carsi"
    db.upsert([
        Listing("1","A","u1",advisor="Hamza Aybars Yıldız",source_url=source),
        Listing("2","B","u2",advisor="H. Aybars Yıldız",source_url=source),
        Listing("3","C","u3",advisor="Mehmet Yıldız",source_url=source),
    ])

    db.merge_advisors(
        ["Hamza Aybars Yıldız","H. Aybars Yıldız"],
        "Hamza Aybars Yıldız",
    )

    assert [x.advisor for x in db.all()] == [
        "Hamza Aybars Yıldız",
        "Hamza Aybars Yıldız",
        "Mehmet Yıldız",
    ]


def test_advisor_alias_rule_applies_to_future_scans_and_can_be_removed(tmp_path):
    db=DB(tmp_path/"future-alias.sqlite")
    source="https://www.emlakjet.com/emlak-ofisleri/remax-carsi-1662566"
    db.merge_advisors(["Ali Rıza Akıllı","Rıza Akıllı"],"Ali Rıza Akıllı")
    db.upsert([
        Listing("1","A","u1",advisor="Rıza Akıllı",source_url=source),
    ])

    assert db.all()[0].advisor == "Ali Rıza Akıllı"
    assert db.raw_advisor_names() == ["Rıza Akıllı"]

    db.unmerge_advisor("Ali Rıza Akıllı")

    assert db.all()[0].advisor == "Rıza Akıllı"


def test_reversing_and_extending_an_alias_group_does_not_create_a_cycle(tmp_path):
    db=DB(tmp_path/"alias-cycle.sqlite")
    source="https://remax.com.tr/tr/ofis/detay/carsi"
    db.upsert([
        Listing("1","A","u1",advisor="A Bir",source_url=source),
        Listing("2","B","u2",advisor="B Bir",source_url=source),
        Listing("3","C","u3",advisor="C Bir",source_url=source),
    ])
    db.merge_advisors(["A Bir","B Bir"],"A Bir")
    db.merge_advisors(["A Bir","C Bir"],"C Bir")
    assert {x.advisor for x in db.all()} == {"C Bir"}

    db.merge_advisors(["C Bir","A Bir"],"A Bir")

    assert {x.advisor for x in db.all()} == {"A Bir"}
    assert {canonical for _alias,canonical in db.advisor_aliases()} == {"A Bir"}


def test_hyphenated_alternatives_find_either_property_type_without_partial_word_matches():
    rows=[
        Listing("1","Kiralık Dükkan","u1",transaction_type="Kiralık",property_type="Dükkan"),
        Listing("2","Satılık Ofis","u2",transaction_type="Satılık",property_type="Ofis"),
        Listing("3","Devren Arsa","u3",transaction_type="Devren",property_type="Arsa"),
        Listing("4","Satılık Daire","u4",transaction_type="Satılık",property_type="Daire"),
    ]

    assert [x.listing_id for x in search(rows,"dükkan-ofis")] == ["1","2"]
    assert [x.listing_id for x in search(rows,"ev-daire")] == ["4"]
