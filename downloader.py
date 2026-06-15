import os, logging, asyncio, yt_dlp
from urllib.parse import urlparse
logger = logging.getLogger(__name__)

SUPPORTED = ["youtube.com","youtu.be","facebook.com","fb.watch","instagram.com","twitter.com","x.com","tiktok.com"]

class VideoDownloader:
    def __init__(self):
        self.temp = "temp_downloads"
        os.makedirs(self.temp, exist_ok=True)

    def is_supported(self, url):
        domain = urlparse(url).netloc.lower()
        return any(s in domain for s in SUPPORTED)

    async def get_info(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                return {'title': info.get('title', '?'), 'duration': info.get('duration', 0), 'uploader': info.get('uploader', '?')}
        except:
            return None

    async def download(self, url, quality='best'):
        path = None
        try:
            name = f"vid_{os.urandom(4).hex()}"
            fmt = {'best': 'best[height<=1080]', '720': 'best[height<=720]', '480': 'best[height<=480]', '360': 'best[height<=360]', 'audio': 'bestaudio/best'}
            out_template = os.path.join(self.temp, f"{name}.%(ext)s")
            opts = {'format': fmt.get(quality, 'best'), 'outtmpl': out_template, 'quiet': True}
            if quality == 'audio':
                opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
            with yt_dlp.YoutubeDL(opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.download([url]))
            for f in os.listdir(self.temp):
                if f.startswith(name):
                    path = os.path.join(self.temp, f)
                    return path
            return None
        except Exception as e:
            logger.error(f"Download: {e}")
            return None