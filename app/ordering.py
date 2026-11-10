import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .config import ROOT, db_path

COUNT_WORDS = {'တစ်':1, 'တ':1, 'နှစ်':2, 'နှစ်ခု':2, 'သုံး':3, 'လေး':4, 'ငါး':5, 'ခြောက်':6, 'ခုနစ်':7, 'ရှစ်':8, 'ကိုး':9, 'ဆယ်':10}
UNITS = '(?:ခွက်|ပွဲ|ခု|ချပ်|လုံး|ထုပ်|စုံ)?'
NOTES = ('ချိုပေါ့', 'ချိုကျ', 'ပုံမှန်', 'အချိုလျှော့', 'သကြားမထည့်', 'အစပ်လျှော့', 'အစပ်များ', 'နို့ဆီပို', 'ပါဆယ်')
COUNT_RE = re.compile(r'(?<!\w)(\d{1,2}|'+ '|'.join(sorted(map(re.escape, COUNT_WORDS), key=len, reverse=True)) + r')\s*' + UNITS)

def menu():
    return json.loads((ROOT / 'data' / 'menu.json').read_text(encoding='utf-8'))

def get_quantity(text):
    matches = list(COUNT_RE.finditer(text))
    if not matches: return 1
    token = matches[0].group(1)
    return min(99, max(1, int(token) if token.isdecimal() else COUNT_WORDS[token]))

def parse_order(text, options=None):
    options = menu() if options is None else options
    # Candidate aliases longest-first to avoid counting overlapping aliases twice.
    candidates = []
    for item in options:
        for alias in sorted(set(item.get('aliases', []) + [item['name']]), key=len, reverse=True):
            for m in re.finditer(re.escape(alias), text, re.IGNORECASE):
                candidates.append((m.start(), m.end(), item, len(alias)))
    candidates.sort(key=lambda c: (c[0], -c[3]))
    matches = []
    for start, end, item, _ in candidates:
        if any(start < m[1] and end > m[0] for m in matches): continue
        matches.append((start, end, item))
    matches.sort(key=lambda c:c[0])
    result = []
    for i, (start, end, item) in enumerate(matches):
        prev_end = matches[i-1][1] if i else 0
        next_start = matches[i+1][0] if i+1 < len(matches) else len(text)
        # Quantity typically follows the item; do not take next item's quantity.
        trailing = text[end:next_start][:25]
        leading = text[max(prev_end,start-20):start]
        qty = get_quantity(trailing) if COUNT_RE.search(trailing) else get_quantity(leading)
        segment = text[max(prev_end,start-16):next_start]
        note = ', '.join(word for word in NOTES if word in segment)
        result.append({'id':item['id'], 'name':item['name'], 'qty':qty, 'price':int(item['price']), 'note':note})
    return result

def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, table_no TEXT NOT NULL, waiter TEXT NOT NULL, transcript TEXT NOT NULL, items_json TEXT NOT NULL, total INTEGER NOT NULL, status TEXT NOT NULL DEFAULT "new")')

def save_order(table_no, waiter, transcript, items):
    catalog = {x['id']:x for x in menu()}
    validated = []
    for x in items:
        item = catalog.get(x['id'])
        if item is None: raise ValueError('Unknown menu item')
        qty = int(x['qty'])
        if not 1 <= qty <= 99: raise ValueError('Quantity must be 1–99')
        validated.append({'id':item['id'],'name':item['name'],'qty':qty,'price':item['price'],'note':str(x.get('note',''))[:200]})
    if not validated: raise ValueError('Cannot submit an empty order')
    if not str(table_no).strip(): raise ValueError('Table is required')
    total = sum(x['qty']*x['price'] for x in validated)
    with connect() as conn:
        cur = conn.execute('INSERT INTO orders(created_at,table_no,waiter,transcript,items_json,total,status) VALUES (?,?,?,?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(),str(table_no)[:32],str(waiter)[:80],str(transcript)[:2000],json.dumps(validated,ensure_ascii=False),total,'new'))
        return cur.lastrowid

def list_orders(limit=100):
    with connect() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT ?', (limit,))]

def update_status(order_id, status):
    if status not in {'new','preparing','served'}: raise ValueError('Invalid status')
    with connect() as conn:
        cur = conn.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))
        if cur.rowcount == 0: raise ValueError('Order not found')
