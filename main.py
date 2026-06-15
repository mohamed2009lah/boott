import os
import logging
from datetime import datetime

# استيراد telegram مع معالجة الأخطاء
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, CallbackQueryHandler,
        ConversationHandler, ContextTypes, filters, PreCheckoutQueryHandler
    )
    from telegram.warnings import PTBUserWarning
    import warnings
    warnings.filterwarnings("ignore", category=PTBUserWarning)
except ImportError as e:
    print(f"❌ Error importing telegram: {e}")
    print("Make sure python-telegram-bot is installed: pip install python-telegram-bot[job-queue]==20.7")
    exit(1)

from config import TOKEN, ADMIN_IDS, PAYMENT_PROVIDER_TOKEN
from db import init, get_conn
from api import shorten
from earnings import update_earnings
from admin import broadcast
from referral import generate_ref_code, add_referral, get_referral_stats
from withdraw import request_withdraw
from support import support_message, reply_to_user
from points import points_system
from ads import ads_system
from admin_panel import admin_panel
from middleware import middleware
from ocr import OCRProcessor
from downloader import VideoDownloader
from tts import TextToSpeech

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ocr = OCRProcessor()
downloader = VideoDownloader()
tts = TextToSpeech()

# حالات ConversationHandler
WAIT_LINK, WAIT_BROADCAST, WAIT_SUPPORT, WAIT_OCR_PHOTO, WAIT_ORIGINAL = range(5)

# قاموس لتخزين الفواتير المؤقتة للتحقق
pending_invoices = {}

# ========== دوال الخدمات ==========
async def receive_link(update, context):
    user_id = update.effective_user.id
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط صحيح يبدأ بـ http:// أو https://")
        return WAIT_LINK
    
    # خصم النقاط بعد نجاح الاختصار
    short = await shorten(url)
    if short:
        # خصم النقاط بعد النجاح
        if not middleware.spend_points_after_success(user_id, points_system.get_service_cost('shorten'), 'shorten'):
            await update.message.reply_text("❌ حدث خطأ في خصم النقاط")
            return ConversationHandler.END
        
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO links(user_id, original_url, short, created_at) VALUES(?,?,?,?)",
                  (user_id, url, short, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ رابط مختصر:\n{short}")
    else:
        await update.message.reply_text("❌ فشل اختصار الرابط، حاول مجدداً")
    return ConversationHandler.END

async def receive_broadcast(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("غير مصرح")
        return ConversationHandler.END
    text = update.message.text
    await update.message.reply_text("جاري الإرسال...")
    ok, fail = await broadcast(context.bot, text)
    await update.message.reply_text(f"✅ تم: {ok}\n❌ فشل: {fail}")
    return ConversationHandler.END

async def receive_support(update, context):
    await support_message(update, context)
    return ConversationHandler.END

async def receive_ocr_photo(update, context):
    user_id = update.effective_user.id
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("❌ لم أجد صورة، أرسل صورة صالحة")
        return WAIT_OCR_PHOTO
    
    wait = await update.message.reply_text("🔍 جارٍ استخراج النص...")
    text = await ocr.extract_from_photo(photo)
    if text:
        # خصم النقاط بعد النجاح
        if middleware.spend_points_after_success(user_id, points_system.get_service_cost('ocr'), 'ocr'):
            await wait.edit_text(f"📝 {text}")
        else:
            await wait.edit_text("❌ حدث خطأ في خصم النقاط")
    else:
        await wait.edit_text("⚠️ لا يوجد نص")
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("تم الإلغاء")
    return ConversationHandler.END

# ========== أوامر النقاط ==========
async def points_cmd(update, context):
    uid = update.effective_user.id
    s = points_system.get_user_stats(uid)
    r = get_referral_stats(uid)
    msg = f"⭐ نقاطك: {s['balance']}\n📊 المكتسبة: {s['total_earned']}\n💸 المنفقة: {s['total_spent']}\n\n"
    msg += f"👥 الدعوات: {r['total_invited']} (✅{r['watched_ads']} ⏳{r['pending']})\n\n"
    msg += middleware.get_service_cost_info()
    await update.message.reply_text(msg)

async def daily_cmd(update, context):
    ok, msg = points_system.claim_daily_bonus(update.effective_user.id)
    await update.message.reply_text(msg)

async def buy_points_cmd(update, context):
    pricing = points_system.get_pricing_list()
    msg = "🛒 شراء نقاط:\n\n"
    kb = []
    for amt, price, stars in pricing:
        msg += f"⭐ {amt} نقطة = {price:.2f}$ | ⭐{stars} نجمة\n"
        kb.append([InlineKeyboardButton(f"💰 {amt} نقطة - {price:.2f}$", callback_data=f"buy_{amt}"),
                   InlineKeyboardButton(f"⭐ {stars} نجمة", callback_data=f"stars_{amt}")])
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def invite_cmd(update, context):
    uid = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT ref_code, referrals_count, referrals_watched_ads FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    if row:
        bot = (await context.bot.get_me()).username
        link = f"https://t.me/{bot}?start={row[0]}"
        await update.message.reply_text(f"🔗 {link}\n👥 {row[1]} ({row[2]} شاهدوا)\n⭐ كل مشاهدة = 5 نقاط")

# ========== أوامر الأدمن ==========
async def admin_cmd(update, context):
    if update.effective_user.id in ADMIN_IDS:
        await admin_panel.show_main_panel(update)

async def grant_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target, amt = int(context.args[0]), int(context.args[1])
        points_system.admin_grant_points(update.effective_user.id, target, amt)
        await update.message.reply_text("✅ تم منح النقاط")
    except:
        await update.message.reply_text("/grant <user_id> <amount>")

async def add_ad_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        w = int(context.args[0])
        text = " ".join(context.args[1:])
        nid = ads_system.add_manual_ad(text, w)
        await update.message.reply_text(f"✅ أضيف إعلان #{nid}")
    except:
        await update.message.reply_text("/add_ad <وزن> <نص>")

async def remove_ad_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        ads_system.remove_manual_ad(int(context.args[0]))
        await update.message.reply_text("✅ حذف")
    except:
        await update.message.reply_text("/remove_ad <id>")

# ========== معالجة الدفع بالنجوم ==========
async def pre_checkout_callback(update, context):
    query = update.pre_checkout_query
    user_id = query.from_user.id
    payload = query.invoice_payload
    
    # التحقق من أن الفاتورة صادرة من البوت لهذا المستخدم
    if payload.startswith("points_") and pending_invoices.get(user_id) == payload:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="فاتورة غير صالحة")

async def successful_payment_callback(update, context):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    if payload.startswith("points_"):
        amount = int(payload.split("_")[1])
        # إضافة النقاط بعد الدفع الناجح
        points_system.add_points(user_id, amount, 'stars_payment', f'شراء {amount} نقطة بنجاح')
        # تنظيف الفاتورة المؤقتة
        if user_id in pending_invoices:
            del pending_invoices[user_id]
        await update.message.reply_text(f"✅ تم شراء {amount} نقطة بنجاح!")

# ========== الأزرار (CallbackQuery) ==========
async def button_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    
    if data == "short":
        ok, msg, skip, cost = await middleware.check_and_process(uid, 'shorten', context)
        if not ok:
            await q.message.reply_text(msg)
            return
        if msg:
            await q.message.reply_text(msg)
        await q.message.reply_text("📎 أرسل الرابط للاختصار:")
        return WAIT_LINK
    
    elif data == "bal":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        row = c.fetchone()
        bal = row[0] if row else 0
        pts = points_system.get_balance(uid)
        conn.close()
        await q.message.reply_text(f"💰 {bal:.3f}$ | ⭐ {pts}")
        return
    
    elif data == "points_info":
        s = points_system.get_user_stats(uid)
        r = get_referral_stats(uid)
        msg = f"⭐ الرصيد: {s['balance']}\n📊 مكتسب: {s['total_earned']}\n💸 منفق: {s['total_spent']}\n\n👥 {r['total_invited']} ({r['watched_ads']} شاهدوا)\n\n" + middleware.get_service_cost_info()
        await q.message.reply_text(msg)
        return
    
    elif data == "daily":
        ok, msg = points_system.claim_daily_bonus(uid)
        await q.message.reply_text(msg)
        return
    
    elif data == "buy_points_menu":
        pricing = points_system.get_pricing_list()
        msg = "🛒 شراء نقاط:\n\n"
        kb = []
        for amt, price, stars in pricing:
            kb.append([InlineKeyboardButton(f"💰 {amt} نقطة - {price:.2f}$", callback_data=f"buy_{amt}"),
                       InlineKeyboardButton(f"⭐ {stars} نجمة", callback_data=f"stars_{amt}")])
        await q.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        return
    
    elif data.startswith("buy_"):
        amt = int(data.split("_")[1])
        price, err = points_system.buy_points_with_money(uid, amt)
        if err:
            await q.message.reply_text(err)
            return
        # إرسال إشعار للأدمن بدلاً من إضافة النقاط مباشرة
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"💰 طلب شراء نقاط\n"
                    f"👤 المستخدم: {uid}\n"
                    f"⭐ الكمية: {amt} نقطة\n"
                    f"💵 السعر: {price:.2f}$\n"
                    f"📝 للشراء: /grant {uid} {amt}"
                )
            except:
                pass
        await q.message.reply_text(f"✅ تم إرسال طلب الشراء إلى الإدارة.\nالمبلغ: {price:.2f}$\nسيتم إضافة النقاط بعد تأكيد الدفع.")
        return
    
    elif data.startswith("stars_"):
        if not PAYMENT_PROVIDER_TOKEN:
            await q.message.reply_text("❌ الدفع بالنجوم غير مفعل")
            return
        amt = int(data.split("_")[1])
        stars_needed, err = points_system.buy_points_with_stars(uid, amt)
        if err:
            await q.message.reply_text(err)
            return
        # تخزين الفاتورة المؤقتة
        payload = f"points_{amt}"
        pending_invoices[uid] = payload
        await context.bot.send_invoice(
            chat_id=uid, title="شراء نقاط", description=f"شراء {amt} نقطة",
            payload=payload, provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="XTR", prices=[LabeledPrice(label=f"{amt} نقطة", amount=stars_needed)]
        )
        return
    
    elif data == "stats":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (uid,))
        links = c.fetchone()[0]
        c.execute("SELECT balance, total, referrals_count, referrals_watched_ads, join_date FROM users WHERE user_id=?", (uid,))
        row = c.fetchone()
        conn.close()
        if row:
            bal, total, refs, watched, join = row
            pts = points_system.get_balance(uid)
            await q.message.reply_text(f"📊 الإحصائيات:\n💰 {bal:.3f}$\n💵 {total:.3f}$\n⭐ {pts}\n🔗 {links}\n👥 {refs} ({watched} شاهدوا)\n📅 {join}")
        return
    
    elif data == "ref":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT ref_code, referrals_count, referrals_watched_ads FROM users WHERE user_id=?", (uid,))
        row = c.fetchone()
        conn.close()
        if row:
            ref, refs, watched = row
            bot = (await context.bot.get_me()).username
            link = f"https://t.me/{bot}?start={ref}"
            await q.message.reply_text(f"🔗 {link}\n👥 {refs} ({watched} شاهدوا)\n⭐ كل مشاهدة = 5 نقاط")
        return
    
    elif data == "admin_panel" and uid in ADMIN_IDS:
        await admin_panel.show_main_panel(q)
        return ConversationHandler.END
    
    elif data == "withdraw":
        await q.message.reply_text("💳 /withdraw <المبلغ> <محفظة>")
        return
    
    elif data == "support":
        await q.message.reply_text("📝 أرسل رسالتك:")
        return WAIT_SUPPORT
    
    elif data in ["admin_stats", "admin_adstats", "admin_referrals", "admin_withdrawals", "admin_points", "admin_grant", "admin_broadcast", "admin_manageads"]:
        if uid not in ADMIN_IDS:
            return
        if data == "admin_stats":
            s = admin_panel.get_full_stats()
            msg = f"""📊 إحصائيات:
👥 المستخدمين: {s['total_users']} (شهر:{s['monthly_users']})
🟢 نشط اليوم: {s['active_today']} | 24س: {s['active_24h']}
📢 شاهدوا إعلان: {s['active_ads_today']}
🔗 الروابط: {s['total_links']} (اليوم:{s['today_links']})
💰 الأرباح: {s['total_earnings']:.3f}$ | الأرصدة: {s['total_balance']:.3f}$
⭐ النقاط: {s['total_points']} | مبيعات اليوم: {s['buys_count']} ({s['buys_total']})
💳 السحوبات: {s['pending_wd']} معلقة | إجمالي: {s['wd_count']} ({s['wd_total']:.3f}$)"""
            await q.message.reply_text(msg)
        elif data == "admin_adstats":
            today_views, _, _ = ads_system.get_daily_ad_stats()
            total = ads_system.get_total_ad_stats()
            msg = f"📢 اليوم: {today_views}\n📈 الإجمالي: {total['total_views']}\n\n👥 الدعوات: {total['total_referrals']} ({total['watched_referrals']} شاهدوا)"
            await q.message.reply_text(msg)
        elif data == "admin_referrals":
            r = admin_panel.get_referral_stats()
            msg = f"👥 إجمالي: {r['total_referrals']}\n✅ شاهدوا: {r['watched_referrals']}\n⭐ نقاط: {r['awarded_referrals']}\n⏳ معلق: {r['pending_referrals']}"
            await q.message.reply_text(msg)
        elif data == "admin_withdrawals":
            conn = get_conn()
            c2 = conn.cursor()
            c2.execute("SELECT * FROM withdraws WHERE status='pending'")
            rows = c2.fetchall()
            conn.close()
            msg = "💳 طلبات:\n" + "\n".join(f"#{r[0]} {r[2]:.2f}$ {r[3]}" for r in rows) if rows else "لا يوجد"
            await q.message.reply_text(msg)
        elif data == "admin_points":
            info = admin_panel.get_points_management()
            msg = f"⭐ إجمالي: {info['total_balance']}\n📈 مكتسب: {info['total_earned']}\n💸 منفق: {info['total_spent']}\n🏆 الأعلى:\n"
            msg += "\n".join(f"{u[1]}: {u[2]}" for u in info['top_users'])
            await q.message.reply_text(msg)
        elif data == "admin_broadcast":
            await q.message.reply_text("أرسل الرسالة:")
            return WAIT_BROADCAST
        elif data == "admin_manageads":
            ads = ads_system.get_all_manual_ads()
            msg = "📝 الإعلانات:\n" + "\n".join(f"#{a['id']} {a['text'][:50]}" for a in ads)
            msg += "\n/add_ad <الوزن> <نص>"
            await q.message.reply_text(msg)
        return
    
    return ConversationHandler.END

# ========== أوامر الخدمات (OCR, Download, TTS) ==========
async def ocr_cmd(update, context):
    await update.message.reply_text("📸 أرسل الصورة (يمكنك الرد على صورة موجودة)")
    return WAIT_OCR_PHOTO

async def dl_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip, cost = await middleware.check_and_process(uid, 'download', context)
    if not ok:
        await update.message.reply_text(msg)
        return
    if msg:
        await update.message.reply_text(msg)
    if not context.args:
        await update.message.reply_text("📥 /dl <رابط> أو /dl <جودة> <رابط>\nالجودة: best,720,480,360,audio")
        return
    
    if len(context.args) == 1:
        url = context.args[0]
        quality = 'best'
    else:
        if context.args[0] in ['best', '720', '480', '360', 'audio']:
            quality = context.args[0]
            url = context.args[1]
        else:
            url = context.args[0]
            quality = 'best'
    
    if not downloader.is_supported(url):
        await update.message.reply_text("❌ الرابط غير مدعوم")
        return
    
    wait = await update.message.reply_text("📥 جارٍ التحميل...")
    info = await downloader.get_info(url)
    if info:
        await wait.edit_text(f"📹 {info['title']}\n⏳ تحميل...")
    
    path = await downloader.download(url, quality)
    if path:
        # خصم النقاط بعد النجاح
        if middleware.spend_points_after_success(uid, cost, 'download'):
            await wait.edit_text("📤 رفع...")
            try:
                with open(path, 'rb') as f:
                    if quality == 'audio':
                        await update.message.reply_audio(f, title=info['title'] if info else "Audio")
                    else:
                        await update.message.reply_video(f, caption=info['title'] if info else "فيديو")
                os.remove(path)
                await wait.delete()
            except Exception as e:
                await update.message.reply_text(f"❌ فشل الرفع: {e}")
        else:
            await wait.edit_text("❌ حدث خطأ في خصم النقاط")
    else:
        await wait.edit_text("❌ فشل التحميل")

async def tts_cmd(update, context):
    uid = update.effective_user.id
    ok, msg, skip, cost = await middleware.check_and_process(uid, 'speak', context)
    if not ok:
        await update.message.reply_text(msg)
        return
    if msg:
        await update.message.reply_text(msg)
    if not context.args:
        await update.message.reply_text("🎙️ /tts <نص>")
        return
    text = " ".join(context.args)
    path, err = await tts.convert(text)
    if path:
        if middleware.spend_points_after_success(uid, cost, 'speak'):
            with open(path, 'rb') as f:
                await update.message.reply_voice(f)
            os.remove(path)
        else:
            await update.message.reply_text("❌ حدث خطأ في خصم النقاط")
    else:
        await update.message.reply_text(f"❌ {err}")

# ========== /start ==========
async def start(update, context):
    u = update.effective_user
    conn = get_conn()
    cur = conn.cursor()
    ref = context.args[0] if context.args else None
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        new_ref = generate_ref_code()
        referrer = 0
        if ref:
            cur.execute("SELECT user_id FROM users WHERE ref_code=?", (ref,))
            rr = cur.fetchone()
            if rr:
                referrer = rr[0]
        cur.execute("INSERT INTO users(user_id, username, ref_code, referred_by, join_date) VALUES(?,?,?,?,?)",
                    (u.id, u.username or "user", new_ref, referrer, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if referrer:
            add_referral(u.id, referrer)
            try:
                ad_text = ads_system.show_referral_ad(u.id, referrer)
                await update.message.reply_text(f"📢 {ad_text}\n✅ تم تسجيلك")
            except:
                pass
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (u.id,))
    links = cur.fetchone()[0]
    cur.execute("SELECT balance, total, ref_code, referrals_count, referrals_watched_ads, join_date FROM users WHERE user_id=?", (u.id,))
    row = cur.fetchone()
    conn.close()
    if row:
        bal, total, my_ref, refs, watched, join = row
        pts = points_system.get_balance(u.id)
        bot = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot}?start={my_ref}"
        msg = f"""👋 أهلاً بك
💰 الرصيد: {bal:.3f}$ | 💵 إجمالي الأرباح: {total:.3f}$
⭐ النقاط: {pts} | 🔗 الروابط: {links}
👥 المدعوين: {refs} (✅{watched} ⏳{refs-watched})
🔗 رابط الدعوة: {ref_link}"""
        kb = [
            [InlineKeyboardButton("🔗 اختصار رابط", callback_data="short")],
            [InlineKeyboardButton("💰 رصيدي", callback_data="bal"),
             InlineKeyboardButton("⭐ نقاطي", callback_data="points_info")],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
            [InlineKeyboardButton("💳 سحب", callback_data="withdraw")],
            [InlineKeyboardButton("🔗 الدعوة", callback_data="ref"),
             InlineKeyboardButton("🛒 شراء نقاط", callback_data="buy_points_menu")],
            [InlineKeyboardButton("🎁 يومية", callback_data="daily"),
             InlineKeyboardButton("🆘 دعم", callback_data="support")],
        ]
        if u.id in ADMIN_IDS:
            kb.append([InlineKeyboardButton("🔐 لوحة الأدمن", callback_data="admin_panel")])
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ========== Job Queue ==========
async def earnings_job(context: ContextTypes.DEFAULT_TYPE):
    await update_earnings(context.bot)

# ========== main ==========
def main():
    init()
    points_system.init_tables()
    ads_system.init_tables()

    app = Application.builder().token(TOKEN).build()

    # إعداد ConversationHandlers
    conv_short = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^short$")],
        states={WAIT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    conv_broadcast = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^admin_broadcast$")],
        states={WAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    conv_support = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^support$")],
        states={WAIT_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_support)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    conv_ocr = ConversationHandler(
        entry_points=[CommandHandler("ocr", ocr_cmd)],
        states={WAIT_OCR_PHOTO: [MessageHandler(filters.PHOTO, receive_ocr_photo)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("points", points_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("buy_points", buy_points_cmd))
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(CommandHandler("withdraw", request_withdraw))
    app.add_handler(CommandHandler("reply", reply_to_user))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("grant", grant_cmd))
    app.add_handler(CommandHandler("add_ad", add_ad_cmd))
    app.add_handler(CommandHandler("remove_ad", remove_ad_cmd))
    app.add_handler(CommandHandler("dl", dl_cmd))
    app.add_handler(CommandHandler("tts", tts_cmd))

    # ConversationHandlers
    app.add_handler(conv_short)
    app.add_handler(conv_broadcast)
    app.add_handler(conv_support)
    app.add_handler(conv_ocr)

    # باقي المعالجات
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Job queue
    if app.job_queue:
        app.job_queue.run_repeating(earnings_job, interval=1800, first=60)

    # تشغيل البوت
    print("✅ البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
