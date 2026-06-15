from db import get_conn
from api import stats
from referral import process_referral_commission

async def update_earnings(bot):
    c = get_conn().cursor()
    c.execute("SELECT id,user_id,short,earned FROM links")
    for link_id,uid,url,last_earned in c.fetchall():
        earned = await stats(url)
        if not earned or earned<=last_earned: continue
        delta = earned-last_earned
        user_share = delta*0.70
        c.execute("UPDATE users SET balance=balance+?, total=total+? WHERE user_id=?",(user_share,delta,uid))
        c.execute("UPDATE links SET earned=? WHERE id=?",(earned,link_id))
        process_referral_commission(delta,uid)
    c.connection.commit()
    c.connection.close()