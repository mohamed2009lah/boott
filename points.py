from db import get_conn
from datetime import datetime

class PointsSystem:
    def __init__(self):
        self.service_costs = {
            'shorten': 1,
            'ocr': 4,
            'download': 5,
            'speak': 3,
            # تم إزالة 'separate' لأن الخدمة غير مفعلة
        }
        self.referral_points = 5
        self.daily_bonus = 2
        self.stars_ratio = 10

    def init_tables(self):
        c = get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM points_pricing")
        if c.fetchone()[0] == 0:
            prices = [
                (10, 0.50, 5),
                (25, 1.00, 10),
                (50, 1.80, 18),
                (100, 3.00, 30),
                (250, 6.50, 65),
                (500, 10.00, 100),
                (1000, 18.00, 180),
            ]
            for amount, price, stars in prices:
                c.execute("INSERT INTO points_pricing(amount, price, stars_price) VALUES(?,?,?)",
                          (amount, price, stars))
            c.connection.commit()
        c.connection.close()

    def get_balance(self, user_id):
        c = get_conn().cursor()
        c.execute("SELECT balance FROM points WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        return row[0] if row else 0

    def add_points(self, user_id, amount, trans_type, description):
        c = get_conn().cursor()
        c.execute("""
        INSERT INTO points(user_id, balance, total_earned) VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET balance=balance+?, total_earned=total_earned+?
        """, (user_id, amount, amount, amount, amount))
        c.execute("""
        INSERT INTO points_transactions(user_id, amount, type, description, created_at)
        VALUES(?,?,?,?,?)
        """, (user_id, amount, trans_type, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.connection.commit()
        c.connection.close()

    def spend_points(self, user_id, amount, description):
        if self.get_balance(user_id) < amount:
            return False
        c = get_conn().cursor()
        c.execute("UPDATE points SET balance=balance-?, total_spent=total_spent+? WHERE user_id=?",
                  (amount, amount, user_id))
        c.execute("""
        INSERT INTO points_transactions(user_id, amount, type, description, created_at)
        VALUES(?,?,?,?,?)
        """, (user_id, -amount, 'spend', description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.connection.commit()
        c.connection.close()
        return True

    def get_service_cost(self, service):
        return self.service_costs.get(service, 5)

    def add_referral_points(self, referrer_id):
        self.add_points(referrer_id, self.referral_points, 'referral', 'مكافأة دعوة صديق شاهد الإعلان')

    def claim_daily_bonus(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        c = get_conn().cursor()
        c.execute("SELECT last_daily_bonus FROM points WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row and row[0] == today:
            c.connection.close()
            return False, "لقد استلمت مكافأتك اليومية بالفعل"
        self.add_points(user_id, self.daily_bonus, 'daily', 'المكافأة اليومية')
        c.execute("UPDATE points SET last_daily_bonus=? WHERE user_id=?", (today, user_id))
        c.connection.commit()
        c.connection.close()
        return True, f"✅ تمت إضافة {self.daily_bonus} نقاط"

    def get_pricing_list(self):
        c = get_conn().cursor()
        c.execute("SELECT amount, price, stars_price FROM points_pricing WHERE active=1 ORDER BY amount")
        rows = c.fetchall()
        c.connection.close()
        return rows

    def buy_points_with_money(self, user_id, package_amount):
        """ترجع السعر فقط، لا تضيف نقاط"""
        c = get_conn().cursor()
        c.execute("SELECT price FROM points_pricing WHERE amount=? AND active=1", (package_amount,))
        row = c.fetchone()
        if not row:
            c.connection.close()
            return None, "باقة غير موجودة"
        price = row[0]
        c.connection.close()
        return price, None

    def buy_points_with_stars(self, user_id, package_amount):
        """ترجع عدد النجوم المطلوبة فقط، لا تضيف نقاط"""
        c = get_conn().cursor()
        c.execute("SELECT stars_price FROM points_pricing WHERE amount=? AND active=1", (package_amount,))
        row = c.fetchone()
        if not row:
            c.connection.close()
            return None, "باقة غير موجودة"
        stars = row[0]
        c.connection.close()
        return stars, None

    def get_user_stats(self, user_id):
        c = get_conn().cursor()
        c.execute("SELECT balance, total_earned, total_spent FROM points WHERE user_id=?", (user_id,))
        row = c.fetchone()
        c.connection.close()
        if row:
            return {'balance': row[0], 'total_earned': row[1], 'total_spent': row[2]}
        return {'balance': 0, 'total_earned': 0, 'total_spent': 0}

    def admin_grant_points(self, admin_id, target_user_id, amount):
        self.add_points(target_user_id, amount, 'admin_grant', f'منحة من الأدمن {admin_id}')

points_system = PointsSystem()