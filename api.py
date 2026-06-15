import aiohttp
from config import API_KEY

async def shorten(url, alias=None):
    try:
        params = {"api": API_KEY, "url": url, "format": "json"}
        if alias:
            params["alias"] = alias
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            r = await s.get("https://shrinkearn.com/api", params=params)
            d = await r.json()
            if d.get("status") == "success":
                return d.get("shortenedUrl")
            return None
    except:
        return None

async def stats(url):
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            r = await s.get("https://shrinkearn.com/api", params={
                "api": API_KEY, "url": url, "format": "json", "action": "stats"
            })
            d = await r.json()
            if d.get("status") == "success":
                earned = d.get("earned")
                if earned is not None:
                    return float(earned)
    except:
        return None
    return None