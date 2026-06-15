from db import get_conn
from config import ADMIN_IDS
from datetime import datetime

async def support_message(update, context):
    user_id = update.effective_user.id
    msg = update.message.text
    c = get_conn()
    cur = c.cursor()
    cur.execute("INSERT INTO support_tickets(user_id,message,created_at) VALUES(?,?,?)",
                (user_id,msg,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    tid = cur.lastrowid
    c.commit()
    username = update.effective_user.username or "بدون معرف"
    for a in ADMIN_IDS:
        try: await context.bot.send_message(a, f"📩 تذكرة #{tid}\n👤 {username} ({user_id})\n📝 {msg}\nللرد: /reply {tid} <الرد>")
        except: pass
    await update.message.reply_text("✅ تم إرسال رسالتك للإدارة")
    c.close()

async def reply_to_user(update, context):
    if update.effective_user.id not in ADMIN_IDS: return
    args = context.args
    if len(args)<2: await update.message.reply_text("❌ /reply <رقم التذكرة> <الرد>"); return
    try: tid=int(args[0])
    except: await update.message.reply_text("❌ رقم غير صالح"); return
    reply = " ".join(args[1:])
    c = get_conn().cursor()
    c.execute("SELECT user_id FROM support_tickets WHERE id=? AND status='open'",(tid,))
    row = c.fetchone()
    if not row: await update.message.reply_text("❌ التذكرة غير موجودة"); c.connection.close(); return
    target = row[0]
    c.execute("UPDATE support_tickets SET reply=?, status='closed' WHERE id=?",(reply,tid))
    c.connection.commit()
    c.connection.close()
    try: await context.bot.send_message(target, f"📬 رد الإدارة:\n{reply}"); await update.message.reply_text("✅ تم الرد")
    except: await update.message.reply_text("⚠️ تعذر الإرسال")