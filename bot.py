import os
import io
import json
import asyncio
import logging
import subprocess
import tempfile
import numpy as np
from datetime import date
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputSticker
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("STICKER_BOT_TOKEN")
ADMIN_ID = 8590370942
DATA_FILE = "artifacts/sticker-bot/data/users.json"
BOT_USERNAME = ""

FFMPEG = "/nix/store/s41bqqrym7dlk8m3nk74fx26kgrx0kv8-replit-runtime-path/bin/ffmpeg"
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

# ─── Tarjimalar ───────────────────────────────────────────────────────────────

T = {
    "uz": {
        "welcome": "Salom, {name}! 👋\n\nAsosiy menyudan tanlang:",
        "main_menu": "Asosiy menyu 👇",
        "choose_action": "✅ Rasm qabul qilindi! Nima qilish kerak?",
        "choose_filter": "🎨 Filtr tanlang:",
        "send_photo": "📸 Rasm yuboring:",
        "send_gif": "🎬 GIF yoki video yuboring (max 10 soniya):",
        "send_text": "✏️ Sticker uchun matn yozing:",
        "choose_color": "🎨 Fon rangini tanlang:",
        "processing": "⏳ Jarayonda...",
        "error": "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
        "no_photo": "❌ Avval rasm yuboring.",
        "ref_text": "👥 *Referral tizimi*\n\nSizning havolangiz:\n`{link}`\n\nTaklif qilganlar: *{count}* ta\n\nHavola orqali do'stlaringizni taklif qiling!",
        "lang_changed": "✅ Til o'zgartirildi!",
        "help_text": "ℹ️ *Qo'llanma*\n\n🖼 *Sticker* — 512x512 WebP formatga o'zgartiradi\n🎨 *Filtrlar* — 6 xil effekt: Qora-oq, Vintaj, Keskin, Yorqin, Sovuq, Iliq\n🎬 *GIF Sticker* — GIF/video dan animatsiyali sticker\n✏️ *Matn → Sticker* — matndan chiroyli sticker\n📦 *Sticker pak* — o'zingizning sticker pakingiz\n👥 *Referral* — do'stlarni taklif qiling\n🪄 *Fon o'chirish* — orqa fonni AI bilan olib tashlaydi\n🎭 *Cartoon* — rasmni anime uslubiga o'zgartiradi",
        "pack_menu": "📦 Sticker pak menyusi:",
        "pack_no_pack": "❌ Sizda hali pak yo'q. Yangi pak yarating!",
        "pack_new_title": "📦 Pakingizga nom bering\n(masalan: Mening stickerlarim):",
        "pack_title_saved": "✅ Nom saqlandi: *{title}*\n\nEndi rasm yuboring — birinchi sticker pakni yaratadi!",
        "pack_added": "✅ Sticker pakka qo'shildi!\n\n🔗 {link}",
        "pack_error": "❌ Pakka qo'shishda xatolik. Qayta urinib ko'ring.",
        "pack_link": "🔗 Sizning pakingiz:\n{link}",
        "sticker_done": "✅ Sticker tayyor!",
        "rembg_done": "✅ Fon o'chirildi!",
        "cartoon_done": "✅ Cartoon tayyor!",
        "filter_done": "✅ Filtr qo'llanildi!",
        "gif_done": "✅ GIF Sticker tayyor!",
        "text_done": "✅ Matn sticker tayyor!",
        "gif_too_long": "❌ Video juda uzun! Maksimal 10 soniya.",
        "back": "◀️ Orqaga",
        "cancel": "❌ Bekor qilish",
        "new_user_notif": "🆕 Yangi foydalanuvchi: {name}\nID: {uid}\nRef orqali: {ref}",
    },
    "ru": {
        "welcome": "Привет, {name}! 👋\n\nВыберите из меню:",
        "main_menu": "Главное меню 👇",
        "choose_action": "✅ Фото принято! Что делать?",
        "choose_filter": "🎨 Выберите фильтр:",
        "send_photo": "📸 Отправьте фото:",
        "send_gif": "🎬 Отправьте GIF или видео (макс. 10 сек.):",
        "send_text": "✏️ Напишите текст для стикера:",
        "choose_color": "🎨 Выберите цвет фона:",
        "processing": "⏳ Обработка...",
        "error": "❌ Ошибка. Попробуйте ещё раз.",
        "no_photo": "❌ Сначала отправьте фото.",
        "ref_text": "👥 *Реферальная система*\n\nВаша ссылка:\n`{link}`\n\nПриглашено: *{count}* чел.\n\nПриглашайте друзей!",
        "lang_changed": "✅ Язык изменён!",
        "help_text": "ℹ️ *Помощь*\n\n🖼 *Стикер* — конвертирует в 512x512 WebP\n🎨 *Фильтры* — 6 эффектов\n🎬 *GIF Стикер* — анимированный стикер\n✏️ *Текст → Стикер* — текстовый стикер\n📦 *Пакет* — ваш пакет стикеров\n👥 *Реферал* — пригласи друзей\n🪄 *Удалить фон* — AI удаляет фон\n🎭 *Мультяшка* — аниме стиль",
        "pack_menu": "📦 Меню пакета стикеров:",
        "pack_no_pack": "❌ Нет пакета. Создайте новый!",
        "pack_new_title": "📦 Введите название пакета:",
        "pack_title_saved": "✅ Название сохранено: *{title}*\n\nОтправьте фото!",
        "pack_added": "✅ Стикер добавлен!\n\n🔗 {link}",
        "pack_error": "❌ Ошибка добавления.",
        "pack_link": "🔗 Ваш пакет:\n{link}",
        "sticker_done": "✅ Стикер готов!",
        "rembg_done": "✅ Фон удалён!",
        "cartoon_done": "✅ Мультяшка готова!",
        "filter_done": "✅ Фильтр применён!",
        "gif_done": "✅ GIF Стикер готов!",
        "text_done": "✅ Текстовый стикер готов!",
        "gif_too_long": "❌ Видео слишком длинное! Макс. 10 сек.",
        "back": "◀️ Назад",
        "cancel": "❌ Отмена",
        "new_user_notif": "🆕 Новый пользователь: {name}\nID: {uid}\nРеф: {ref}",
    },
    "en": {
        "welcome": "Hello, {name}! 👋\n\nChoose from the menu:",
        "main_menu": "Main menu 👇",
        "choose_action": "✅ Photo received! What to do?",
        "choose_filter": "🎨 Choose a filter:",
        "send_photo": "📸 Send a photo:",
        "send_gif": "🎬 Send a GIF or video (max 10 sec):",
        "send_text": "✏️ Write text for your sticker:",
        "choose_color": "🎨 Choose background color:",
        "processing": "⏳ Processing...",
        "error": "❌ Error. Please try again.",
        "no_photo": "❌ Send a photo first.",
        "ref_text": "👥 *Referral System*\n\nYour link:\n`{link}`\n\nInvited: *{count}* people\n\nInvite your friends!",
        "lang_changed": "✅ Language changed!",
        "help_text": "ℹ️ *Help*\n\n🖼 *Sticker* — converts to 512x512 WebP\n🎨 *Filters* — 6 effects\n🎬 *GIF Sticker* — animated sticker\n✏️ *Text → Sticker* — text sticker\n📦 *Pack* — your sticker pack\n👥 *Referral* — invite friends\n🪄 *Remove BG* — AI background removal\n🎭 *Cartoon* — anime style",
        "pack_menu": "📦 Sticker pack menu:",
        "pack_no_pack": "❌ No pack found. Create one!",
        "pack_new_title": "📦 Enter pack name:",
        "pack_title_saved": "✅ Name saved: *{title}*\n\nSend a photo!",
        "pack_added": "✅ Sticker added!\n\n🔗 {link}",
        "pack_error": "❌ Error adding sticker.",
        "pack_link": "🔗 Your pack:\n{link}",
        "sticker_done": "✅ Sticker ready!",
        "rembg_done": "✅ Background removed!",
        "cartoon_done": "✅ Cartoon ready!",
        "filter_done": "✅ Filter applied!",
        "gif_done": "✅ GIF Sticker ready!",
        "text_done": "✅ Text sticker ready!",
        "gif_too_long": "❌ Video too long! Max 10 sec.",
        "back": "◀️ Back",
        "cancel": "❌ Cancel",
        "new_user_notif": "🆕 New user: {name}\nID: {uid}\nRef: {ref}",
    },
}

def tr(lang: str, key: str, **kwargs) -> str:
    text = T.get(lang, T["uz"]).get(key, T["uz"].get(key, key))
    return text.format(**kwargs) if kwargs else text

# ─── Foydalanuvchi ma'lumotlari ───────────────────────────────────────────────

def load_users() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def register_user(user, referred_by: int = None) -> bool:
    """True = yangi foydalanuvchi"""
    users = load_users()
    uid = str(user.id)
    today = str(date.today())
    is_new = uid not in users
    if is_new:
        users[uid] = {
            "id": user.id, "name": user.full_name or "",
            "username": user.username or "", "lang": "uz",
            "joined": today, "last_seen": today,
            "ref_count": 0, "referred_by": referred_by,
        }
        if referred_by:
            ref_uid = str(referred_by)
            if ref_uid in users:
                users[ref_uid]["ref_count"] = users[ref_uid].get("ref_count", 0) + 1
    else:
        users[uid]["last_seen"] = today
        users[uid]["name"] = user.full_name or ""
    save_users(users)
    return is_new

def get_lang(user_id: int) -> str:
    users = load_users()
    return users.get(str(user_id), {}).get("lang", "uz")

def set_lang(user_id: int, lang: str):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["lang"] = lang
        save_users(users)

def get_ref_count(user_id: int) -> int:
    users = load_users()
    return users.get(str(user_id), {}).get("ref_count", 0)

def get_stats() -> dict:
    users = load_users()
    today = str(date.today())
    return {
        "total": len(users),
        "today_active": sum(1 for u in users.values() if u.get("last_seen") == today),
        "today_new": sum(1 for u in users.values() if u.get("joined") == today),
    }

# ─── Klaviaturalar ────────────────────────────────────────────────────────────

def main_kb(lang: str, is_admin=False) -> InlineKeyboardMarkup:
    b = tr(lang, "back")
    rows = [
        [InlineKeyboardButton("🖼 Sticker", callback_data="menu_sticker"),
         InlineKeyboardButton("🎨 Filtrlar", callback_data="menu_filters")],
        [InlineKeyboardButton("🎬 GIF Sticker", callback_data="menu_gif"),
         InlineKeyboardButton("✏️ Matn → Sticker", callback_data="menu_text")],
        [InlineKeyboardButton("🪄 Fon o'chirish", callback_data="menu_rembg"),
         InlineKeyboardButton("🎭 Cartoon", callback_data="menu_cartoon")],
        [InlineKeyboardButton("📦 Sticker pak", callback_data="menu_pack"),
         InlineKeyboardButton("👥 Referral", callback_data="menu_ref")],
        [InlineKeyboardButton("🌐 Til / Lang", callback_data="menu_lang"),
         InlineKeyboardButton("ℹ️ Yordam", callback_data="menu_help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def photo_action_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 Sticker qil", callback_data="do_sticker"),
         InlineKeyboardButton("🪄 Fonni o'chir", callback_data="do_rembg")],
        [InlineKeyboardButton("🎭 Cartoon", callback_data="do_cartoon"),
         InlineKeyboardButton("🎨 Filtr qo'y", callback_data="do_filter_menu")],
        [InlineKeyboardButton("📦 Pakka qo'sh", callback_data="do_addtopack")],
        [InlineKeyboardButton(tr(lang, "cancel"), callback_data="back_main")],
    ])

def filter_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬛ Qora-oq", callback_data="filter_bw"),
         InlineKeyboardButton("🟤 Vintaj", callback_data="filter_vintage")],
        [InlineKeyboardButton("✨ Keskin", callback_data="filter_sharpen"),
         InlineKeyboardButton("☀️ Yorqin", callback_data="filter_bright")],
        [InlineKeyboardButton("💙 Sovuq", callback_data="filter_cool"),
         InlineKeyboardButton("❤️ Iliq", callback_data="filter_warm")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")],
    ])

def text_color_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬜ Oq fon", callback_data="txtcolor_white"),
         InlineKeyboardButton("⬛ Qora fon", callback_data="txtcolor_black")],
        [InlineKeyboardButton("🟦 Ko'k", callback_data="txtcolor_blue"),
         InlineKeyboardButton("🟩 Yashil", callback_data="txtcolor_green")],
        [InlineKeyboardButton("🟥 Qizil", callback_data="txtcolor_red"),
         InlineKeyboardButton("🟨 Sariq", callback_data="txtcolor_yellow")],
        [InlineKeyboardButton("🌈 Gradient", callback_data="txtcolor_gradient")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")],
    ])

def pack_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi pak", callback_data="pack_new")],
        [InlineKeyboardButton("🔗 Mening pakim", callback_data="pack_mylink")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")],
    ])

def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="setlang_uz"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")],
    ])

def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "cancel"), callback_data="back_main")]])

# ─── Rasm qayta ishlash ───────────────────────────────────────────────────────

def prepare_sticker_png(img_bytes: bytes, watermark=True) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img.thumbnail((512, 512), Image.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    canvas.paste(img, (x, y), img)
    if watermark:
        draw = ImageDraw.Draw(canvas)
        text = "@uzstickerbot"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        m = 8
        draw.text((512-tw-m+1, 512-th-m+1), text, font=font, fill=(0,0,0,140))
        draw.text((512-tw-m, 512-th-m), text, font=font, fill=(255,255,255,200))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()

def make_sticker_webp(img_bytes: bytes) -> bytes:
    png = prepare_sticker_png(img_bytes, watermark=True)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()

def remove_background(img_bytes: bytes) -> bytes:
    from rembg import remove
    result = remove(img_bytes)
    img = Image.open(io.BytesIO(result)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def make_cartoon(img_bytes: bytes) -> bytes:
    import cv2
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    color = img.copy()
    for _ in range(4):
        color = cv2.bilateralFilter(color, d=9, sigmaColor=75, sigmaSpace=75)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.medianBlur(gray, 7)
    edges = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 2)
    edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    cartoon = cv2.bitwise_and(color, edges_colored)
    _, buf = cv2.imencode(".png", cartoon)
    return buf.tobytes()

def apply_filter(img_bytes: bytes, filter_type: str) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    if filter_type == "bw":
        gray = np.dot(arr, [0.299, 0.587, 0.114])
        arr = np.stack([gray, gray, gray], axis=-1)

    elif filter_type == "vintage":
        gray = np.dot(arr, [0.299, 0.587, 0.114])
        arr = np.zeros((*arr.shape[:2], 3), dtype=np.float32)
        arr[:, :, 0] = np.clip(gray * 1.07, 0, 255)
        arr[:, :, 1] = np.clip(gray * 0.74, 0, 255)
        arr[:, :, 2] = np.clip(gray * 0.43, 0, 255)

    elif filter_type == "sharpen":
        img = img.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
        arr = np.array(img, dtype=np.float32)

    elif filter_type == "bright":
        arr = np.clip(arr * 1.4, 0, 255)

    elif filter_type == "cool":
        arr[:, :, 0] = np.clip(arr[:, :, 0] - 10, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] + 30, 0, 255)

    elif filter_type == "warm":
        arr[:, :, 0] = np.clip(arr[:, :, 0] + 30, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] - 10, 0, 255)

    result = Image.fromarray(arr.astype(np.uint8))
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    return buf.getvalue()

def convert_gif_to_sticker(input_bytes: bytes, ext: str = "gif") -> bytes | None:
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, f"input.{ext}")
        out = os.path.join(tmp, "output.webm")
        with open(inp, "wb") as f:
            f.write(input_bytes)
        cmd = [
            FFMPEG, "-y", "-i", inp,
            "-c:v", "libvpx-vp9",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0,fps=30",
            "-t", "3", "-an", "-b:v", "500k",
            out
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0 or not os.path.exists(out):
            return None
        with open(out, "rb") as f:
            return f.read()

def make_text_sticker(text: str, theme: str = "white") -> bytes:
    THEMES = {
        "white":    ((255,255,255), (30,30,30)),
        "black":    ((20,20,20),    (255,255,255)),
        "blue":     ((37,99,235),   (255,255,255)),
        "green":    ((22,163,74),   (255,255,255)),
        "red":      ((220,38,38),   (255,255,255)),
        "yellow":   ((234,179,8),   (30,30,30)),
        "gradient": (None,          (255,255,255)),
    }
    bg_color, text_color = THEMES.get(theme, THEMES["white"])
    size = 512

    if theme == "gradient":
        c1 = np.array([138, 43, 226, 255])
        c2 = np.array([37, 99, 235, 255])
        arr = np.zeros((size, size, 4), dtype=np.uint8)
        for y in range(size):
            t = y / size
            arr[y, :] = (c1 * (1 - t) + c2 * t).astype(np.uint8)
        canvas = Image.fromarray(arr, "RGBA")
    else:
        canvas = Image.new("RGBA", (size, size), (*bg_color, 255))

    draw = ImageDraw.Draw(canvas)
    font_size = 72
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Matnni qatorlarga bo'lish
    def wrap(txt, fnt, max_w):
        words = txt.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textbbox((0, 0), test, font=fnt)[2] > max_w:
                if cur:
                    lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    lines = wrap(text, font, size - 60)
    # Ko'p qator bo'lsa font kichraytir
    while len(lines) > 6 and font_size > 28:
        font_size -= 8
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            break
        lines = wrap(text, font, size - 60)

    line_h = font_size + 12
    total_h = len(lines) * line_h
    y = (size - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (size - lw) // 2
        draw.text((x+2, y+2), line, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font, fill=(*text_color, 255))
        y += line_h

    buf = io.BytesIO()
    canvas.save(buf, format="WEBP")
    return buf.getvalue()

# ─── Sticker pak ─────────────────────────────────────────────────────────────

def pack_name(user_id: int) -> str:
    return f"uz{user_id}_by_{BOT_USERNAME}"

async def ensure_pack(bot, user_id: int, title: str, first_png: bytes) -> bool:
    name = pack_name(user_id)
    try:
        await bot.get_sticker_set(name)
        return True
    except:
        pass
    try:
        await bot.create_new_sticker_set(
            user_id=user_id, name=name, title=title,
            stickers=[InputSticker(sticker=first_png, emoji_list=["🙂"], format="static")],
        )
        return True
    except Exception as e:
        logger.error(f"Pak yaratishda xato: {e}")
        return False

async def add_to_pack(bot, user_id: int, png: bytes) -> bool:
    try:
        await bot.add_sticker_to_set(
            user_id=user_id, name=pack_name(user_id),
            sticker=InputSticker(sticker=png, emoji_list=["🙂"], format="static"),
        )
        return True
    except Exception as e:
        logger.error(f"Sticker qo'shishda xato: {e}")
        return False

# ─── Handlerlar ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    ref_id = None
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0][4:])
        except:
            pass

    is_new = register_user(user, referred_by=ref_id)
    lang = get_lang(user.id)

    if is_new and ref_id and ref_id != user.id:
        try:
            await context.bot.send_message(
                ref_id,
                f"🎉 Sizning havolangiz orqali yangi foydalanuvchi keldi!\n"
                f"Jami taklif qilganlar: *{get_ref_count(ref_id)}* ta",
                parse_mode="Markdown"
            )
        except:
            pass
        try:
            await context.bot.send_message(
                ADMIN_ID,
                tr(lang, "new_user_notif", name=user.full_name, uid=user.id, ref=ref_id),
            )
        except:
            pass

    await update.message.reply_text(
        tr(lang, "welcome", name=user.first_name),
        reply_markup=main_kb(lang, user.id == ADMIN_ID),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = get_lang(user.id)
    data = query.data

    # ── Orqaga / asosiy menyu ──
    if data == "back_main":
        context.user_data.pop("mode", None)
        context.user_data.pop("pending_text", None)
        await query.edit_message_text(
            tr(lang, "main_menu"),
            reply_markup=main_kb(lang, user.id == ADMIN_ID),
        )

    # ── Asosiy tugmalar ──
    elif data == "menu_sticker":
        await query.edit_message_text(
            "🖼 " + tr(lang, "send_photo"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_rembg":
        await query.edit_message_text(
            "🪄 " + tr(lang, "send_photo"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_cartoon":
        await query.edit_message_text(
            "🎭 " + tr(lang, "send_photo"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_filters":
        context.user_data["mode"] = "filter_first_photo"
        await query.edit_message_text(
            "🎨 " + tr(lang, "send_photo"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_gif":
        context.user_data["mode"] = "waiting_gif"
        await query.edit_message_text(
            tr(lang, "send_gif"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_text":
        context.user_data["mode"] = "waiting_text_sticker"
        await query.edit_message_text(
            tr(lang, "send_text"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "menu_pack":
        await query.edit_message_text(
            tr(lang, "pack_menu"),
            reply_markup=pack_kb(lang),
        )

    elif data == "menu_ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        count = get_ref_count(user.id)
        await query.edit_message_text(
            tr(lang, "ref_text", link=link, count=count),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Havolani ulashish", url=f"https://t.me/share/url?url={link}")],
                [InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")],
            ]),
        )

    elif data == "menu_lang":
        await query.edit_message_text(
            "🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=lang_kb(),
        )

    elif data == "menu_help":
        await query.edit_message_text(
            tr(lang, "help_text"),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")]]),
        )

    # ── Til tanlash ──
    elif data.startswith("setlang_"):
        new_lang = data.split("_")[1]
        set_lang(user.id, new_lang)
        lang = new_lang
        await query.edit_message_text(
            tr(lang, "lang_changed"),
            reply_markup=main_kb(lang, user.id == ADMIN_ID),
        )

    # ── Rasm amallari (foto kelgandan keyin) ──
    elif data in ("do_sticker", "do_rembg", "do_cartoon", "do_filter_menu", "do_addtopack"):
        img_bytes = context.user_data.get("photo")
        if not img_bytes:
            await query.edit_message_text(tr(lang, "no_photo"), reply_markup=cancel_kb(lang))
            return

        if data == "do_filter_menu":
            await query.edit_message_text(tr(lang, "choose_filter"), reply_markup=filter_kb(lang))
            return

        await query.edit_message_text(tr(lang, "processing"))
        loop = asyncio.get_event_loop()

        try:
            if data == "do_sticker":
                result = await loop.run_in_executor(None, make_sticker_webp, img_bytes)
                buf = io.BytesIO(result); buf.name = "sticker.webp"
                await query.message.reply_sticker(sticker=buf)
                await query.edit_message_text(tr(lang, "sticker_done"), reply_markup=main_kb(lang, user.id == ADMIN_ID))

            elif data == "do_rembg":
                result = await loop.run_in_executor(None, remove_background, img_bytes)
                buf = io.BytesIO(result); buf.name = "no_bg.png"
                await query.message.reply_document(document=buf, filename="no_background.png", caption=tr(lang, "rembg_done"))
                await query.edit_message_text("✅", reply_markup=main_kb(lang, user.id == ADMIN_ID))

            elif data == "do_cartoon":
                result = await loop.run_in_executor(None, make_cartoon, img_bytes)
                buf = io.BytesIO(result)
                await query.message.reply_photo(photo=buf, caption=tr(lang, "cartoon_done"))
                await query.edit_message_text("✅", reply_markup=main_kb(lang, user.id == ADMIN_ID))

            elif data == "do_addtopack":
                pack_title = context.user_data.get("pack_title", f"{user.first_name} Stickers")
                png = await loop.run_in_executor(None, prepare_sticker_png, img_bytes, False)
                name = pack_name(user.id)
                try:
                    await context.bot.get_sticker_set(name)
                    ok = await add_to_pack(context.bot, user.id, png)
                except:
                    ok = await ensure_pack(context.bot, user.id, pack_title, png)
                if ok:
                    link = f"https://t.me/addstickers/{name}"
                    await query.edit_message_text(
                        tr(lang, "pack_added", link=link),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📦 Pakni ochish", url=link)],
                            [InlineKeyboardButton("➕ Yana qo'sh", callback_data="do_addtopack")],
                            [InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")],
                        ]),
                    )
                else:
                    await query.edit_message_text(tr(lang, "pack_error"), reply_markup=cancel_kb(lang))

        except Exception as e:
            logger.error(f"Amal xatosi ({data}): {e}", exc_info=True)
            await query.edit_message_text(tr(lang, "error"), reply_markup=cancel_kb(lang))

    # ── Filtrlar ──
    elif data.startswith("filter_"):
        filter_type = data.split("_")[1]
        img_bytes = context.user_data.get("photo")
        if not img_bytes:
            await query.edit_message_text(tr(lang, "no_photo"), reply_markup=cancel_kb(lang))
            return
        await query.edit_message_text(tr(lang, "processing"))
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, apply_filter, img_bytes, filter_type)
            buf = io.BytesIO(result)
            await query.message.reply_photo(photo=buf, caption=tr(lang, "filter_done"))
            await query.edit_message_text("✅", reply_markup=main_kb(lang, user.id == ADMIN_ID))
        except Exception as e:
            logger.error(f"Filtr xatosi: {e}", exc_info=True)
            await query.edit_message_text(tr(lang, "error"), reply_markup=cancel_kb(lang))

    # ── Matn sticker rangi ──
    elif data.startswith("txtcolor_"):
        theme = data.split("_")[1]
        text = context.user_data.get("pending_text")
        if not text:
            await query.edit_message_text(tr(lang, "send_text"), reply_markup=cancel_kb(lang))
            return
        await query.edit_message_text(tr(lang, "processing"))
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, make_text_sticker, text, theme)
            buf = io.BytesIO(result); buf.name = "sticker.webp"
            await query.message.reply_sticker(sticker=buf)
            await query.edit_message_text(tr(lang, "text_done"), reply_markup=main_kb(lang, user.id == ADMIN_ID))
            context.user_data.pop("pending_text", None)
            context.user_data.pop("mode", None)
        except Exception as e:
            logger.error(f"Matn sticker xatosi: {e}", exc_info=True)
            await query.edit_message_text(tr(lang, "error"), reply_markup=cancel_kb(lang))

    # ── Sticker pak ──
    elif data == "pack_new":
        context.user_data["mode"] = "waiting_pack_title"
        await query.edit_message_text(
            tr(lang, "pack_new_title"),
            reply_markup=cancel_kb(lang),
        )

    elif data == "pack_mylink":
        name = pack_name(user.id)
        try:
            await context.bot.get_sticker_set(name)
            link = f"https://t.me/addstickers/{name}"
            await query.edit_message_text(
                tr(lang, "pack_link", link=link),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Pakni ochish", url=link)],
                    [InlineKeyboardButton(tr(lang, "back"), callback_data="menu_pack")],
                ]),
            )
        except:
            await query.edit_message_text(tr(lang, "pack_no_pack"), reply_markup=pack_kb(lang))

    # ── Admin panel ──
    elif data == "admin_panel":
        if user.id != ADMIN_ID:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        await query.edit_message_text("👑 *Admin panel*", parse_mode="Markdown", reply_markup=admin_kb())

    elif data == "admin_stats":
        if user.id != ADMIN_ID:
            return
        s = get_stats()
        await query.edit_message_text(
            f"📊 *Statistika*\n\n👥 Jami: *{s['total']}*\n🟢 Bugun faol: *{s['today_active']}*\n🆕 Bugun yangi: *{s['today_new']}*",
            parse_mode="Markdown", reply_markup=admin_kb(),
        )

    elif data == "admin_broadcast":
        if user.id != ADMIN_ID:
            return
        context.user_data["mode"] = "broadcast"
        await query.edit_message_text(
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
            reply_markup=cancel_kb("uz"),
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)
    lang = get_lang(user.id)
    mode = context.user_data.get("mode")

    if mode in ("waiting_pack_title", "waiting_text_sticker", "broadcast", "waiting_gif"):
        await update.message.reply_text("📸 " + tr(lang, "send_photo"), reply_markup=cancel_kb(lang))
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    context.user_data["photo"] = buf.getvalue()

    await update.message.reply_text(
        tr(lang, "choose_action"),
        reply_markup=photo_action_kb(lang),
    )


async def handle_video_gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)
    lang = get_lang(user.id)
    mode = context.user_data.get("mode")

    if mode != "waiting_gif":
        await update.message.reply_text(
            "🎬 " + tr(lang, "send_gif"),
            reply_markup=cancel_kb(lang),
        )
        context.user_data["mode"] = "waiting_gif"
        return

    media = update.message.video or update.message.animation or update.message.document
    if not media:
        await update.message.reply_text(tr(lang, "send_gif"), reply_markup=cancel_kb(lang))
        return

    duration = getattr(media, "duration", 0) or 0
    if duration > 10:
        await update.message.reply_text(tr(lang, "gif_too_long"), reply_markup=cancel_kb(lang))
        return

    status = await update.message.reply_text(tr(lang, "processing"))
    try:
        file = await context.bot.get_file(media.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        data = buf.getvalue()

        mime = getattr(media, "mime_type", "") or ""
        ext = "gif" if "gif" in mime else "mp4"

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, convert_gif_to_sticker, data, ext)

        if not result:
            await status.edit_text(tr(lang, "error"))
            return

        sticker_buf = io.BytesIO(result)
        sticker_buf.name = "sticker.webm"
        await update.message.reply_sticker(sticker=sticker_buf)
        await status.edit_text(tr(lang, "gif_done"), reply_markup=main_kb(lang, user.id == ADMIN_ID))
        context.user_data.pop("mode", None)

    except Exception as e:
        logger.error(f"GIF xatosi: {e}", exc_info=True)
        await status.edit_text(tr(lang, "error"))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)
    lang = get_lang(user.id)
    text = update.message.text or ""
    mode = context.user_data.get("mode")

    if mode == "waiting_pack_title":
        title = text.strip()[:64]
        context.user_data["pack_title"] = title
        context.user_data.pop("mode", None)
        await update.message.reply_text(
            tr(lang, "pack_title_saved", title=title),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="back_main")]]),
        )
        return

    if mode == "waiting_text_sticker":
        context.user_data["pending_text"] = text.strip()[:100]
        context.user_data.pop("mode", None)
        await update.message.reply_text(
            tr(lang, "choose_color"),
            reply_markup=text_color_kb(lang),
        )
        return

    if mode == "broadcast" and user.id == ADMIN_ID:
        context.user_data.pop("mode", None)
        users = load_users()
        sent = failed = 0
        status = await update.message.reply_text(f"📢 Yuborilmoqda... (0/{len(users)})")
        for i, uid_str in enumerate(users.keys()):
            try:
                await context.bot.send_message(int(uid_str), f"📢 *Xabar:*\n\n{text}", parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
            if (i+1) % 20 == 0:
                try:
                    await status.edit_text(f"📢 Yuborilmoqda... ({i+1}/{len(users)})")
                except:
                    pass
            await asyncio.sleep(0.05)
        await status.edit_text(
            f"✅ Yuborildi!\n✔️ Muvaffaqiyatli: *{sent}*\n❌ Xatolik: *{failed}*",
            parse_mode="Markdown", reply_markup=admin_kb(),
        )
        return

    await update.message.reply_text(tr(lang, "main_menu"), reply_markup=main_kb(lang, user.id == ADMIN_ID))

# ─── Health server ────────────────────────────────────────────────────────────

async def run_health_server():
    from aiohttp import web
    app = web.Application()
    async def health(r): return web.Response(text="OK")
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    port = int(os.environ.get("PORT", 5000))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info(f"Health server: port {port}")

async def post_init(application: Application) -> None:
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username
    logger.info(f"Bot: @{BOT_USERNAME}")

def main() -> None:
    if not BOT_TOKEN:
        logger.error("STICKER_BOT_TOKEN topilmadi!")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION | filters.Document.GIF, handle_video_gif))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    async def run_all():
        await asyncio.gather(run_health_server(), _run_bot(app))

    async def _run_bot(a):
        await a.initialize()
        await a.start()
        await a.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

    logger.info("Bot ishga tushdi...")
    asyncio.run(run_all())

if __name__ == "__main__":
    main()
