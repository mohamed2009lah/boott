import asyncio
from db import get_conn
import html

async def broadcast(bot, message: str):
    # ترميز النص لتجنب مشاكل HTML
    safe_message = html.escape(message)
    c = get_conn().cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    c.connection.close()
    ok = fail = 0
    for i, u in enumerate(users):
        try:
            await bot.send_message(u[0], f"📢 {safe_message}", parse_mode="HTML")
            ok += 1
            if i % 25 == 0:
                await asyncio.sleep(1)
        except:
            fail += 1
    return ok, fail