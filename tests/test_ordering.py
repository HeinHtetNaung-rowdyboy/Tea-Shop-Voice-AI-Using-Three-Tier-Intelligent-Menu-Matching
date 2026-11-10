from app.ordering import menu, save_order
from app.order_parser import OrderParser


def test_real_catalog():
    catalog=menu()
    assert len(catalog)>=150
    assert any(x["id"]=="ITEM159" for x in catalog)


def test_burmese_order():
    cart=OrderParser().parse("နံပြားလွတ် နှစ်ပွဲ ပေါင်မုန့်မီးကင် သုံးပွဲ")["items"]
    assert [(x["id"],x["qty"]) for x in cart]==[("ITEM159",2),("ITEM608",3)]


def test_digit_quantities():
    cart=OrderParser().parse("နံပြားလွတ် ၂ ပွဲ ပေါင်မုန့်မီးကင် ၁ ပွဲ")["items"]
    assert [(x["id"],x["qty"]) for x in cart]==[("ITEM159",2),("ITEM608",1)]
