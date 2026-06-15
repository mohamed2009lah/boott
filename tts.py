import os, logging, asyncio
from gtts import gTTS
logger = logging.getLogger(__name__)

VOICES = {
    'ar_female': {'lang': 'ar', 'tld': 'com'},
    'ar_male': {'lang': 'ar', 'tld': 'com'},
    'en_female': {'lang': 'en', 'tld': 'co.uk'},
    'en_male': {'lang': 'en', 'tld': 'com'},
    'en_us_female': {'lang': 'en', 'tld': 'us'},
    'en_us_male': {'lang': 'en', 'tld': 'us'},
}

class TextToSpeech:
    def __init__(self):
        self.temp = "temp_tts"
        os.makedirs(self.temp, exist_ok=True)

    async def convert(self, text, voice='ar_female', speed='normal'):
        path = None
        if len(text) > 500:
            return None, "❌ النص أطول من 500 حرف"
        v = VOICES.get(voice, VOICES['ar_female'])
        slow = speed == 'slow'
        out = os.path.join(self.temp, f"tts_{os.urandom(4).hex()}.mp3")
        try:
            tts = gTTS(text=text, lang=v['lang'], tld=v['tld'], slow=slow)
            await asyncio.get_event_loop().run_in_executor(None, lambda: tts.save(out))
            if os.path.exists(out):
                return out, None
            return None, "❌ فشل"
        except Exception as e:
            logger.error(f"TTS: {e}")
            return None, str(e)