from points import points_system
from ads import ads_system

class Middleware:
    def __init__(self):
        self.free_services = ['help','start','balance','referral','withdraw','buy_points','points','daily','invite']

    async def check_and_process(self, user_id, service, context):
        """تتحقق من الرصيد وتعرض إعلان، ولكن لا تخصم النقاط (الخصم يحدث بعد النجاح)"""
        if service in self.free_services:
            return True, None, True, 0
        cost = points_system.get_service_cost(service)
        bal = points_system.get_balance(user_id)
        if bal < cost:
            if ads_system.should_show_referral(user_id):
                msg = ads_system.referral_message + f"\n\n⭐ تحتاج {cost} نقطة | رصيدك: {bal}"
                return False, msg, True, cost
            return False, f"⭐ رصيدك غير كافٍ\nتحتاج {cost} نقطة\nرصيدك {bal}\n🛒 /buy_points", True, cost
        # عرض إعلان فقط، لا نخصم هنا
        ad = await ads_system.show_ad(user_id, service)
        msg = f"📢 **إعلان:**\n\n{ad}\n\n✅ سيتم خصم {cost} نقطة بعد إتمام الخدمة | رصيدك: {bal}"
        return True, msg, False, cost

    def spend_points_after_success(self, user_id, cost, service):
        """تُستدعى بعد نجاح الخدمة لخصم النقاط"""
        if points_system.spend_points(user_id, cost, f'استخدام {service}'):
            return True
        return False

    def get_service_cost_info(self):
        c = points_system.service_costs
        return (
            "📊 تكاليف الخدمات:\n"
            f"🔗 اختصار: {c.get('shorten', 1)} نقطة\n"
            f"📸 OCR: {c.get('ocr', 4)} نقاط\n"
            f"📥 تحميل: {c.get('download', 5)} نقاط\n"
            f"🎙️ TTS: {c.get('speak', 3)} نقاط\n"
            "\n💡 ادعُ أصدقاء (5 نقاط) أو /buy_points"
        )

middleware = Middleware()