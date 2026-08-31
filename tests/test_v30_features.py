import remax_bot.importer as importer
from remax_bot.core import Listing
from remax_bot.whatsapp_state import ActivationGate

def sample():
    return [
        Listing("1","Kiralık","u1","Murat Şenoğlu","","55000 TL","İzmit","3+1","Kiralık","Daire","120","","remax"),
        Listing("2","Satılık","u2","Portföy No","","4000000 TL","İzmit","2+1","Satılık","Daire","90","","remax"),
        Listing("3","Satılık","u3","Mustafa Mert Yılmaz","","4250000 TL","Başiskele","3+1","Satılık","Daire","130","","remax"),
        Listing("4","Satılık","u4","Kocaeli / İzmit","","3500000 TL","İzmit","2+1","Satılık","Daire","95","","remax"),
    ]

def test_single_hash_command_is_accepted():
    cmd=importer.parse_command("#izmit kiralık 55 bin")
    assert cmd["type"]=="search"
    assert cmd["target_price"]==55000
    assert cmd["query"]=="izmit kiralık"

def test_legacy_double_hash_still_works():
    assert importer.parse_command("#danışmanlar#")["type"]=="advisors"

def test_activation_gate_uses_max_start_stop():
    gate=ActivationGate()
    assert gate.handle("#Max başla")[0]=="started"
    assert gate.handle("#izmit kiralık")[0]=="query"
    assert gate.handle("#Max durdur")[0]=="stopped"

def test_advisor_list_uses_real_names_and_rejects_page_noise():
    assert hasattr(importer,"advisor_names")
    assert importer.advisor_names(sample())==["Murat Şenoğlu","Mustafa Mert Yılmaz"]

def test_listing_filter_combines_advisor_and_price():
    assert hasattr(importer,"filter_listings")
    rows=importer.filter_listings(sample(),advisor="Murat Şenoğlu",max_price=60000)
    assert [x.listing_id for x in rows]==["1"]
