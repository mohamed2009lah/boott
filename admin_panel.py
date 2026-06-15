from db import get_conn
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from ads import ads_system

class AdminPanel:
    async def show_main_panel(self, update_or_query):
        kb = [
            [InlineKeyboardButton("📊 إحصائيات شاملة", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 إحصائيات الإعلانات", callback_data="admin_adstats")],
            [InlineKeyboardButton("👥 إحصائيات الدعوات", callback_data="admin_referrals")],
            [InlineKeyboardButton("⭐ إدارة النقاط", callback_data="admin_points")],
            [InlineKeyboardButton("💳 طلبات السحب", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("📢 إرسال للجميع", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👤 منح نقاط", callback_data="admin_grant")],
            [InlineKeyboardButton("📝 إدارة الإعلانات", callback_data="admin_manageads")],
        ]
        if hasattr(update_or_query, 'message') and hasattr(update_or_query.message, 'reply_text'):
            await update_or_query.message.reply_text("🔐 لوحة التحكم", reply_markup=InlineKeyboardMarkup(kb))
        elif hasattr(update_or_query, 'edit_message_text'):
            await update_or_query.edit_message_text("🔐 لوحة التحكم", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update_or_query.message.reply_text("🔐 لوحة التحكم", reply_markup=InlineKeyboardMarkup(kb))

    def get_full_stats(self):
        c = get_conn().cursor()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE join_date>=?", (month_start,))
        monthly = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at>=?", (today,))
        active_today = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM links WHERE created_at>=?", (yesterday,))
        active_24h = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM ad_views WHERE viewed_at>=?", (today,))
        ad_today = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM links")
        total_links = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM links WHERE created_at>=?", (today,))
        today_links = c.fetchone()[0]
        c.execute("SELECT SUM(total) FROM users")
        total_earn = c.fetchone()[0] or 0
        c.execute("SELECT SUM(balance) FROM users")
        bal = c.fetchone()[0] or 0
        c.execute("SELECT SUM(balance) FROM points")
        pts = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*), SUM(amount) FROM points_transactions WHERE type='buy' AND created_at>=?", (today,))
        buys = c.fetchone()
        c.execute("SELECT COUNT(*) FROM withdraws WHERE status='pending'")
        pend = c.fetchone()[0]
        c.execute("SELECT COUNT(*), SUM(amount) FROM withdraws")
        wd = c.fetchone()
        c.connection.close()
        return {
            'total_users': total_users, 'monthly_users': monthly,
            'active_today': active_today, 'active_24h': active_24h,
            'active_ads_today': ad_today, 'total_links': total_links,
            'today_links': today_links, 'total_earnings': total_earn,
            'total_balance': bal, 'total_points': pts,
            'buys_count': buys[0] or 0, 'buys_total': buys[1] or 0,
            'pending_wd': pend, 'wd_count': wd[0] or 0, 'wd_total': wd[1] or 0
        }

    def get_points_management(self):
        c = get_conn().cursor()
        c.execute("""
            SELECT u.user_id, u.username, p.balance, p.total_earned, p.total_spent
            FROM points p JOIN users u ON p.user_id=u.user_id
            ORDER BY p.balance DESC LIMIT 10
        """)
        top = c.fetchall()
        c.execute("SELECT SUM(balance) FROM points")
        tot_bal = c.fetchone()[0] or 0
        c.execute("SELECT SUM(total_earned) FROM points")
        tot_earn = c.fetchone()[0] or 0
        c.execute("SELECT SUM(total_spent) FROM points")
        tot_spent = c.fetchone()[0] or 0
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*), SUM(amount) FROM points_transactions WHERE type='buy' AND created_at>=?", (today,))
        buys = c.fetchone()
        c.connection.close()
        return {
            'top_users': top, 'total_balance': tot_bal,
            'total_earned': tot_earn, 'total_spent': tot_spent,
            'buys_count': buys[0] or 0, 'buys_total': buys[1] or 0
        }

    def get_referral_stats(self):
        c = get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM referral_tracking")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE ad_watched=1")
        watched = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM referral_tracking WHERE points_awarded=1")
        awarded = c.fetchone()[0]
        c.execute("""
            SELECT u.user_id, u.username, u.referrals_count, u.referrals_watched_ads
            FROM users u WHERE u.referrals_count>0
            ORDER BY u.referrals_watched_ads DESC LIMIT 10
        """)
        top = c.fetchall()
        c.connection.close()
        return {
            'total_referrals': total, 'watched_referrals': watched,
            'awarded_referrals': awarded, 'pending_referrals': total - watched,
            'top_referrers': top
        }

admin_panel = AdminPanel()