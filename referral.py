from db import get_conn
from datetime import datetime
import random, string

def generate_ref_code():
    conn = get_conn()
    c = conn.cursor()
    while True:
        code = ''.join(random.choices(string.ascii_letters+string.digits, k=8))
        c.execute("SELECT 1 FROM users WHERE ref_code=?", (code,))
        if not c.fetchone():
            conn.close()
            return code

def add_referral(new_user_id, referrer_id):
    c = get_conn().cursor()
    c.execute("UPDATE users SET referrals_count=referrals_count+1 WHERE user_id=?", (referrer_id,))
    c.execute("INSERT INTO referral_tracking(referrer_id, new_user_id, created_at) VALUES(?,?,?)",
              (referrer_id, new_user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.connection.commit()
    c.connection.close()

def get_referral_stats(user_id):
    c = get_conn().cursor()
    c.execute("SELECT referrals_count, referrals_watched_ads FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    total = row[0] if row else 0
    watched = row[1] if row else 0
    c.connection.close()
    return {'total_invited':total,'watched_ads':watched,'pending':total-watched}

def process_referral_commission(earned_amount, user_id):
    c = get_conn().cursor()
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row and row[0] != 0:
        commission = earned_amount * 0.10
        c.execute("UPDATE users SET balance=balance+?, total=total+? WHERE user_id=?",
                  (commission, commission, row[0]))
        c.connection.commit()
    c.connection.close()