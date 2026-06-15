import os, random, logging
from db import get_conn
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

class AdsSystem:
    def __init__(self):
        self.telega_key = os.getenv("TELEGA_API_KEY", "")
        self.adtractor_key = os.getenv("ADTRACTOR_API_KEY", "")
        self.adsgram_key = os.getenv("ADSGRAM_API_KEY", "")

        self.manual_ads = [
            {'id':1,'text':"📢 **إعلان ممول**\n\n🎯 **عرض خاص!**\nاربح 50$ يومياً من اختصار الروابط\nسجل الآن: https://example.com",'weight':5},
            {'id':2,'text':"📢 **إعلان ممول**\n\n📢 **فرصة ذهبية!**\nتعلم الربح من الإنترنت مجاناً\nانضم الآن: https://example.com",'weight':3},
            {'id':3,'text':"📢 **إعلان ممول**\n\n💎 **خصم 20%** على أول عملية شراء نقاط\nاستخدم الكود: WELCOME20",'weight':4},
            {'id':4,'text':"📢 **إعلان ممول**\n\n🚀 **طور بوتك الخاص** مع أفضل المبرمجين\nللتواصل: @DevSupport",'weight':3},
            {'id':5,'text':"📢 **إعلان ممول**\n\n📊 **إحصائيات مذهلة:**\nأكثر من 10,000 مستخدم يربحون يومياً\nانضم للربح الآن!",'weight':2},
        ]
        self.referral_message = (
            "🔗 **هل تريد استخدام هذه الخدمة مجاناً؟**\n\n"
            "👥 ادعُ صديقاً واحداً لتحصل على نقاط مجانية!\n"
            "⭐ كل صديق يشاهد الإعلان = 5 نقاط للخدمات\n\n"
            "استخدم /invite للحصول على رابط الدعوة"
        )

    def init_tables(self): pass

    async def _fetch_ad_from_telega(self, user_id):
        if not self.telega_key: return None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get("https://api.telega.io/v1/ad", params={
                    "token": self.telega_key, "user_id": str(user_id)
                }) as r:
                    data = await r.json()
                    if data.get("success"):
                        return data.get("text") or data.get("message")
        except Exception as e:
            logger.warning(f"Telega.io failed: {e}")
        return None

    async def _fetch_ad_from_adtractor(self, user_id):
        if not self.adtractor_key: return None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get("https://api.adtractor.io/v1/ad", params={
                    "token": self.adtractor_key, "user_id": str(user_id)
                }) as r:
                    data = await r.json()
                    if data.get("status") == "ok":
                        return data.get("ad", {}).get("text", "")
        except Exception as e:
            logger.warning(f"AdTractor failed: {e}")
        return None

    async def _fetch_ad_from_adsgram(self, user_id):
        if not self.adsgram_key: return None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get("https://api.adsgram.com/v1/ad", params={
                    "token": self.adsgram_key, "user_id": str(user_id)
                }) as r:
                    data = await r.json()
                    if data.get("status") == "success":
                        return data.get("ad_text") or data.get("message")
        except Exception as e:
            logger.warning(f"AdsGram failed: {e}")
        return None

    async def _get_ad_from_platforms(self, user_id):
        ad = await self._fetch_ad_from_telega(user_id)
        if ad: return ad
        ad = await self._fetch_ad_from_adtractor(user_id)
        if ad: return ad
        ad = await self._fetch_ad_from_adsgram(user_id)
        if ad: return ad
        return None

    async def show_ad(self, user_id, service):
        ad_text = await self._get_ad_from_platforms(user_id)
        if not ad_text:
            ad_text = self._get_random_manual_ad()['text']
        self._log_view(user_id, 0, service)
        return ad_text

    def show_referral_ad(self, new_user_id, referrer_id):
        ad = self._get_random_manual_ad()
        self._log_view(new_user_id, ad['id'], 'referral')
        c = get_conn().cursor()
        c.execute("UPDATE referral_tracking SET ad_watched=1 WHERE new_user_id=? AND referrer_id=? AND ad_watched=0",
                  (new_user_id, referrer_id))
        if c.rowcount > 0:
            c.execute("UPDATE referral_tracking SET points_awarded=1 WHERE new_user_id=? AND referrer_id=?",
                      (new_user_id, referrer_id))
            c.execute("UPDATE users SET referrals_watched_ads=referrals_watched_ads+1 WHERE user_id=?", (referrer_id,))
            from points import points_system
            points_system.add_referral_points(referrer_id)
        c.connection.commit()
        c.connection.close()
        return ad['text']

    def _get_random_manual_ad(self):
        total = sum(a['weight'] for a in self.manual_ads)
        r = random.uniform(0, total)
        upto = 0
        for a in self.manual_ads:
            if upto + a['weight'] >= r:
                return a
            upto += a['weight']
        return self.manual_ads[0]

    def _log_view(self, user_id, ad_id, service):
        try:
            c = get_conn().cursor()
            c.execute("INSERT INTO ad_views(user_id, ad_id, service, viewed_at) VALUES(?,?,?,?)",
                      (user_id, ad_id, service, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.connection.commit()
            c.connection.close()
        except: pass

    def should_show_referral(self, user_id):
        c = get_conn().cursor()
        c.execute("SELECT referrals_count FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        return not row or row[0] == 0

    def get_daily_ad_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        c = get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM ad_views WHERE viewed_at>=?", (today,))
        today_views = c.fetchone()[0]
        c.execute("SELECT ad_id, COUNT(*) FROM ad_views WHERE viewed_at>=? GROUP BY ad_id", (today,))
        today_by_ad = c.fetchall()
        c.execute("SELECT service, COUNT(*) FROM ad_views WHERE viewed_at>=? GROUP BY service", (today,))
        today_by_service = c.fetchall()
        c.connection.close()
        return today_views, today_by_ad, today_by_service

    def get_total_ad_stats(self):
        c = get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM ad_views")
        total_views = c.fetchone()[0]
        c.execute("SELECT ad_id, COUNT(*) FROM ad_views GROUP BY ad_id")
        total_by_ad = c.fetchall()
        c.execute("SELECT service, COUNT(*) FROM ad_views GROUP BY service")
        total_by_service = c.fetchall()
        c.execute("SELECT COUNT(*) FROM referral_tracking")
        total_ref = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE ad_watched=1")
        watched = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE points_awarded=1")
        awarded = c.fetchone()[0]
        c.connection.close()
        return {'total_views':total_views,'total_by_ad':total_by_ad,'total_by_service':total_by_service,'total_referrals':total_ref,'watched_referrals':watched,'awarded_referrals':awarded}

    def add_manual_ad(self, text, weight=3):
        new_id = max([a['id'] for a in self.manual_ads], default=0)+1
        self.manual_ads.append({'id':new_id,'text':text,'weight':weight})
        return new_id

    def remove_manual_ad(self, ad_id):
        self.manual_ads = [a for a in self.manual_ads if a['id']!=ad_id]
        return True

    def get_all_manual_ads(self):
        return self.manual_ads

ads_system = AdsSystem()