import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class Database:
    def __init__(self, db_name: str = "referral_bot.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Foydalanuvchilar jadvali
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            registration_date TEXT,
            phone TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id)
        )
        """)

        # Referallar jadvali
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            amount INTEGER,
            date TEXT,
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
        )
        """)

        # Tranzaksiyalar jadvali
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,
            description TEXT,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """)

        # Pul yechish so'rovlari jadvali
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            method TEXT,
            details TEXT,
            status TEXT DEFAULT 'pending',
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """)

        self.conn.commit()

    # Foydalanuvchilar bilan ishlash
    def get_user(self, user_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, user))
        return None

    def register_user(self, user_id: int, username: str, full_name: str, referrer_id: int = None, phone: str = None):
        if self.get_user(user_id):
            return False

        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO users (user_id, username, full_name, referrer_id, registration_date, phone)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, referrer_id, datetime.now().isoformat(), phone))

        if referrer_id and self.get_user(referrer_id):
            # Referalga bonus berish (5000 so'm)
            self.update_balance(referrer_id, 5000)

            cursor.execute("""
            INSERT INTO referrals (referrer_id, referred_id, amount, date)
            VALUES (?, ?, ?, ?)
            """, (referrer_id, user_id, 5000, datetime.now().isoformat()))

            cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description, date)
            VALUES (?, ?, ?, ?, ?)
            """, (referrer_id, 5000, 'referral', f'New referral: {username}', datetime.now().isoformat()))

        self.conn.commit()
        return True

    def update_balance(self, user_id: int, amount: int):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    # Referallar bilan ishlash
    def get_referrals_count(self, user_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()[0]

    def get_referral_stats(self, user_id: int) -> Dict:
        cursor = self.conn.cursor()

        # Umumiy statistikalar
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(amount) as total_amount
        FROM referrals 
        WHERE referrer_id = ?
        """, (user_id,))
        total_stats = cursor.fetchone()

        # Haftalik statistikalar
        cursor.execute("""
        SELECT 
            COUNT(*) as weekly,
            SUM(amount) as weekly_amount
        FROM referrals 
        WHERE referrer_id = ? 
        AND date >= datetime('now', '-7 days')
        """, (user_id,))
        weekly_stats = cursor.fetchone()

        # Kunlik statistikalar
        cursor.execute("""
        SELECT 
            COUNT(*) as daily,
            SUM(amount) as daily_amount
        FROM referrals 
        WHERE referrer_id = ? 
        AND date >= datetime('now', '-1 days')
        """, (user_id,))
        daily_stats = cursor.fetchone()

        return {
            'total': total_stats[0] if total_stats else 0,
            'total_amount': total_stats[1] if total_stats and total_stats[1] else 0,
            'weekly': weekly_stats[0] if weekly_stats else 0,
            'weekly_amount': weekly_stats[1] if weekly_stats and weekly_stats[1] else 0,
            'daily': daily_stats[0] if daily_stats else 0,
            'daily_amount': daily_stats[1] if daily_stats and daily_stats[1] else 0
        }

    def get_recent_referrals(self, user_id: int, limit: int = 10) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT r.*, u.username, u.full_name
        FROM referrals r
        JOIN users u ON r.referred_id = u.user_id
        WHERE r.referrer_id = ?
        ORDER BY r.date DESC
        LIMIT ?
        """, (user_id, limit))

        referrals = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            referrals.append(dict(zip(columns, row)))
        return referrals

    # Admin statistikasi
    def get_total_users(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

    def get_total_referrals(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM referrals")
        return cursor.fetchone()[0]

    def get_total_paid(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM referrals")
        result = cursor.fetchone()[0]
        return result if result else 0

    def get_top_referrers(self, limit: int = 5) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT 
            u.user_id,
            u.username,
            u.full_name,
            COUNT(r.id) as referrals_count,
            SUM(r.amount) as total_amount
        FROM referrals r
        JOIN users u ON r.referrer_id = u.user_id
        GROUP BY r.referrer_id
        ORDER BY referrals_count DESC
        LIMIT ?
        """, (limit,))

        top_referrers = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            top_referrers.append(dict(zip(columns, row)))
        return top_referrers

    def get_recent_users(self, limit: int = 20) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT * FROM users
        ORDER BY registration_date DESC
        LIMIT ?
        """, (limit,))

        users = []
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            users.append(dict(zip(columns, row)))
        return users

    def __del__(self):
        self.conn.close()