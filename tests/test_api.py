import os
import io
import wave
from fastapi.testclient import TestClient
os.environ['API_KEY']='testing-key'
from api import app
client=TestClient(app)
HEADERS={'X-API-Key':'testing-key'}

def test_protected():
    assert client.get('/api/menu').status_code==401
    assert client.get('/api/menu',headers=HEADERS).status_code==200

def test_parse():
    r=client.post('/api/parse',headers=HEADERS,json={'text':'နံပြားလွတ် နှစ်ပွဲ ပေါင်မုန့်မီးကင် သုံးပွဲ'})
    assert r.status_code==200
    assert [(x['id'],x['qty']) for x in r.json()['items']]==[('ITEM159',2),('ITEM608',3)]

def test_upload_without_raj(monkeypatch):
    monkeypatch.setattr('api.transcribe_wav',lambda wav:'လက်ဖက်ရည် နှစ်ခွက်')
    b=io.BytesIO()
    with wave.open(b,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\x00\x00'*16000)
    r=client.post('/api/asr',headers=HEADERS,files={'file':('test.wav',b.getvalue(),'audio/wav')})
    assert r.status_code==200 and r.json()['text']=='လက်ဖက်ရည် နှစ်ခွက်'
