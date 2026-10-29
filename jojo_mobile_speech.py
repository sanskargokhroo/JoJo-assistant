"""Phone playback uses the laptop-selected voice without playing on the laptop."""
import tempfile
from pathlib import Path
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

class SpeechRequest(BaseModel):
    text: str = Field(min_length=1,max_length=3000)

def register(app,core,authenticate):
    @app.post('/api/mobile/speech')
    def mobile_speech(req: SpeechRequest,request: Request):
        authenticate(request)
        from jojo_workspace import private_session
        if private_session():
            raise HTTPException(409,'Selected online voice is unavailable in a private session. Text remains available.')
        from jojo_dialogue import speech_text
        text=speech_text(req.text)
        if not text:raise HTTPException(422,'No speakable text')
        # No phone speech cache: temporary content is removed on both success and failure.
        with tempfile.TemporaryDirectory(prefix='jojo-phone-speech-') as folder:
            target=Path(folder)/'speech.mp3'
            try:
                if not core.synthesize_sync(text,str(target)) or not target.is_file():
                    raise HTTPException(503,'Selected voice unavailable; no alternative voice was used.')
                audio=target.read_bytes()
                if not 400<len(audio)<=5_000_000:raise ValueError('Invalid audio size')
            except HTTPException:raise
            except Exception as exc:
                raise HTTPException(503,'Selected voice unavailable; no alternative voice was used.') from exc
        return Response(audio,media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-JoJo-Voice':core.VOICE_PARAMS['voice']})
