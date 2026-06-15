from db import get_conn
from config import ADMIN_IDS, MIN_WITHDRAW
from datetime import datetime

async def request_withdraw(update, context):
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(f"❌ /withdraw <المبلغ> <عنوان Binance>\nالحد الأدنى: {MIN_WITHDRAW}$")
        return
    try:
        amount = float(args[0])
    except:
        await update.message.reply_text("❌ مبلغ غير صالح")
        return
    wallet = " ".join(args[1:])
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    balance = row[0] if row else 0
    if amount < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ الحد الأدنى {MIN_WITHDRAW}$")
        conn.close()
        return
    if amount > balance:
        await update.message.reply_text("❌ رصيد غير كاف")
        conn.close()
        return
    c.execute("INSERT INTO withdraws(user_id, amount, wallet, request_date) VALUES(?,?,?,?)",
              (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    conn.commit()
    c.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
    row2 = c.fetchone()
    username = row2[0] if row2 and row2[0] else "بدون معرف"
    try:
        from points import points_system
        pts = points_system.get_balance(user_id)
    except:
        pts = 0
    conn.close()
    for a in ADMIN_IDS:
        try:
            await context.bot.send_message(a, f"📥 طلب سحب\n👤 {username} ({user_id})\n💰 {amount:.3f}$\n🏦 {wallet}\n⭐ {pts}")
        except:
            pass
    await update.message.reply_text(f"✅ تم تقديم طلب سحب {amount:.3f}$")