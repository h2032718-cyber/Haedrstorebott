# -*- coding: utf-8 -*-

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ChatMember
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError, BadRequest

from config import (
    BOT_TOKEN, ADMIN_ID, WALLETS, CURRENCY, BOT_NAME,
    CHANNEL_USERNAME, CHANNEL_URL, SUPPORT_URL, SUPPORT_USERNAME
)
from database import (
    init_db, add_user, is_channel_verified, set_channel_verified,
    get_categories, get_category,
    get_subcategories, get_subcategory,
    get_groups, get_group,
    get_services, get_service,
    get_quantities, add_quantity, delete_quantity,
    get_quantity, update_quantity, delete_quantities_for_service,
    add_category, update_category, delete_category,
    add_subcategory, update_subcategory, delete_subcategory,
    add_group, update_group, delete_group,
    add_service, update_service, delete_service,
    create_order, update_order, get_order, get_user_orders,
    get_stats,
    get_direct_services, add_direct_service
)
from error_handler import error_handler

import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

pending_orders = {}
admin_states = {}


def main_menu():
    keyboard = [
        [KeyboardButton("🛒 الخدمات"), KeyboardButton("📋 طلباتي")],
        [KeyboardButton("💰 معلومات الدفع"), KeyboardButton("📞 الدعم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_menu():
    keyboard = [
        [KeyboardButton("📊 إحصائيات"), KeyboardButton("📁 الفئات")],
        [KeyboardButton("📦 الطلبات"), KeyboardButton("🔙 رجوع")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def check_channel_membership(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return True
        return False
    except TelegramError as e:
        logger.error(f"Channel check failed: {e}")
        return False


def channel_gate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 انضم للقناة", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ تحققت من المتابعة", callback_data="check_channel")]
    ])


async def show_channel_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📢 مرحباً بك\n\n"
        "للاستفادة من خدمات البوت، يجب عليك أولاً:\n\n"
        "1️⃣ الاشتراك في قناتنا الرسمية\n"
        "2️⃣ العودة والضغط على (✅ تحققت من المتابعة)\n\n"
        f"🔗 القناة: {CHANNEL_USERNAME}"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=channel_gate_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=channel_gate_keyboard())


async def check_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    is_member = await check_channel_membership(user.id, context)
    if is_member:
        set_channel_verified(user.id)
        await edit_or_reply(query, "✅ تم التحقق بنجاح\n\nاضغط /start للبدء")
    else:
        await query.answer("❌ لم يتم التحقق", show_alert=True)


async def edit_or_reply(query, text, **kwargs):
    """تعدّل الرسالة أو ترسل جديدة إذا الرسالة صورة"""
    try:
        await query.edit_message_text(text, **kwargs)
    except (TelegramError, BadRequest, Exception) as e:
        # أي خطأ → احذف الرسالة القديمة وأرسل جديدة
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await query.message.reply_text(text, **kwargs)
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.full_name, user.username)
    if not is_channel_verified(user.id):
        await show_channel_gate(update, context)
        return
    await update.message.reply_text(
        f"👋 أهلاً بك {user.first_name}\n\n"
        f"⚡ في {BOT_NAME}\n\n"
        f"اختر من القائمة:",
        reply_markup=main_menu()
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_menu())


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("🛠 لوحة التحكم\n\nاختر ما تريد:", reply_markup=admin_menu())


async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_channel_verified(user.id):
        await show_channel_gate(update, context)
        return
    categories = get_categories()
    if not categories:
        await update.message.reply_text("⚠️ لا توجد فئات حالياً")
        return
    keyboard = []
    for cat in categories:
        cat_id, cat_name, cat_emoji = cat[0], cat[1], cat[2]
        keyboard.append([InlineKeyboardButton(f"{cat_emoji} {cat_name}", callback_data=f"cat_{cat_id}")])
    await update.message.reply_text("🛒 اختر الفئة:", reply_markup=InlineKeyboardMarkup(keyboard))


async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("cat_", ""))
    cat = get_category(cat_id)
    if not cat:
        await edit_or_reply(query, "❌ الفئة غير موجودة")
        return
    subs = get_subcategories(cat_id)
    if not subs:
        keyboard = [[InlineKeyboardButton("◀️ رجوع", callback_data="back_cats")]]
        await edit_or_reply(query, f"{cat[2]} {cat[1]}\n\n⚠️ لا توجد فروع", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = []
    for sub in subs:
        sub_id, sub_name, sub_emoji = sub[0], sub[1], sub[2]
        keyboard.append([InlineKeyboardButton(f"{sub_emoji} {sub_name}", callback_data=f"sub_{sub_id}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data="back_cats")])
    await edit_or_reply(query, f"{cat[2]} {cat[1]}\n\nاختر الفرع:", reply_markup=InlineKeyboardMarkup(keyboard))


async def back_cats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = get_categories()
    keyboard = []
    for cat in categories:
        cat_id, cat_name, cat_emoji = cat[0], cat[1], cat[2]
        keyboard.append([InlineKeyboardButton(f"{cat_emoji} {cat_name}", callback_data=f"cat_{cat_id}")])
    await edit_or_reply(query, "🛒 اختر الفئة:", reply_markup=InlineKeyboardMarkup(keyboard))


async def subcategory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("sub_", ""))
    sub = get_subcategory(sub_id)
    if not sub:
        await edit_or_reply(query, "❌ الفرع غير موجود")
        return
    sub_id, sub_name, sub_emoji, sub_img, sub_phone, cat_id = sub[0], sub[1], sub[2], sub[3], sub[4], sub[5]
    info_text = f"{sub_emoji} {sub_name}\n"
    if sub_phone:
        info_text += f"📞 {sub_phone}\n"
    groups = get_groups(sub_id)
    direct = get_direct_services(sub_id)
    if not groups and not direct:
        keyboard = [[InlineKeyboardButton("◀️ رجوع", callback_data=f"cat_{cat_id}")]]
        out = info_text + "\n⚠️ لا توجد خدمات"
        if sub_img:
            try:
                await query.message.reply_photo(photo=sub_img, caption=out, reply_markup=InlineKeyboardMarkup(keyboard))
                await query.message.delete()
                return
            except Exception:
                pass
        await edit_or_reply(query, out, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = []
    for grp in groups:
        grp_id, grp_name, grp_emoji = grp[0], grp[1], grp[2]
        keyboard.append([InlineKeyboardButton(f"{grp_emoji} {grp_name}", callback_data=f"grp_{grp_id}")])
    for s in direct:
        sid, sname = s[0], s[1]
        keyboard.append([InlineKeyboardButton(f"🎁 {sname}", callback_data=f"srv_{sid}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"cat_{cat_id}")])
    out = info_text + "\nاختر:"
    if sub_img:
        try:
            await query.message.reply_photo(photo=sub_img, caption=out, reply_markup=InlineKeyboardMarkup(keyboard))
            await query.message.delete()
            return
        except Exception:
            pass
    await edit_or_reply(query, out, reply_markup=InlineKeyboardMarkup(keyboard))


async def group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    grp_id = int(query.data.replace("grp_", ""))
    grp = get_group(grp_id)
    if not grp:
        await edit_or_reply(query, "❌ التصنيف غير موجود")
        return
    grp_id, grp_name, grp_emoji, sub_id = grp[0], grp[1], grp[2], grp[3]
    services = get_services(grp_id)
    if not services:
        keyboard = [[InlineKeyboardButton("◀️ رجوع", callback_data=f"sub_{sub_id}")]]
        await edit_or_reply(query, f"{grp_emoji} {grp_name}\n\n⚠️ لا توجد خدمات", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = []
    for s in services:
        sid, sname = s[0], s[1]
        keyboard.append([InlineKeyboardButton(sname, callback_data=f"srv_{sid}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"sub_{sub_id}")])
    await edit_or_reply(query, f"{grp_emoji} {grp_name}\n\nاختر الخدمة:", reply_markup=InlineKeyboardMarkup(keyboard))
# ==========================================
# معالج الخدمة
# ==========================================

async def qty_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # callback_data: "qtypick_{qty_id}_{srv_id}"
    parts = query.data.split("_")
    qty_id = int(parts[1])
    srv_id = int(parts[2])
    qty = get_quantity(qty_id)
    if not qty:
        await edit_or_reply(query, "❌ الكمية غير موجودة")
        return
    _, _, label, psyp, pusd = qty
    srv = get_service(srv_id)
    if not srv:
        await edit_or_reply(query, "❌ الخدمة غير موجودة")
        return
    srv_name = srv[1]
    sub_id = srv[6]
    grp_id = srv[5]
    sub = get_subcategory(sub_id)
    grp = get_group(grp_id)
    sub_name = sub[1] if sub else ""
    grp_name = grp[1] if grp else ""
    data_type = srv[4] or "id"
    # احفظ الطلب في pending_orders
    pending_orders[query.from_user.id] = {
        "service_id": srv_id,
        "service_name": srv_name,
        "subcategory_name": sub_name,
        "group_name": grp_name,
        "data_type": data_type,
        "price_syp": psyp or "",
        "price_usd": pusd or "",
        "quantity_label": label,
    }
    text = f"📦 *{srv_name}*\n🎯 الكمية: *{label}*\n\n💰 *اختر طريقة الدفع:*"
    keyboard = []
    if psyp:
        keyboard.append([InlineKeyboardButton(f"💰 سيرياتيل — {psyp} ل.س", callback_data="pay_syriatel")])
        keyboard.append([InlineKeyboardButton(f"💵 شام كاش — {psyp} ل.س", callback_data="pay_sham_syp")])
    if pusd:
        keyboard.append([InlineKeyboardButton(f"💵 شام كاش — ${pusd}", callback_data="pay_sham_usd")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"srv_{srv_id}")])
    await edit_or_reply(query, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    srv_id = int(query.data.replace("srv_", ""))
    srv = get_service(srv_id)
    if not srv:
        await edit_or_reply(query, "❌ الخدمة غير موجودة")
        return
    srv_id = srv[0]
    srv_name = srv[1]
    srv_desc = srv[2]
    srv_img = srv[3]
    data_type = srv[4]
    grp_id = srv[5]
    sub_id = srv[6]
    psyp = srv[8]
    pusd = srv[9]

    sub = get_subcategory(sub_id)
    grp = get_group(grp_id)
    sub_name = sub[1] if sub else ""
    grp_name = grp[1] if grp else ""

    pending_orders[query.from_user.id] = {
        "service_id": srv_id,
        "service_name": srv_name,
        "subcategory_name": sub_name,
        "group_name": grp_name,
        "data_type": data_type or "id",
        "price_syp": psyp or "",
        "price_usd": pusd or "",
    }

    # ✅ Patch 10: عرض الكميات إذا موجودة
    qty_list = get_quantities(srv_id)
    if qty_list:
        text = f"📦 *{srv_name}*\n"
        if srv_desc:
            text += f"📝 {srv_desc}\n"
        text += "\n🎯 *اختر الفئة:*"
        keyboard = []
        for q in qty_list:
            qid, label, qsyp, qusd = q
            price_txt = []
            if qsyp:
                price_txt.append(f"{qsyp} ل.س")
            if qusd:
                price_txt.append(f"${qusd}")
            btn_text = f"📦 {label} — {' | '.join(price_txt)}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"qtypick_{qid}_{srv_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"sub_{sub_id}")])
        if srv_img:
            try:
                await query.message.reply_photo(photo=srv_img, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                await query.message.delete()
                return
            except Exception:
                pass
        await edit_or_reply(query, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # لا توجد كميات — السلوك القديم
    text = f"📦 *{srv_name}*\n"
    if srv_desc:
        text += f"📝 {srv_desc}\n"
    text += "\n💰 *اختر طريقة الدفع:*"

    keyboard = []
    if psyp:
        keyboard.append([InlineKeyboardButton(f"💰 سيرياتيل كاش — {psyp}", callback_data="pay_syriatel")])
        keyboard.append([InlineKeyboardButton(f"💵 شام كاش — {psyp}", callback_data="pay_sham_syp")])
    if pusd:
        keyboard.append([InlineKeyboardButton(f"💵 شام كاش — {pusd}", callback_data="pay_sham_usd")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"sub_{sub_id}")])

    if srv_img:
        try:
            await query.message.reply_photo(photo=srv_img, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            await query.message.delete()
            return
        except Exception:
            pass
    await edit_or_reply(query, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def payment_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = pending_orders.get(user.id)
    if not data:
        await edit_or_reply(query, "❌ انتهت الجلسة، ابدأ من جديد /start")
        return
    choice = query.data
    if choice == "pay_syriatel":
        wallet = "سيرياتيل كاش"
        amount = data.get("price_syp", "")
    elif choice == "pay_sham_syp":
        wallet = "شام كاش (ل.س)"
        amount = data.get("price_syp", "")
    elif choice == "pay_sham_usd":
        wallet = "شام كاش (دولار)"
        amount = data.get("price_usd", "")
    else:
        return
    data["payment_method"] = wallet
    data["price_text"] = amount

    await edit_or_reply(query, 
        f"✅ اخترت: *{wallet}*\n"
        f"💵 المبلغ: {amount}\n\n"
    f"{('📱 أرسل رقم هاتفك:' if data.get('data_type') == 'phone' else '✏️ أرسل الآن ID حسابك:')}",
        parse_mode="Markdown"
    )


async def receive_account_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = pending_orders.get(user.id)
    if not data or "service_id" not in data:
        return
    if "account_id" in data:
        return
    account_id = update.message.text.strip()
    data["account_id"] = account_id
    wallets_lines = []
    for name, num in WALLETS.items():
        wallets_lines.append(f"• {name}:\n  `{num}`")
    wallets_text = "\n\n".join(wallets_lines)
    price_text = data.get("price_text", "") or data.get("final_price", "")
    price_block = f"\n💵 المبلغ:\n{price_text}\n" if price_text else "\n"
    text = (
        f"✅ تم تسجيل البيانات: {account_id}\n\n"
        f"📦 {data['service_name']}\n"
        f"{price_block}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💳 حوّل المبلغ إلى:\n\n{wallets_text}\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ بعد التحويل:\n"
        f"1️⃣ اضغط زر دفعت\n"
        f"2️⃣ أرسل صورة الإشعار\n"
        f"3️⃣ ثم رقم العملية"
    )
    keyboard = [
        [InlineKeyboardButton("✅ دفعت", callback_data="confirm_pay")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_order")]
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def confirm_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = pending_orders.get(query.from_user.id)
    if not data:
        await edit_or_reply(query, "❌ انتهت الجلسة، ابدأ من جديد /start")
        return
    data["awaiting"] = "photo"
    await edit_or_reply(query, "📸 أرسل الآن صورة إشعار التحويل:")


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_orders.pop(query.from_user.id, None)
    await edit_or_reply(query, "❌ تم إلغاء الطلب\nللبدء من جديد اضغط /start")


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = pending_orders.get(user.id)
    if not data or data.get("awaiting") != "photo":
        return
    photo = update.message.photo[-1]
    data["photo"] = photo.file_id
    data["awaiting"] = "txn"
    await update.message.reply_text("✅ تم استلام الصورة\n\n🔢 أرسل الآن رقم العملية:")


async def receive_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = pending_orders.get(user.id)
    if not data or data.get("awaiting") != "txn":
        return
    txn = update.message.text.strip()
    oid = create_order(
        user_id=user.id,
        service_id=data["service_id"],
        service_name=data["service_name"],
        category_name="",
        subcategory_name=data.get("subcategory_name", ""),
        group_name=data.get("group_name", ""),
        price_text=data.get("price_text", "") or data.get("final_price", ""),
        account_id=data.get("account_id", ""),
        data_type=data.get("data_type", "id")
    )
    update_order(oid, receipt_photo=data["photo"], txn_number=txn)
    price_line = ""
    if data.get("price_text"):
        price_line = f"💵 المبلغ: {data['price_text']}\n"
    dtype = data.get("data_type", "id")
    dtype_label = "📱 رقم الهاتف" if dtype == "phone" else "🎯 ID اللاعب"
    admin_caption = (
        f"🔔 طلب جديد #{oid}\n\n"
        f"👤 العميل: {user.full_name}\n"
        f"🆔 @{user.username or 'لا يوجد'}\n"
        f"📱 ID: `{user.id}`\n\n"
        f"📦 {data['service_name']}\n"
        f"📂 الفرع: {data.get('subcategory_name', '-')}\n"
        f"📋 التصنيف: {data.get('group_name', '-')}\n"
        f"{dtype_label}: `{data.get('account_id', '-')}`\n"
        f"{price_line}"
        f"🔢 رقم العملية: `{txn}`"
    )
    keyboard = [[
        InlineKeyboardButton("✅ موافقة", callback_data=f"approve_{oid}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject_{oid}")
    ]]
    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID, photo=data["photo"], caption=admin_caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")
    try:
        await update.message.reply_text(
            f"✅ تم استلام طلبك #{oid}\n\n⏳ طلبك قيد المعالجة",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Customer notify failed: {e}")
    pending_orders.pop(user.id, None)


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_channel_verified(user.id):
        await show_channel_gate(update, context)
        return
    orders = get_user_orders(user.id)
    if not orders:
        await update.message.reply_text("📭 لا توجد طلبات حتى الآن")
        return
    smap = {"pending": "⏳ قيد المراجعة", "approved": "✅ مقبول", "shipped": "🎉 تم الشحن", "rejected": "❌ مرفوض"}
    text = "📋 آخر طلباتك:\n\n"
    for o in orders:
        text += f"#{o[0]} — {o[1]}\n{smap.get(o[2], '❓')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_channel_verified(user.id):
        await show_channel_gate(update, context)
        return
    text = "💰 طرق الدفع المتاحة:\n\n"
    for name, num in WALLETS.items():
        text += f"• {name}:\n  `{num}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📞 الدعم الفني\n\n👤 {SUPPORT_USERNAME}\n\n🔗 {SUPPORT_URL}")


async def order_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("غير مصرح", show_alert=True)
        return
    parts = query.data.split("_")
    action = parts[0]
    oid = int(parts[1])
    order = get_order(oid)
    if not order:
        try:
            await query.edit_message_caption("الطلب غير موجود")
        except Exception:
            pass
        return
    user_id = order[1]
    if action == "approve":
        update_order(oid, status="approved")
        new_kb = [[
            InlineKeyboardButton("📤 تم الشحن", callback_data=f"shipped_{oid}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject_{oid}")
        ]]
        try:
            await query.edit_message_caption((query.message.caption or "") + "\n\n✅ تمت الموافقة", reply_markup=InlineKeyboardMarkup(new_kb))
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ تمت الموافقة على طلبك #{oid}")
        except Exception as e:
            logger.error(f"Notify failed: {e}")
    elif action == "shipped":
        update_order(oid, status="shipped")
        try:
            await query.edit_message_caption((query.message.caption or "") + "\n\n🎉 تم الشحن")
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=user_id, text=f"🎉 تم شحن حسابك بنجاح\n\nللدعم: {SUPPORT_URL}")
        except Exception as e:
            logger.error(f"Notify failed: {e}")
    elif action == "reject":
        update_order(oid, status="rejected")
        try:
            await query.edit_message_caption((query.message.caption or "") + "\n\n❌ تم الرفض")
        except Exception:
            pass
        try:
            await context.bot.send_message(chat_id=user_id, text=f"❌ تم رفض طلبك #{oid}")
        except Exception as e:
            logger.error(f"Notify failed: {e}")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    s = get_stats()
    text = (
        f"📊 إحصائيات\n\n"
        f"👥 المستخدمون: {s['users']}\n"
        f"📦 الطلبات: {s['total_orders']}\n"
        f"⏳ معلقة: {s['pending']}\n"
        f"✅ مقبولة: {s['approved']}\n"
        f"🎉 مشحونة: {s['shipped']}\n"
        f"❌ مرفوضة: {s['rejected']}\n\n"
        f"📁 الفئات: {s['categories']}\n"
        f"📂 الفروع: {s['subcategories']}\n"
        f"📋 التصنيفات: {s['groups']}\n"
        f"🎁 الخدمات: {s['services']}"
    )
    await update.message.reply_text(text)


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("📦 الطلبات تصلك تلقائياً عند إنشائها")


async def admin_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    categories = get_categories(only_active=False)
    keyboard = []
    for cat in categories:
        cat_id, cat_name, cat_emoji = cat[0], cat[1], cat[2]
        keyboard.append([InlineKeyboardButton(f"{cat_emoji} {cat_name}", callback_data=f"adm_cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة فئة", callback_data="adm_add_cat")])
    await update.message.reply_text("📁 إدارة الفئات:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_back_cats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = get_categories(only_active=False)
    keyboard = []
    for cat in categories:
        cat_id, cat_name, cat_emoji = cat[0], cat[1], cat[2]
        keyboard.append([InlineKeyboardButton(f"{cat_emoji} {cat_name}", callback_data=f"adm_cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة فئة", callback_data="adm_add_cat")])
    await edit_or_reply(query, "📁 إدارة الفئات:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_category_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_cat_", ""))
    cat = get_category(cat_id)
    if not cat:
        await edit_or_reply(query, "❌ الفئة غير موجودة")
        return
    subs = get_subcategories(cat_id, only_active=False)
    text = f"📁 {cat[2]} {cat[1]}\n\nعدد الفروع: {len(subs)}"
    keyboard = [
        [InlineKeyboardButton("📂 إدارة الفروع", callback_data=f"adm_subs_{cat_id}")],
        [InlineKeyboardButton("🖼 صورة الفئة", callback_data=f"adm_catphoto_{cat_id}")],
        [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_editcat_{cat_id}")],
        [InlineKeyboardButton("🗑️ حذف الفئة", callback_data=f"adm_delcat_{cat_id}")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="adm_back_cats")]
    ]
    await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_cat_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_catphoto_", ""))
    admin_states[query.from_user.id] = {"action": "cat_photo", "cat_id": cat_id}
    await edit_or_reply(query, 
        "🖼 *إضافة صورة للفئة*\n\n"
        "أرسل الصورة الآن 📷\n\n"
        "⚠️ ملاحظة: الصورة رح تحل مكان الإيموجي في عرض الفئات للعميل.\n"
        "🔙 للإلغاء أرسل /start",
        parse_mode="Markdown"
    )


async def admin_add_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_states[query.from_user.id] = {"action": "add_cat"}
    await edit_or_reply(query, "➕ إضافة فئة\n\nأرسل: اسم الفئة | الإيموجي\nمثال: ألعاب | 🎮")


async def admin_edit_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_editcat_", ""))
    admin_states[query.from_user.id] = {"action": "edit_cat", "cat_id": cat_id}
    await edit_or_reply(query, "✏️ أرسل: اسم جديد | إيموجي")


async def admin_del_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_delcat_", ""))
    delete_category(cat_id)
    await edit_or_reply(query, "✅ تم حذف الفئة")


async def admin_subs_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_subs_", ""))
    cat = get_category(cat_id)
    subs = get_subcategories(cat_id, only_active=False)
    keyboard = []
    for sub in subs:
        sub_id, sub_name, sub_emoji = sub[0], sub[1], sub[2]
        keyboard.append([InlineKeyboardButton(f"{sub_emoji} {sub_name}", callback_data=f"adm_sub_{sub_id}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة فرع", callback_data=f"adm_addsub_{cat_id}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_cat_{cat_id}")])
    await edit_or_reply(query, f"📂 فروع {cat[1]}\n\nعدد: {len(subs)}", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_sub_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_subphoto_", ""))
    admin_states[query.from_user.id] = {"action": "sub_photo", "sub_id": sub_id}
    await edit_or_reply(query, 
        "🖼 *إضافة صورة للفرع*\n\n"
        "أرسل الصورة الآن 📷\n\n"
        "🔙 للإلغاء أرسل /start",
        parse_mode="Markdown"
    )


async def admin_sub_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_sub_", ""))
    sub = get_subcategory(sub_id)
    if not sub:
        await edit_or_reply(query, "❌ الفرع غير موجود")
        return
    sub_id, sub_name, sub_emoji, sub_img, sub_phone, cat_id = sub[0], sub[1], sub[2], sub[3], sub[4], sub[5]
    groups = get_groups(sub_id, only_active=False)
    direct = get_direct_services(sub_id, only_active=False)
    text = f"📂 {sub_emoji} {sub_name}\n"
    if sub_phone:
        text += f"📞 {sub_phone}\n"
    text += f"\nعدد التصنيفات: {len(groups)}"
    text += f"\nعدد الخدمات المباشرة: {len(direct)}"
    keyboard = [
        [InlineKeyboardButton("📋 إدارة التصنيفات", callback_data=f"adm_grps_{sub_id}")],
        [InlineKeyboardButton(f"🎁 الخدمات المباشرة ({len(direct)})", callback_data=f"adm_direct_{sub_id}")],
        [InlineKeyboardButton("📞 تعديل الهاتف", callback_data=f"adm_subphone_{sub_id}")],
        [InlineKeyboardButton("🖼 صورة الفرع", callback_data=f"adm_subphoto_{sub_id}")],
        [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_editsub_{sub_id}")],
        [InlineKeyboardButton("🗑️ حذف الفرع", callback_data=f"adm_delsub_{sub_id}")],
        [InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_subs_{cat_id}")]
    ]
    await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_add_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_addsub_", ""))
    admin_states[query.from_user.id] = {"action": "add_sub", "cat_id": cat_id}
    await edit_or_reply(query, "➕ إضافة فرع\n\nأرسل: اسم الفرع | الإيموجي")


async def admin_edit_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_editsub_", ""))
    admin_states[query.from_user.id] = {"action": "edit_sub", "sub_id": sub_id}
    await edit_or_reply(query, "✏️ أرسل: اسم جديد | إيموجي")


async def admin_del_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_delsub_", ""))
    delete_subcategory(sub_id)
    await edit_or_reply(query, "✅ تم حذف الفرع")


async def admin_subphone_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_subphone_", ""))
    admin_states[query.from_user.id] = {"action": "edit_sub_phone", "sub_id": sub_id}
    await edit_or_reply(query, "📞 أرسل رقم الهاتف:")


async def admin_direct_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_direct_", ""))
    sub = get_subcategory(sub_id)
    if not sub:
        await edit_or_reply(query, "❌ الفرع غير موجود")
        return
    services = get_direct_services(sub_id, only_active=False)
    keyboard = []
    for s in services:
        sid, sname = s[0], s[1]
        keyboard.append([InlineKeyboardButton(sname, callback_data=f"adm_srv_{sid}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة خدمة مباشرة", callback_data=f"adm_adddirect_{sub_id}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_sub_{sub_id}")])
    await edit_or_reply(query, 
        f"🎁 خدمات {sub[1]} المباشرة\n\nعدد: {len(services)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_add_direct_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_adddirect_", ""))
    admin_states[query.from_user.id] = {"action": "add_direct", "sub_id": sub_id}
    await edit_or_reply(query, "➕ إضافة خدمة مباشرة\n\nأرسل اسم الخدمة:")


async def admin_grps_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_grps_", ""))
    sub = get_subcategory(sub_id)
    groups = get_groups(sub_id, only_active=False)
    keyboard = []
    for g in groups:
        gid, gname, gemoji = g[0], g[1], g[2]
        keyboard.append([InlineKeyboardButton(f"{gemoji} {gname}", callback_data=f"adm_grp_{gid}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة تصنيف", callback_data=f"adm_addgrp_{sub_id}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_sub_{sub_id}")])
    await edit_or_reply(query, f"📋 تصنيفات {sub[1]}\n\nعدد: {len(groups)}", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_grp_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.replace("adm_grp_", ""))
    g = get_group(gid)
    if not g:
        await edit_or_reply(query, "❌ التصنيف غير موجود")
        return
    gid, gname, gemoji, sub_id = g[0], g[1], g[2], g[3]
    services = get_services(gid, only_active=False)
    text = f"📋 {gemoji} {gname}\n\nعدد الخدمات: {len(services)}"
    keyboard = [
        [InlineKeyboardButton("🎁 إدارة الخدمات", callback_data=f"adm_srvs_{gid}")],
        [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_editgrp_{gid}")],
        [InlineKeyboardButton("🗑️ حذف التصنيف", callback_data=f"adm_delgrp_{gid}")],
        [InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_grps_{sub_id}")]
    ]
    await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_add_grp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_addgrp_", ""))
    admin_states[query.from_user.id] = {"action": "add_grp", "sub_id": sub_id}
    await edit_or_reply(query, "➕ إضافة تصنيف\n\nأرسل: اسم التصنيف | الإيموجي")


async def admin_edit_grp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.replace("adm_editgrp_", ""))
    admin_states[query.from_user.id] = {"action": "edit_grp", "grp_id": gid}
    await edit_or_reply(query, "✏️ أرسل: اسم جديد | إيموجي")


async def admin_del_grp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.replace("adm_delgrp_", ""))
    delete_group(gid)
    await edit_or_reply(query, "✅ تم حذف التصنيف")


async def admin_srvs_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.replace("adm_srvs_", ""))
    g = get_group(gid)
    if not g:
        await edit_or_reply(query, "❌ الفرع غير موجود")
        return
    services = get_services(gid, only_active=False)
    keyboard = []
    for s in services:
        sid, sname = s[0], s[1]
        keyboard.append([InlineKeyboardButton(sname, callback_data=f"adm_srv_{sid}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة خدمة", callback_data=f"adm_addsrv_{gid}")])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_grp_{gid}")])
    await edit_or_reply(query, f"🎁 خدمات {g[1]}\n\nعدد: {len(services)}", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_srv_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_srv_", ""))
    srv = get_service(sid)
    if not srv:
        await edit_or_reply(query, "❌ الخدمة غير موجودة")
        return
    (sid, name, desc, img, dt, gid, sub_id, ptype, psyp, pusd,
     rsyp, rusd, minq, maxq, comm, unit, profit, input_method) = srv
    ptype_labels = {"fixed": "💰 سعر ثابت", "rate": "🧮 حاسبة نسبة", "commission": "💵 حاسبة عمولة"}
    method_labels = {"qty": "🔢 بالكمية", "amount": "💰 بالمبلغ", "both": "🔄 الاثنان"}
    text = f"🎁 {name}\n\n💵 التسعير: {ptype_labels.get(ptype, ptype)}\n"
    if ptype == "fixed":
        if psyp:
            text += f"• {psyp}\n"
        if pusd:
            text += f"• {pusd}\n"
    elif ptype == "rate":
        if rsyp:
            text += f"• {rsyp:g} ل.س/وحدة\n"
        if rusd:
            text += f"• ${rusd:g}/وحدة\n"
        if profit:
            text += f"📈 الربح: {profit:g}%\n"
        if minq:
            text += f"⚠️ الأدنى: {minq:g}\n"
        if maxq:
            text += f"⚠️ الأعلى: {maxq:g}\n"
        if input_method:
            text += f"🔀 الإدخال: {method_labels.get(input_method, input_method)}\n"
    elif ptype == "commission":
        text += f"• العمولة: {comm:g}%\n"
    keyboard = [
        [InlineKeyboardButton("📊 إدارة الكميات", callback_data=f"adm_qty_menu_{sid}")],
        [InlineKeyboardButton("📝 نوع البيانات", callback_data=f"adm_srvtype_{sid}")],
        [InlineKeyboardButton("💰 تعديل السعر", callback_data=f"adm_srvprice_{sid}")],
        [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_editsrv_{sid}")],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"adm_delsrv_{sid}")],
        [InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_srvs_{gid}")]
    ]
    await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_add_srv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gid = int(query.data.replace("adm_addsrv_", ""))
    admin_states[query.from_user.id] = {"action": "add_srv", "grp_id": gid}
    await edit_or_reply(query, "➕ إضافة خدمة\n\nأرسل اسم الخدمة:")


async def admin_edit_srv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_editsrv_", ""))
    admin_states[query.from_user.id] = {"action": "edit_srv_name", "srv_id": sid}
    await edit_or_reply(query, "✏️ أرسل الاسم الجديد:")


async def admin_del_srv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_delsrv_", ""))
    delete_service(sid)
    await edit_or_reply(query, "✅ تم حذف الخدمة")




# ═══════════════ إدارة الكميات (Patch 10) ═══════════════
async def admin_qty_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_qty_menu_", ""))
    srv = get_service(sid)
    if not srv:
        await edit_or_reply(query, "❌ الخدمة غير موجودة")
        return
    srv_name = srv[1]
    qty_list = get_quantities(sid)
    
    text = f"📊 إدارة كميات: {srv_name}\n\n"
    if qty_list:
        text += "الكميات المضافة:\n"
        for q in qty_list:
            qid, label, psyp, pusd = q
            parts = [f"• {label}"]
            if psyp:
                parts.append(f"{psyp} ل.س")
            if pusd:
                parts.append(f"${pusd}")
            text += " — ".join(parts) + "\n"
    else:
        text += "لا توجد كميات مضافة بعد.\n"
    
    text += "\nاختر إجراءً:"
    
    kb = [[InlineKeyboardButton("➕ إضافة كمية", callback_data=f"adm_qty_add_{sid}")]]
    
    if qty_list:
        for q in qty_list:
            qid, label, psyp, pusd = q
            kb.append([InlineKeyboardButton(f"🗑 حذف {label}", callback_data=f"adm_qty_del_{qid}_{sid}")])
    
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_srv_{sid}")])
    
    await edit_or_reply(query, text, reply_markup=InlineKeyboardMarkup(kb))


async def admin_qty_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_qty_add_", ""))
    admin_states[query.from_user.id] = {"action": "add_qty_label", "service_id": sid}
    await edit_or_reply(query, "📦 أدخل اسم الكمية/الفئة:\n\nمثال: 1000 جوهرة، شهر، 500 نقطة")


async def admin_qty_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    qid = int(parts[3])
    sid = int(parts[4])
    delete_quantity(qid)
    await edit_or_reply(query, "✅ تم حذف الكمية")
    # رجوع تلقائي للقائمة
    await admin_qty_menu(update, context)


async def admin_qty_input_syp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستدعى من message_handler الرئيسي — لهذا محتاجين نضيفه في الـ main handler"""
    pass

# ═══════════════ نهاية إدارة الكميات ═══════════════

# ═══════════════ نوع البيانات (Patch 12) ═══════════════
async def admin_srv_datatype_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_srvtype_", ""))
    srv = get_service(sid)
    if not srv:
        await query.edit_message_text("❌ الخدمة غير موجودة")
        return
    srv_name = srv[1]
    current = srv[4] or "id"
    current_label = "🆔 ID اللاعب" if current == "id" else "📱 رقم هاتف"
    
    text = (
        f"📝 *نوع البيانات للخدمة:* {srv_name}\n\n"
        f"الحالي: {current_label}\n\n"
        f"اختر النوع الجديد:"
    )
    keyboard = [
        [InlineKeyboardButton("🆔 ID اللاعب", callback_data=f"adm_settype_id_{sid}")],
        [InlineKeyboardButton("📱 رقم هاتف", callback_data=f"adm_settype_phone_{sid}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_srv_{sid}")]
    ]
    await edit_or_reply(query, text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_set_datatype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("adm_settype_", "").split("_")
    dtype = parts[0]
    sid = int(parts[1])
    update_service(sid, data_type=dtype)
    
    label = "🆔 ID اللاعب" if dtype == "id" else "📱 رقم هاتف"
    await query.edit_message_text(
        f"✅ تم تحديث نوع البيانات إلى: *{label}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع للخدمة", callback_data=f"adm_srv_{sid}")
        ]])
    )

# ═══════════════ نهاية نوع البيانات ═══════════════


async def admin_srv_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("adm_srvprice_", ""))
    srv = get_service(sid)
    if not srv:
        await edit_or_reply(query, "❌ الخدمة غير موجودة")
        return
    ptype = "fixed"
    admin_states[query.from_user.id] = {"action": "edit_srv_price", "srv_id": sid, "ptype": ptype}
    if ptype == "fixed":
        msg = "💰 تعديل السعر\n\nأرسل:\n• 20 ل.س (بالليرة)\n• أو $1.5 (بالدولار)\n• أو: 20 ل.س | $1.5"
    elif ptype == "rate":
        admin_states[query.from_user.id]["action"] = "edit_rate_menu"
        keyboard = [
            [InlineKeyboardButton("💰 السعر الوحدوي + الربح", callback_data=f"adm_rate_step1_{sid}")],
            [InlineKeyboardButton("📊 الحدود (الكمية)", callback_data=f"adm_limits_step1_{sid}")],
            [InlineKeyboardButton("🔀 طريقة الإدخال", callback_data=f"adm_input_{sid}")],
            [InlineKeyboardButton("◀️ رجوع", callback_data=f"adm_srv_{sid}")]
        ]
        await edit_or_reply(query, 
            "🧮 إعدادات الحاسبة\n\nاختر ما تريد:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif ptype == "commission":
        msg = "💵 نسبة العمولة\n\nأرسل رقم فقط:\nمثال: 5"
    else:
        msg = "أرسل السعر:"
    await edit_or_reply(query, msg)


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return False
    state = admin_states.get(user.id)
    if not state:
        return False
    action = state.get("action")
    text = update.message.text.strip()

    if action == "add_cat":
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else "📁"
        else:
            name, emoji = text, "📁"
        cid = add_category(name, emoji)
        admin_states.pop(user.id, None)
        if cid:
            await update.message.reply_text(f"✅ تمت إضافة الفئة: {emoji} {name}")
        else:
            await update.message.reply_text("❌ الفئة موجودة مسبقاً")
        return True

    elif action == "edit_cat":
        cid = state["cat_id"]
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else None
        else:
            name, emoji = text, None
        update_category(cid, name=name, emoji=emoji)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تم التعديل: {name}")
        return True

    elif action == "add_sub":
        cat_id = state["cat_id"]
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else "📂"
        else:
            name, emoji = text, "📂"
        add_subcategory(cat_id, name, emoji)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تمت إضافة الفرع: {emoji} {name}")
        return True

    elif action == "edit_sub":
        sid = state["sub_id"]
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else None
        else:
            name, emoji = text, None
        update_subcategory(sid, name=name, emoji=emoji)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تم التعديل: {name}")
        return True

    elif action == "edit_sub_phone":
        sid = state["sub_id"]
        update_subcategory(sid, phone=text)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تم حفظ الهاتف: {text}")
        return True

    elif action == "add_grp":
        sub_id = state["sub_id"]
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else "📋"
        else:
            name, emoji = text, "📋"
        add_group(sub_id, name, emoji)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تمت إضافة التصنيف: {emoji} {name}")
        return True

    elif action == "edit_grp":
        gid = state["grp_id"]
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            name, emoji = parts[0], parts[1] if len(parts) > 1 else None
        else:
            name, emoji = text, None
        update_group(gid, name=name, emoji=emoji)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تم التعديل: {name}")
        return True

    elif action == "add_srv":
        gid = state["grp_id"]
        add_service(gid, text)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تمت إضافة الخدمة: {text}\n\nافتحها لضبط السعر")
        return True

    elif action == "add_direct":
        sub_id = state["sub_id"]
        add_direct_service(sub_id, text)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تمت إضافة الخدمة المباشرة: {text}\n\nافتحها لضبط السعر")
        return True

    elif action == "edit_srv_name":
        sid = state["srv_id"]
        update_service(sid, name=text)
        admin_states.pop(user.id, None)
        await update.message.reply_text(f"✅ تم التعديل: {text}")
        return True

    elif action == "edit_srv_price":
        sid = state["srv_id"]
        ptype = state.get("ptype", "fixed")
        try:
            if ptype == "fixed":
                if "|" in text:
                    parts = [p.strip() for p in text.split("|")]
                    update_service(sid, price_syp=parts[0], price_usd=parts[1] if len(parts) > 1 else "")
                elif text.startswith("$"):
                    update_service(sid, price_usd=text)
                else:
                    update_service(sid, price_syp=text)
                await update.message.reply_text(f"✅ تم حفظ السعر: {text}")
            elif ptype == "commission":
                comm = float(text)
                update_service(sid, commission_percent=comm)
                await update.message.reply_text(f"✅ تم حفظ العمولة: {comm:g}%")
        except ValueError:
            await update.message.reply_text("⚠️ صيغة غير صحيحة")
            return True
        admin_states.pop(user.id, None)
        return True

    elif action == "edit_rate_step1":
        sid = state["srv_id"]
        try:
            if "|" in text:
                parts = [p.strip() for p in text.split("|")]
                rsyp = float(parts[0]) if parts[0] else 0
                rusd = float(parts[1]) if len(parts) > 1 and parts[1] else 0
            else:
                rsyp = float(text)
                rusd = 0
            update_service(sid, rate_syp=rsyp, rate_usd=rusd)
            admin_states.pop(user.id, None)
            keyboard = [[InlineKeyboardButton("📈 إضافة نسبة الربح", callback_data=f"adm_rate_step2_{sid}")]]
            await update.message.reply_text(
                f"✅ تم حفظ السعر الوحدوي:\n"
                f"• ل.س: {rsyp:g}\n"
                f"• $: {rusd:g}\n\n"
                f"الآن أضف نسبة الربح:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("⚠️ صيغة غير صحيحة")
            return True
        return True

    elif action == "edit_rate_step2":
        sid = state["srv_id"]
        try:
            profit = float(text)
            update_service(sid, profit_percent=profit)
            admin_states.pop(user.id, None)
            keyboard = [[InlineKeyboardButton("📊 إضافة الحدود", callback_data=f"adm_limits_step1_{sid}")]]
            await update.message.reply_text(
                f"✅ تم حفظ نسبة الربح: {profit:g}%\n\n"
                f"الآن أضف الحدود:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("⚠️ أرسل رقماً")
            return True
        return True

    elif action == "edit_limits_step1":
        sid = state["srv_id"]
        try:
            if "|" in text:
                parts = [p.strip() for p in text.split("|")]
                minq = float(parts[0]) if parts[0] else 0
                maxq = float(parts[1]) if len(parts) > 1 and parts[1] else 0
            else:
                minq = float(text)
                maxq = 0
            update_service(sid, min_qty=minq, max_qty=maxq)
            admin_states.pop(user.id, None)
            keyboard = [[InlineKeyboardButton("🔀 طريقة الإدخال", callback_data=f"adm_input_{sid}")]]
            await update.message.reply_text(
                f"✅ تم حفظ الحدود:\n"
                f"• الأدنى: {minq:g}\n"
                f"• الأعلى: {maxq:g}\n\n"
                f"الآن اختر طريقة الإدخال:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("⚠️ صيغة غير صحيحة")
            return True
        return True


    # ═══════════════ حالات إضافة الكميات (Patch 10) ═══════════════
    elif action == "add_qty_label":
        sid = state["service_id"]
        admin_states[user.id] = {"action": "add_qty_syp", "service_id": sid, "qty_label": text}
        await update.message.reply_text(f"📦 الكمية: {text}\n\n💰 أدخل السعر بالليرة السورية (مثال: 20):")
        return True

    elif action == "add_qty_syp":
        sid = state["service_id"]
        label = state["qty_label"]
        admin_states[user.id] = {"action": "add_qty_usd", "service_id": sid, "qty_label": label, "qty_syp": text}
        await update.message.reply_text(f"💰 السعر بالليرة: {text}\n\n💵 أدخل السعر بالدولار (مثال: 1.5):")
        return True

    elif action == "add_qty_usd":
        sid = state["service_id"]
        label = state["qty_label"]
        syp = state["qty_syp"]
        usd = text
        add_quantity(sid, label, syp, usd)
        admin_states.pop(user.id, None)
        keyboard = [[InlineKeyboardButton("📊 رجوع لإدارة الكميات", callback_data=f"adm_qty_menu_{sid}")]]
        await update.message.reply_text(
            f"✅ تمت إضافة الكمية:\n"
            f"• الاسم: {label}\n"
            f"• ل.س: {syp}\n"
            f"• $: {usd}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True
    # ═══════════════ نهاية حالات الكميات ═══════════════

    return False



async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID and user.id in admin_states:
        handled = await admin_text_handler(update, context)
        if handled:
            return
    data = pending_orders.get(user.id)
    if data:
        ptype = data.get("pricing_type")
        if ptype in ("rate", "commission") and "qty_input" not in data:
            await receive_qty(update, context)
            return
        if "account_id" not in data:
            await receive_account_id(update, context)
            return
        if data.get("awaiting") == "txn":
            await receive_txn(update, context)
            return


async def photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # صورة الفرع (للأدمن)
    state = admin_states.get(user.id)
    if state and state.get("action") == "sub_photo":
        photo = update.message.photo[-1]
        sub_id = state["sub_id"]
        update_subcategory(sub_id, image_id=photo.file_id)
        admin_states.pop(user.id, None)
        await update.message.reply_text(
            "✅ تم حفظ صورة الفرع بنجاح!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع للفرع", callback_data=f"adm_sub_{sub_id}")
            ]])
        )
        return
    
    # صورة الفئة (للأدمن)
    state = admin_states.get(user.id)
    if state and state.get("action") == "cat_photo":
        photo = update.message.photo[-1]
        cat_id = state["cat_id"]
        update_category(cat_id, image_id=photo.file_id)
        admin_states.pop(user.id, None)
        await update.message.reply_text(
            "✅ تم حفظ صورة الفئة بنجاح!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع للفئة", callback_data=f"adm_cat_{cat_id}")
            ]])
        )
        return
    
    # صورة الإيصال (للعميل)
    data = pending_orders.get(user.id)
    if data and data.get("awaiting") == "photo":
        await receive_photo(update, context)
        return


def main():
    init_db()
    logger.info("Bot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("services", show_services))
    app.add_handler(CommandHandler("stats", admin_stats))

    app.add_handler(MessageHandler(filters.Regex("^🛒 الخدمات$"), show_services))
    app.add_handler(MessageHandler(filters.Regex("^📋 طلباتي$"), my_orders))
    app.add_handler(MessageHandler(filters.Regex("^💰 معلومات الدفع$"), payment_info))
    app.add_handler(MessageHandler(filters.Regex("^📞 الدعم$"), support))
    app.add_handler(MessageHandler(filters.Regex("^🔙 رجوع$"), back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^📊 إحصائيات$"), admin_stats))
    app.add_handler(MessageHandler(filters.Regex("^📁 الفئات$"), admin_categories))
    app.add_handler(MessageHandler(filters.Regex("^📦 الطلبات$"), admin_orders))

    app.add_handler(MessageHandler(filters.PHOTO, photo_router))
    app.add_handler(CallbackQueryHandler(check_channel_callback, pattern="^check_channel$"))

    app.add_handler(CallbackQueryHandler(payment_choice_handler, pattern="^pay_(syriatel|sham_syp|sham_usd)$"))
    app.add_handler(CallbackQueryHandler(confirm_pay, pattern="^confirm_pay$"))
    app.add_handler(CallbackQueryHandler(cancel_order, pattern="^cancel_order$"))
    app.add_handler(CallbackQueryHandler(qty_choice_handler, pattern="^qtypick_"))
    app.add_handler(CallbackQueryHandler(service_handler, pattern="^srv_"))
    app.add_handler(CallbackQueryHandler(group_handler, pattern="^grp_"))
    app.add_handler(CallbackQueryHandler(subcategory_handler, pattern="^sub_"))
    app.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(back_cats, pattern="^back_cats$"))

    app.add_handler(CallbackQueryHandler(order_action, pattern="^(approve|reject|shipped)_"))

    app.add_handler(CallbackQueryHandler(admin_back_cats, pattern="^adm_back_cats$"))
    app.add_handler(CallbackQueryHandler(admin_add_cat_start, pattern="^adm_add_cat$"))
    app.add_handler(CallbackQueryHandler(admin_edit_cat_start, pattern="^adm_editcat_"))
    app.add_handler(CallbackQueryHandler(admin_del_cat, pattern="^adm_delcat_"))
    app.add_handler(CallbackQueryHandler(admin_subs_list, pattern="^adm_subs_"))
    app.add_handler(CallbackQueryHandler(admin_cat_photo_start, pattern="^adm_catphoto_"))
    app.add_handler(CallbackQueryHandler(admin_category_detail, pattern="^adm_cat_"))

    app.add_handler(CallbackQueryHandler(admin_subphone_start, pattern="^adm_subphone_"))
    app.add_handler(CallbackQueryHandler(admin_edit_sub_start, pattern="^adm_editsub_"))
    app.add_handler(CallbackQueryHandler(admin_del_sub, pattern="^adm_delsub_"))
    app.add_handler(CallbackQueryHandler(admin_add_sub_start, pattern="^adm_addsub_"))
    app.add_handler(CallbackQueryHandler(admin_sub_photo_start, pattern="^adm_subphoto_"))
    app.add_handler(CallbackQueryHandler(admin_sub_detail, pattern="^adm_sub_"))

    app.add_handler(CallbackQueryHandler(admin_direct_list, pattern="^adm_direct_"))
    app.add_handler(CallbackQueryHandler(admin_add_direct_start, pattern="^adm_adddirect_"))
    app.add_handler(CallbackQueryHandler(admin_edit_grp_start, pattern="^adm_editgrp_"))
    app.add_handler(CallbackQueryHandler(admin_del_grp, pattern="^adm_delgrp_"))
    app.add_handler(CallbackQueryHandler(admin_add_grp_start, pattern="^adm_addgrp_"))
    app.add_handler(CallbackQueryHandler(admin_grp_detail, pattern="^adm_grp_"))
    app.add_handler(CallbackQueryHandler(admin_grps_list, pattern="^adm_grps_"))

    app.add_handler(CallbackQueryHandler(admin_srv_price_start, pattern="^adm_srvprice_"))
    app.add_handler(CallbackQueryHandler(admin_edit_srv_start, pattern="^adm_editsrv_"))
    app.add_handler(CallbackQueryHandler(admin_del_srv, pattern="^adm_delsrv_"))
    app.add_handler(CallbackQueryHandler(admin_add_srv_start, pattern="^adm_addsrv_"))
    app.add_handler(CallbackQueryHandler(admin_set_datatype, pattern="^adm_settype_"))
    app.add_handler(CallbackQueryHandler(admin_srv_datatype_menu, pattern="^adm_srvtype_"))
    app.add_handler(CallbackQueryHandler(admin_srv_detail, pattern="^adm_srv_"))
    app.add_handler(CallbackQueryHandler(admin_srvs_list, pattern="^adm_srvs_"))
    # ═══ handlers الكميات (Patch 10) ═══
    app.add_handler(CallbackQueryHandler(admin_qty_menu, pattern="^adm_qty_menu_"))
    app.add_handler(CallbackQueryHandler(admin_qty_add_start, pattern="^adm_qty_add_"))
    app.add_handler(CallbackQueryHandler(admin_qty_del, pattern="^adm_qty_del_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
