"""
╔══════════════════════════════════════════╗
║   🌐 All Language to Persian Bot        ║
║   Developer: @alirezan5555              ║
║   Hosting: Render.com (Free)            ║
║   Mode: Polling — no webhook needed     ║
╚══════════════════════════════════════════╝
"""

import os
import csv
import logging
import threading
from datetime import datetime
from io import BytesIO

from flask import Flask
from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

DetectorFactory.seed = 0

# ─────────────────────────────────────────────
#  ⚙️  CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DEVELOPER = "@alirezan5555"
BOT_NAME  = "🌐 All Language to Persian"
CSV_FILE  = "usage_log.csv"
PORT      = int(os.environ.get("PORT", 8080))

# ─────────────────────────────────────────────
#  📋  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  📊  CSV
# ─────────────────────────────────────────────
CSV_HEADERS = [
    "تاریخ", "ساعت",
    "شناسه_کاربر", "نام_کاربری", "نام",
    "شناسه_گروه", "نام_گروه",
    "تعداد_تگ", "زبان_شناسایی",
    "متن_اصلی", "متن_ترجمه",
]

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(CSV_HEADERS)

def get_tag_count(user_id: int, group_id: int) -> int:
    count = 0
    try:
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("شناسه_کاربر") == str(user_id) and
                        row.get("شناسه_گروه") == str(group_id)):
                    count += 1
    except FileNotFoundError:
        init_csv()
    return count

def log_usage(user_id, username, first_name,
              group_id, group_name,
              detected_lang, original_text, translated_text):
    init_csv()
    tag_count = get_tag_count(user_id, group_id) + 1
    now = datetime.now()
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            user_id,
            username or "—",
            first_name or "—",
            group_id,
            group_name or "—",
            tag_count,
            detected_lang,
            (original_text  or "")[:500],
            (translated_text or "")[:500],
        ])

# ─────────────────────────────────────────────
#  🔍  LANGUAGE DETECTION
# ─────────────────────────────────────────────
LANG_MAP = {
    "en":"انگلیسی 🇬🇧",   "fa":"فارسی 🇮🇷",      "ar":"عربی 🇸🇦",
    "fr":"فرانسوی 🇫🇷",   "de":"آلمانی 🇩🇪",      "es":"اسپانیایی 🇪🇸",
    "ru":"روسی 🇷🇺",      "zh-cn":"چینی 🇨🇳",    "ja":"ژاپنی 🇯🇵",
    "ko":"کره‌ای 🇰🇷",    "tr":"ترکی 🇹🇷",        "it":"ایتالیایی 🇮🇹",
    "pt":"پرتغالی 🇵🇹",   "hi":"هندی 🇮🇳",        "nl":"هلندی 🇳🇱",
    "pl":"لهستانی 🇵🇱",   "sv":"سوئدی 🇸🇪",       "uk":"اوکراینی 🇺🇦",
    "he":"عبری 🇮🇱",      "bn":"بنگالی 🇧🇩",      "vi":"ویتنامی 🇻🇳",
    "th":"تایلندی 🇹🇭",   "id":"اندونزیایی 🇮🇩",  "ur":"اردو 🇵🇰",
    "ro":"رومانیایی 🇷🇴", "cs":"چکی 🇨🇿",          "hu":"مجاری 🇭🇺",
}

UNICODE_RANGES = [
    (0x0600, 0x06FF, "ar_fa"),
    (0x0900, 0x097F, "hi"),
    (0x0E00, 0x0E7F, "th"),
    (0x0400, 0x04FF, "cyrillic"),
    (0x0590, 0x05FF, "he"),
    (0x0980, 0x09FF, "bn"),
    (0x3040, 0x30FF, "ja"),
    (0x4E00, 0x9FFF, "zh"),
    (0xAC00, 0xD7AF, "ko"),
]

def _unicode_hint(text: str):
    counts = {}
    for ch in text:
        cp = ord(ch)
        for lo, hi, tag in UNICODE_RANGES:
            if lo <= cp <= hi:
                counts[tag] = counts.get(tag, 0) + 1
                break
    total = max(len(text), 1)
    dominant = max(counts, key=counts.get, default=None)
    if dominant and counts[dominant] / total > 0.25:
        mapping = {"ja":"ja","zh":"zh-cn","ko":"ko",
                   "hi":"hi","th":"th","he":"he","bn":"bn"}
        return mapping.get(dominant)
    return None

def _is_persian(text: str) -> bool:
    return any(ch in "پچژگک‌" for ch in text)

def detect_language(text: str):
    text = text.strip()
    if not text or len(text) < 2:
        return "unknown", "ناشناخته"
    hint = _unicode_hint(text)
    if hint:
        return hint, LANG_MAP.get(hint, hint)
    if any(0x0600 <= ord(ch) <= 0x06FF for ch in text):
        if _is_persian(text):
            return "fa", LANG_MAP["fa"]
        return "ar", LANG_MAP["ar"]
    try:
        code = detect(text)
        return code, LANG_MAP.get(code, code.upper())
    except Exception:
        return "unknown", "ناشناخته"

# ─────────────────────────────────────────────
#  🌐  TRANSLATION
# ─────────────────────────────────────────────
def translate_text(text: str, target_lang: str = "fa"):
    try:
        result = GoogleTranslator(source="auto", target=target_lang).translate(text)
        return result, True
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return None, False

# ─────────────────────────────────────────────
#  🖼️  OCR
# ─────────────────────────────────────────────
def preprocess_image(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def extract_text_from_image(image_bytes: bytes):
    try:
        img = preprocess_image(Image.open(BytesIO(image_bytes)))
        for langs in ("eng+ara+fas", "eng+rus", "eng+chi_sim", "eng"):
            try:
                text = pytesseract.image_to_string(
                    img, lang=langs, config="--oem 3 --psm 6").strip()
                if text:
                    return text
            except Exception:
                continue
    except Exception as e:
        logger.error(f"OCR error: {e}")
    return None

# ─────────────────────────────────────────────
#  ⌨️  KEYBOARDS
# ─────────────────────────────────────────────
MAIN_KB = ReplyKeyboardMarkup([
    ["🌍 تغییر زبان مقصد",    "🖼 ارسال تصویر برای ترجمه"],
    ["➕ افزودن ربات به گروه", "ℹ️ درباره ما"],
], resize_keyboard=True)

LANG_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🇮🇷 فارسی (پیش‌فرض)", callback_data="tl_fa")],
    [InlineKeyboardButton("🇬🇧 English",  callback_data="tl_en"),
     InlineKeyboardButton("🇸🇦 عربى",      callback_data="tl_ar")],
    [InlineKeyboardButton("🇩🇪 Deutsch",  callback_data="tl_de"),
     InlineKeyboardButton("🇫🇷 Français",  callback_data="tl_fr")],
    [InlineKeyboardButton("🇷🇺 Русский",  callback_data="tl_ru"),
     InlineKeyboardButton("🇹🇷 Türkçe",   callback_data="tl_tr")],
    [InlineKeyboardButton("🇨🇳 中文",      callback_data="tl_zh-CN"),
     InlineKeyboardButton("🇯🇵 日本語",    callback_data="tl_ja")],
    [InlineKeyboardButton("🇪🇸 Español",  callback_data="tl_es"),
     InlineKeyboardButton("🇮🇳 हिन्दी",   callback_data="tl_hi")],
])

# ─────────────────────────────────────────────
#  🤖  HANDLERS
# ─────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"سلام *{user.first_name}* عزیز! 👋\n\n"
        f"به ربات _{BOT_NAME}_ خوش آمدید!\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "✨ *قابلیت‌ها:*\n"
        "• ترجمه خودکار هر زبانی به فارسی\n"
        "• تشخیص زبان با الگوریتم هوشمند ۳ مرحله‌ای\n"
        "• استخراج و ترجمه متن از تصویر (OCR)\n"
        "• کار در گروه — Reply کنید و تگ کنید!\n"
        "• پشتیبانی از ۳۰+ زبان\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "📌 *نحوه استفاده در گروه:*\n"
        "روی پیام موردنظر Reply بزنید، سپس ربات را تگ کنید.\n\n"
        "از منوی زیر شروع کنید 👇",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_csv()
    total, users, langs = 0, set(), {}
    try:
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                total += 1
                users.add(row.get("شناسه_کاربر"))
                l = row.get("زبان_شناسایی", "نامشخص")
                langs[l] = langs.get(l, 0) + 1
    except Exception:
        pass
    top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]
    top_txt = "\n".join(f"  • {l}: {c} بار" for l, c in top) or "  هنوز داده‌ای نیست"
    await update.message.reply_text(
        "📊 *آمار کلی ربات:*\n\n"
        f"🔢 مجموع ترجمه‌ها: *{total}*\n"
        f"👥 کاربران یکتا: *{len(users)}*\n\n"
        f"🌍 پرکاربردترین زبان‌ها:\n{top_txt}",
        parse_mode="Markdown",
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.startswith("tl_"):
        lang = q.data[3:]
        context.user_data["target_lang"] = lang
        display = LANG_MAP.get(lang.lower(), lang)
        await q.edit_message_text(
            f"✅ زبان مقصد به *{display}* تغییر یافت!\n"
            "حالا متن یا تصویر بفرستید.",
            parse_mode="Markdown",
        )

async def handle_text_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg    = update.message.text
    target = context.user_data.get("target_lang", "fa")

    if "🌍 تغییر زبان" in msg:
        await update.message.reply_text(
            "🌍 *زبان مقصد ترجمه را انتخاب کنید:*",
            parse_mode="Markdown", reply_markup=LANG_KB)
        return

    if "🖼 ارسال تصویر" in msg:
        context.user_data["awaiting_image"] = True
        await update.message.reply_text(
            "🖼 *ارسال تصویر:*\n\n"
            "تصویر حاوی متن را بفرستید.\n"
            "ربات متن را استخراج و ترجمه می‌کند.\n\n"
            "💡 کیفیت بالاتر = دقت OCR بیشتر",
            parse_mode="Markdown")
        return

    if "➕ افزودن" in msg:
        bot_info = await context.bot.get_me()
        await update.message.reply_text(
            "📌 *افزودن ربات به گروه:*\n\n"
            "۱. روی دکمه زیر کلیک کنید\n"
            "۲. گروه مورد نظر را انتخاب کنید\n"
            "۳. ربات را ادمین کنید (فقط ارسال پیام)\n\n"
            "⚡ بعد از اضافه شدن، Reply کنید و تگ کنید!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "➕ افزودن به گروه",
                    url=f"https://t.me/{bot_info.username}?startgroup=true")
            ]]))
        return

    if "ℹ️ درباره" in msg:
        await update.message.reply_text(
            f"🤖 *{BOT_NAME}*\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "این ربات در حال توسعه است.\n"
            "امکان ترجمه خودکار پیام‌ها از هر زبانی\n"
            "به فارسی (و سایر زبان‌ها) را فراهم می‌کند.\n\n"
            f"👨‍💻 *توسعه‌دهنده:* {DEVELOPER}\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🔧 نسخه: *1.0.0*\n\n"
            "⚡ *فناوری‌ها:*\n"
            "• python-telegram-bot\n"
            "• Google Translate\n"
            "• Tesseract OCR (چند‌زبانه)\n"
            "• LangDetect + Unicode Analysis",
            parse_mode="Markdown")
        return

    # ترجمه مستقیم
    if len(msg) < 2:
        return
    lang_code, lang_name = detect_language(msg)
    target_name = LANG_MAP.get(target, target)
    if lang_code == target:
        await update.message.reply_text(
            f"ℹ️ متن از قبل به *{target_name}* است!", parse_mode="Markdown")
        return
    proc = await update.message.reply_text("🔄 در حال ترجمه...")
    translated, ok = translate_text(msg, target)
    if not ok or not translated:
        await proc.edit_text("❌ خطا در ترجمه. لطفاً دوباره تلاش کنید.")
        return
    await proc.edit_text(
        f"🔍 *زبان:* {lang_name}  →  {target_name}\n\n"
        f"✅ *ترجمه:*\n{translated}",
        parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    chat   = update.effective_chat
    target = context.user_data.get("target_lang", "fa")
    proc   = await update.message.reply_text("⏳ در حال پردازش تصویر...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        img_bytes  = bytes(await photo_file.download_as_bytearray())
        extracted  = extract_text_from_image(img_bytes)
        if not extracted:
            await proc.edit_text(
                "❌ متنی در تصویر یافت نشد.\n"
                "لطفاً تصویر باکیفیت‌تر ارسال کنید.")
            return
        lang_code, lang_name = detect_language(extracted)
        target_name = LANG_MAP.get(target, target)
        if lang_code == target:
            await proc.edit_text(
                f"🖼 *متن استخراج شده:*\n`{extracted[:500]}`\n\n"
                f"ℹ️ از قبل به *{lang_name}* است!",
                parse_mode="Markdown")
            return
        translated, ok = translate_text(extracted, target)
        if not ok:
            await proc.edit_text("❌ خطا در ترجمه.")
            return
        await proc.edit_text(
            f"🖼 *ترجمه متن تصویر*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔍 {lang_name}  →  {target_name}\n\n"
            f"📝 *متن اصلی:*\n`{extracted[:400]}`\n\n"
            f"✅ *ترجمه:*\n{translated}",
            parse_mode="Markdown")
        if chat.type in ("group", "supergroup"):
            log_usage(user.id, user.username, user.first_name,
                      chat.id, chat.title, lang_name, extracted[:300], translated[:300])
    except Exception as e:
        logger.error(f"Photo: {e}")
        await proc.edit_text("❌ خطایی رخ داد.")

async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    if not message.reply_to_message:
        await message.reply_text(
            "📌 لطفاً روی پیامی *Reply* بزنید، سپس مرا تگ کنید.",
            parse_mode="Markdown")
        return
    replied = message.reply_to_message
    user    = message.from_user
    chat    = message.chat
    target  = context.chat_data.get("target_lang", "fa")
    proc    = await message.reply_text("🔄 در حال ترجمه...")
    try:
        original_text = None
        is_image = False
        if replied.text:
            original_text = replied.text
        elif replied.caption:
            original_text = replied.caption
        elif replied.photo:
            is_image = True
            photo_file = await replied.photo[-1].get_file()
            img_bytes  = bytes(await photo_file.download_as_bytearray())
            original_text = extract_text_from_image(img_bytes)
            if not original_text:
                await proc.edit_text("❌ متنی در تصویر یافت نشد.")
                return
        else:
            await proc.edit_text(
                "❌ این نوع پیام پشتیبانی نمی‌شود.\n"
                "متن‌ها و تصاویر حاوی نوشته ترجمه می‌شوند.")
            return
        lang_code, lang_name = detect_language(original_text)
        target_name = LANG_MAP.get(target, target)
        if lang_code == target:
            await proc.edit_text(
                f"ℹ️ پیام از قبل به *{target_name}* است! 😊",
                parse_mode="Markdown")
            log_usage(user.id, user.username, user.first_name,
                      chat.id, chat.title, lang_name,
                      original_text[:300], original_text[:300])
            return
        translated, ok = translate_text(original_text, target)
        if not ok or not translated:
            await proc.edit_text("❌ خطا در ترجمه. لطفاً دوباره تلاش کنید.")
            return
        icon = "🖼" if is_image else "💬"
        await proc.edit_text(
            f"{icon} *ترجمه {'متن تصویر' if is_image else 'پیام'}*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔍 {lang_name}  →  {target_name}\n"
            f"👤 درخواست: *{user.first_name}*\n\n"
            f"📝 *اصلی:*\n`{original_text[:400]}`\n\n"
            f"✅ *ترجمه:*\n{translated}",
            parse_mode="Markdown")
        log_usage(user.id, user.username, user.first_name,
                  chat.id, chat.title, lang_name,
                  original_text[:300], translated[:300])
    except Exception as e:
        logger.error(f"Group mention: {e}")
        await proc.edit_text("❌ خطایی رخ داد.")

async def cmd_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat   = update.effective_chat
    user   = update.effective_user
    admins = await chat.get_administrators()
    if user.id not in {a.user.id for a in admins}:
        await update.message.reply_text("❌ این دستور فقط برای ادمین‌هاست.")
        return
    await update.message.reply_text(
        "🌍 *زبان مقصد گروه را انتخاب کنید:*",
        parse_mode="Markdown", reply_markup=LANG_KB)

# ─────────────────────────────────────────────
#  🌐  FLASK  —  health-check برای Render.com
# ─────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return f"<h2>✅ {BOT_NAME} is running!</h2>", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ─────────────────────────────────────────────
#  🚀  MAIN
# ─────────────────────────────────────────────
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("setlang", cmd_setlang))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(
        MessageHandler(
            (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP)
            & filters.Entity("mention"),
            handle_group_mention,
        )
    )
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_text_private)
    )
    return app

if __name__ == "__main__":
    init_csv()
    logger.info(f"Starting {BOT_NAME}...")

    # Flask در thread جداگانه — فقط برای health-check
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Health endpoint: port {PORT}")

    # Polling — ساده‌ترین روش، نیازی به webhook ندارد
    application = build_app()
    logger.info("Bot polling started ✅")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
