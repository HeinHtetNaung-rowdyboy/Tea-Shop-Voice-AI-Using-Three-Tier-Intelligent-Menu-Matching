import io
import wave
from app.raj_client import validate_wav, transcribe_wav

def audio():
    b=io.BytesIO()
    with wave.open(b,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
    return b.getvalue()

def test_audio_validation():
    assert validate_wav(audio())==1

def test_real_request_shape(monkeypatch):
    seen={}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'text':'လက်ဖက်ရည်'}
    def fake_post(url,**kwargs):
        seen.update({'url':url,**kwargs});return Response()
    monkeypatch.setattr('app.raj_client.requests.post',fake_post)
    assert transcribe_wav(audio())=='လက်ဖက်ရည်'
    assert seen['data']['language']=='my-MM'
    assert seen['url'].endswith('/v1/audio/transcriptions')
