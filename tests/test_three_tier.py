from app.myanmar_text_normalizer import normalize_text
from app.menu_matcher import MenuMatcher
from app.order_parser import OrderParser


def test_normalize_does_not_force_half():
    assert normalize_text('အလက်ဖက်ရည်ချိုစိမ်း နှစ်ခွဲ အလာတာ သုံးခွဲ ပေး ပါ.') == 'လက်ဖက်ရည်ချိုစိမ်း နှစ်ခွဲ ပလာတာ သုံးခွဲ'


def test_exact_and_fuzzy():
    m=MenuMatcher()
    exact=m.search('နံပြားလွတ်')
    assert exact['tier']=='exact' and exact['candidates'][0]['id']=='ITEM159'
    fuzzy=m.search('နံပြားလွတ')
    assert fuzzy['candidates'] and fuzzy['candidates'][0]['id']=='ITEM159'


def test_multiple_menu_items_and_quantities():
    p=OrderParser()
    result=p.parse('နံပြားလွတ် နှစ်ပွဲ ပေါင်မုန့်မီးကင် သုံးပွဲ ပေးပါ')
    assert [(x['id'],x['qty']) for x in result['items']]==[('ITEM159',2),('ITEM608',3)]
    assert result['requires_confirmation']


def test_half_is_not_forced_to_cup():
    p=OrderParser()
    line=p.parse('နံပြားလွတ် နှစ်ခွဲ')['items'][0]
    assert line['qty'] is None and line['needs_review']


def test_unmatched_text_flagged():
    p=OrderParser()
    result=p.parse('နံပြားလွတ် နှစ်ပွဲ အမည်မသိ ၃ ပွဲ')
    assert result['unmatched_text']
