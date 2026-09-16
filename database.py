# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = "data/bot.db"


def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE, name TEXT, username TEXT, joined_at TEXT, channel_verified INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, emoji TEXT DEFAULT 'X', image_id TEXT DEFAULT '', position INTEGER DEFAULT 0, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, emoji TEXT DEFAULT 'X', image_id TEXT DEFAULT '', phone TEXT DEFAULT '', position INTEGER DEFAULT 0, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, subcategory_id INTEGER, name TEXT, emoji TEXT DEFAULT 'X', position INTEGER DEFAULT 0, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, subcategory_id INTEGER, name TEXT, description TEXT DEFAULT '', image_id TEXT DEFAULT '', data_type TEXT DEFAULT 'id', pricing_type TEXT DEFAULT 'fixed', price_syp TEXT DEFAULT '', price_usd TEXT DEFAULT '', rate_syp REAL DEFAULT 0, rate_usd REAL DEFAULT 0, min_qty REAL DEFAULT 0, max_qty REAL DEFAULT 0, commission_percent REAL DEFAULT 0, unit_name TEXT DEFAULT '', position INTEGER DEFAULT 0, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_id INTEGER, service_name TEXT, category_name TEXT, subcategory_name TEXT, group_name TEXT DEFAULT '', price_text TEXT, account_id TEXT, data_type TEXT DEFAULT 'id', qty_input TEXT DEFAULT '', final_price TEXT DEFAULT '', status TEXT DEFAULT 'pending', receipt_photo TEXT, txn_number TEXT, payment_method TEXT DEFAULT '', admin_note TEXT, created_at TEXT, updated_at TEXT)")
    conn.commit()
    conn.close()
    print("DB_OK")


def add_user(tid, name, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (telegram_id, name, username, joined_at) VALUES (?, ?, ?, ?)", (tid, name, username or "", datetime.now().isoformat()))
    conn.commit()
    conn.close()


def is_channel_verified(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_verified FROM users WHERE telegram_id=?", (tid,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1


def set_channel_verified(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET channel_verified=1 WHERE telegram_id=?", (tid,))
    conn.commit()
    conn.close()


def add_category(name, emoji="X"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name, emoji) VALUES (?, ?)", (name, emoji))
        cid = c.lastrowid
        conn.commit()
        return cid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_categories(only_active=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, name, emoji, image_id FROM categories WHERE active=1 ORDER BY position, id")
    else:
        c.execute("SELECT id, name, emoji, image_id, active FROM categories ORDER BY position, id")
    rows = c.fetchall()
    conn.close()
    return rows


def get_category(cat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, emoji, image_id FROM categories WHERE id=?", (cat_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_category(cat_id, name=None, emoji=None, image_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if name:
        c.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
    if emoji:
        c.execute("UPDATE categories SET emoji=? WHERE id=?", (emoji, cat_id))
    if image_id is not None:
        c.execute("UPDATE categories SET image_id=? WHERE id=?", (image_id, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM subcategories WHERE category_id=?", (cat_id,))
    for (sub_id,) in c.fetchall():
        c.execute("SELECT id FROM groups WHERE subcategory_id=?", (sub_id,))
        for (grp_id,) in c.fetchall():
            c.execute("DELETE FROM services WHERE group_id=?", (grp_id,))
        c.execute("DELETE FROM groups WHERE subcategory_id=?", (sub_id,))
    c.execute("DELETE FROM subcategories WHERE category_id=?", (cat_id,))
    c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()


def add_subcategory(category_id, name, emoji="X"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO subcategories (category_id, name, emoji) VALUES (?, ?, ?)", (category_id, name, emoji))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_subcategories(category_id, only_active=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, name, emoji, image_id, phone FROM subcategories WHERE category_id=? AND active=1 ORDER BY position, id", (category_id,))
    else:
        c.execute("SELECT id, name, emoji, image_id, phone, active FROM subcategories WHERE category_id=? ORDER BY position, id", (category_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_subcategory(sub_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, emoji, image_id, phone, category_id FROM subcategories WHERE id=?", (sub_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_subcategory(sub_id, name=None, emoji=None, image_id=None, phone=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if name:
        c.execute("UPDATE subcategories SET name=? WHERE id=?", (name, sub_id))
    if emoji:
        c.execute("UPDATE subcategories SET emoji=? WHERE id=?", (emoji, sub_id))
    if image_id is not None:
        c.execute("UPDATE subcategories SET image_id=? WHERE id=?", (image_id, sub_id))
    if phone is not None:
        c.execute("UPDATE subcategories SET phone=? WHERE id=?", (phone, sub_id))
    conn.commit()
    conn.close()


def delete_subcategory(sub_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM groups WHERE subcategory_id=?", (sub_id,))
    for (grp_id,) in c.fetchall():
        c.execute("DELETE FROM services WHERE group_id=?", (grp_id,))
    c.execute("DELETE FROM groups WHERE subcategory_id=?", (sub_id,))
    c.execute("DELETE FROM subcategories WHERE id=?", (sub_id,))
    conn.commit()
    conn.close()


def add_group(subcategory_id, name, emoji="X"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO groups (subcategory_id, name, emoji) VALUES (?, ?, ?)", (subcategory_id, name, emoji))
    gid = c.lastrowid
    conn.commit()
    conn.close()
    return gid


def get_groups(subcategory_id, only_active=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, name, emoji FROM groups WHERE subcategory_id=? AND active=1 ORDER BY position, id", (subcategory_id,))
    else:
        c.execute("SELECT id, name, emoji, active FROM groups WHERE subcategory_id=? ORDER BY position, id", (subcategory_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_group(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, emoji, subcategory_id FROM groups WHERE id=?", (group_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_group(group_id, name=None, emoji=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if name:
        c.execute("UPDATE groups SET name=? WHERE id=?", (name, group_id))
    if emoji:
        c.execute("UPDATE groups SET emoji=? WHERE id=?", (emoji, group_id))
    conn.commit()
    conn.close()


def delete_group(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE group_id=?", (group_id,))
    c.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.commit()
    conn.close()


def add_service(group_id, name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT subcategory_id FROM groups WHERE id=?", (group_id,))
    row = c.fetchone()
    sub_id = row[0] if row else 0
    c.execute("INSERT INTO services (group_id, subcategory_id, name) VALUES (?, ?, ?)", (group_id, sub_id, name))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_services(group_id, only_active=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, name, pricing_type, price_syp, price_usd FROM services WHERE group_id=? AND active=1 ORDER BY position, id", (group_id,))
    else:
        c.execute("SELECT id, name, pricing_type, price_syp, price_usd, active FROM services WHERE group_id=? ORDER BY position, id", (group_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_service(service_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, description, image_id, data_type, group_id, subcategory_id, pricing_type, price_syp, price_usd, rate_syp, rate_usd, min_qty, max_qty, commission_percent, unit_name FROM services WHERE id=?", (service_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_service(service_id, **kwargs):
    if not kwargs:
        return
    allowed = ["name", "description", "image_id", "data_type", "pricing_type", "price_syp", "price_usd", "rate_syp", "rate_usd", "min_qty", "max_qty", "commission_percent", "unit_name", "active", "position"]
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(k + "=?")
            vals.append(v)
    if not sets:
        return
    vals.append(service_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE services SET " + ", ".join(sets) + " WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_service(service_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id=?", (service_id,))
    conn.commit()
    conn.close()


def create_order(user_id, service_id, service_name, category_name, subcategory_name, group_name, price_text, account_id, data_type="id"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, service_id, service_name, category_name, subcategory_name, group_name, price_text, account_id, data_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, service_id, service_name, category_name, subcategory_name, group_name, price_text, account_id, data_type, datetime.now().isoformat()))
    oid = c.lastrowid
    conn.commit()
    conn.close()
    return oid


def update_order(order_id, **kwargs):
    if not kwargs:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    sets = ", ".join([k + "=?" for k in kwargs.keys()])
    vals = list(kwargs.values()) + [datetime.now().isoformat(), order_id]
    c.execute("UPDATE orders SET " + sets + ", updated_at=? WHERE id=?", vals)
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_user_orders(user_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, service_name, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='approved'")
    approved = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='shipped'")
    shipped = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'")
    rejected = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM categories")
    cats = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM subcategories")
    subs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM groups")
    grps = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM services")
    srvs = c.fetchone()[0]
    conn.close()
    return {"users": users_count, "total_orders": total_orders, "pending": pending, "approved": approved, "shipped": shipped, "rejected": rejected, "categories": cats, "subcategories": subs, "groups": grps, "services": srvs}


def get_direct_services(subcategory_id, only_active=True):
    """الخدمات المباشرة في فرع (بدون تصنيف)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, name, pricing_type, price_syp, price_usd FROM services WHERE subcategory_id=? AND (group_id IS NULL OR group_id=0) AND active=1 ORDER BY position, id", (subcategory_id,))
    else:
        c.execute("SELECT id, name, pricing_type, price_syp, price_usd, active FROM services WHERE subcategory_id=? AND (group_id IS NULL OR group_id=0) ORDER BY position, id", (subcategory_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def add_direct_service(subcategory_id, name):
    """إضافة خدمة مباشرة لفرع (بدون تصنيف)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO services (group_id, subcategory_id, name) VALUES (0, ?, ?)", (subcategory_id, name))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid
