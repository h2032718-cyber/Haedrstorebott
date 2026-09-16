# -*- coding: utf-8 -*-
import logging
import traceback
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception:", exc_info=context.error)
    try:
        from config import ADMIN_ID
        error_message = (
            f"⚠️ خطأ في البوت\n\n"
            f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"❌ الخطأ:\n"
            f"`{str(context.error)[:300]}`"
        )
        if update and hasattr(update, 'effective_user') and update.effective_user:
            user = update.effective_user
            error_message += f"\n\n👤 المستخدم: {user.full_name}\n🆔 ID: `{user.id}`"
        await context.bot.send_message(chat_id=ADMIN_ID, text=error_message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
