import os, logging, asyncio
logger = logging.getLogger(__name__)

class AudioSeparator:
    def __init__(self):
        self.temp = "temp_audio"
        os.makedirs(self.temp, exist_ok=True)

    async def separate(self, audio_path):
        return None, "❌ الخدمة غير متوفرة حالياً"