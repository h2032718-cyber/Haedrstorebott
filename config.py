# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

WALLETS = {
    "سيرياتيل كاش": os.getenv("SYRIATEL_NUMBER", ""),
    "شام كاش": os.getenv("SHAM_NUMBER", ""),
}

CURRENCY = "ل.س"
BOT_NAME = "متجر حيدر ستور"

CHANNEL_USERNAME = "@haedrstore"
CHANNEL_URL = "https://t.me/haedrstore"

SUPPORT_URL = "https://t.me/Haedrstore123"
SUPPORT_USERNAME = "@Haedrstore123"
