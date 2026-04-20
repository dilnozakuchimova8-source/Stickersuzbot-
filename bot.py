import os
import io
import json
import asyncio
import logging
import re
import numpy as np
from datetime import datetime, date

from PIL import Image, ImageDraw, ImageFont
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputSticker,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("STICKER_BOT_TOKEN")
ADMIN_ID = 8590370942
DATA_FILE = "artifacts/sticker-bot/data/users.json"
BOT_USERNAME = ""  # startup da to'ldiriladi

# ─── Ma'lumotlar saqlash ──────────────────────────────────────────────────────

def load_users() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def register_user(user):
    users = load_users()
    uid = str(user.id)
    today = str(date.today())
    if uid not in users:
        users[uid] = {
            "id": user.id,
            "username": user.username or "",
            "name": user.full_name or "",
            "joined": today,
            "last_seen": today,
        }
    else:
        users[uid]["last_seen"] = today
        users[uid]["name"] = user.full_name or ""
    save_users(users)

def get_stats() -> dict:
    users = load_users()
    today = str(date.today())
    total = len(users)
    today_active = sum(1 for u in users.values() if u.get("last_seen") == today)
    today_new = sum(1 for u in users.values() if u.get("joined") == today)
    return {"total": total, "today_active": today_active, "today_new": today_new}

# ─── Klaviaturalar ────────────────────────────────────────────────────────────

def main_menu_keyboard(is_admin=False):
    rows = [
        [
            InlineKeyboardButton("🖼 Sticker yasash", callback_data="menu_sticker"),
            InlineKeyboardButton("📦 Sticker pak", callback_data="menu_pack"),
        ],
        [
            InlineKeyboardButton("🪄 Fon o'chirish", callback_data="menu_rembg"),
            InlineKeyboardButton("🎨 Cartoon avatar", callback_data="menu_cartoon"),
        ],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="menu_help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def photo_action_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Sticker qil", callback_data="do_sticker"),
            InlineKeyboardButton("🪄 Fonni o'chir", callback_data="do_rembg"),
        ],
        [
            InlineKeyboardButton("🎨 Cartoon", callback_data="do_cartoon"),
            InlineKeyboardButton("📦 Pakka qo'sh", callback_data="do_addtopack"),
        ],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")],
    ])

def pack_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi pak yaratish", callback_data="pack_new")],
        [InlineKeyboardButton("🔗 Mening pakim", callback_data="pack_mylink")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast"),
        ],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="back_main")]
    ])

# ─── Rasm qayta ishlash ───────────────────────────────────────────────────────

def prepare_sticker_png(img_bytes: bytes, watermark: bool = True) -> bytes:
    """512x512 shaffof PNG (pak uchun)."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img.thumbnail((512, 512), Image.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    canvas.paste(img, (x, y), img)

    if watermark:
        draw = ImageDraw.Draw(canvas)
        text = "@uzstickerbot"
        font_size = 18
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        m = 8
        draw.text((512 - tw - m + 1, 512 - th - m + 1), text, font=font, fill=(0, 0, 0, 140))
        draw.text((512 - tw - m, 512 - th - m), text, font=font, fill=(255, 255, 255, 200))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()

def make_sticker_webp(img_bytes: bytes) -> bytes:
    """Yuklab berish uchun WebP sticker."""
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
    edges = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 2
    )
    edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    cartoon = cv2.bitwise_and(color, edges_colored)
    _, buf = cv2.imencode(".png", cartoon)
    return buf.tobytes()

# ─── Sticker pak yordamchilari ────────────────────────────────────────────────

def pack_name_for(user_id: int) -> str:
    return f"uz{user_id}_by_{BOT_USERNAME}"

async def ensure_pack(bot, user_id: int, pack_title: str, first_png: bytes) -> bool:
    """Pak mavjud bo'lmasa yaratadi. True=yaratildi, False=xatolik."""
    name = pack_name_for(user_id)
    try:
        await bot.get_sticker_set(name)
        return True  # allaqachon bor
    except Exception:
        pass
    try:
        sticker = InputSticker(
            sticker=first_png,
            emoji_list=["🙂"],
            format="static",
        )
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=name,
            title=pack_title,
            stickers=[sticker],
        )
        return True
    except Exception as e:
        logger.error(f"Pak yaratishda xato: {e}")
        return False

async def add_to_pack(bot, user_id: int, png_bytes: bytes) -> bool:
    name = pack_name_for(user_id)
    try:
        sticker = InputSticker(
            sticker=png_bytes,
            emoji_list=["🙂"],
            format="static",
        )
        await bot.add_sticker_to_set(user_id=user_id, name=name, sticker=sticker)
        return True
    except Exception as e:
        logger.error(f"Sticker qo'shishda xato: {e}")
        return False

# ─── Handlerlar ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)
    is_admin = user.id == ADMIN_ID
    await update.message.reply_text(
        f"Salom, {user.first_name}! 👋\n\n"
        "Men *Sticker & Avatar* botiman 🎨\n"
        "Quyidagi menyudan tanlang:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_admin),
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data

    # ── Asosiy menyu ──
    if data == "back_main":
        context.user_data.pop("mode", None)
        is_admin = user.id == ADMIN_ID
        await query.edit_message_text(
            "Asosiy menyu 👇",
            reply_markup=main_menu_keyboard(is_admin),
        )

    elif data == "menu_sticker":
        await query.edit_message_text(
            "🖼 *Sticker yasash*\n\n"
            "Menga rasm yuboring, men uni Telegram sticker formatiga (512x512) o'zgartiraman.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )

    elif data == "menu_rembg":
        await query.edit_message_text(
            "🪄 *Fon o'chirish*\n\n"
            "Menga rasm yuboring, men orqa fonni avtomatik olib tashlayman.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )

    elif data == "menu_cartoon":
        await query.edit_message_text(
            "🎨 *Cartoon avatar*\n\n"
            "Menga rasm yuboring, men uni cartoon/anime uslubiga o'zgartiraman.",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )

    elif data == "menu_pack":
        await query.edit_message_text(
            "📦 *Sticker pak*\n\n"
            "O'zingizning shaxsiy sticker pakingizni yarating!\n"
            "Xohlagan rasmlaringizni pak ichiga qo'shing.",
            parse_mode="Markdown",
            reply_markup=pack_menu_keyboard(),
        )

    elif data == "menu_help":
        await query.edit_message_text(
            "ℹ️ *Qo'llanma*\n\n"
            "🖼 *Sticker yasash* — rasmni 512x512 WebP sticker qiladi\n"
            "🪄 *Fon o'chirish* — rasmdan orqa fonni olib tashlaydi\n"
            "🎨 *Cartoon avatar* — rasmni anime uslubiga o'zgartiradi\n"
            "📦 *Sticker pak* — o'z sticker pakingizni yarating\n\n"
            "Istalgan vaqt rasm yuboring va kerakli amalni tanlang!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")]
            ]),
        )

    # ── Rasm amallari ──
    elif data in ("do_sticker", "do_rembg", "do_cartoon", "do_addtopack"):
        img_bytes = context.user_data.get("photo")
        if not img_bytes:
            await query.edit_message_text(
                "❌ Rasm topilmadi. Iltimos, qayta rasm yuboring.",
                reply_markup=cancel_keyboard(),
            )
            return

        loop = asyncio.get_event_loop()

        if data == "do_sticker":
            await query.edit_message_text("🖼 Sticker tayyorlanmoqda...")
            result = await loop.run_in_executor(None, make_sticker_webp, img_bytes)
            buf = io.BytesIO(result)
            buf.name = "sticker.webp"
            await query.message.reply_sticker(sticker=buf)
            await query.edit_message_text(
                "✅ Sticker tayyor!",
                reply_markup=main_menu_keyboard(user.id == ADMIN_ID),
            )

        elif data == "do_rembg":
            await query.edit_message_text("🪄 Fon o'chirilmoqda...")
            result = await loop.run_in_executor(None, remove_background, img_bytes)
            buf = io.BytesIO(result)
            buf.name = "no_bg.png"
            await query.message.reply_document(
                document=buf, filename="no_background.png",
                caption="✅ Fon o'chirildi!"
            )
            await query.edit_message_text(
                "✅ Tayyor!",
                reply_markup=main_menu_keyboard(user.id == ADMIN_ID),
            )

        elif data == "do_cartoon":
            await query.edit_message_text("🎨 Cartoon yasalmoqda...")
            result = await loop.run_in_executor(None, make_cartoon, img_bytes)
            buf = io.BytesIO(result)
            await query.message.reply_photo(photo=buf, caption="✅ Cartoon avatar tayyor!")
            await query.edit_message_text(
                "✅ Tayyor!",
                reply_markup=main_menu_keyboard(user.id == ADMIN_ID),
            )

        elif data == "do_addtopack":
            pack_title = context.user_data.get("pack_title", f"{user.first_name} Stickers")
            await query.edit_message_text("📦 Pakka qo'shilmoqda...")
            png = await loop.run_in_executor(None, prepare_sticker_png, img_bytes, False)

            # Pak yo'q bo'lsa yaratamiz
            name = pack_name_for(user.id)
            try:
                await context.bot.get_sticker_set(name)
                ok = await add_to_pack(context.bot, user.id, png)
            except Exception:
                ok = await ensure_pack(context.bot, user.id, pack_title, png)

            if ok:
                link = f"https://t.me/addstickers/{name}"
                await query.edit_message_text(
                    f"✅ Sticker pakka qo'shildi!\n\n"
                    f"🔗 Pakingiz: {link}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📦 Pakni ochish", url=link)],
                        [InlineKeyboardButton("➕ Yana qo'shish", callback_data="menu_pack")],
                        [InlineKeyboardButton("◀️ Asosiy menyu", callback_data="back_main")],
                    ]),
                )
            else:
                await query.edit_message_text(
                    "❌ Pakka qo'shishda xatolik. Qayta urinib ko'ring.",
                    reply_markup=cancel_keyboard(),
                )

    # ── Sticker pak ──
    elif data == "pack_new":
        context.user_data["mode"] = "waiting_pack_title"
        await query.edit_message_text(
            "📦 *Yangi sticker pak*\n\n"
            "Pakingizga nom bering (masalan: *Mening stickerlarim*):",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )

    elif data == "pack_mylink":
        name = pack_name_for(user.id)
        try:
            await context.bot.get_sticker_set(name)
            link = f"https://t.me/addstickers/{name}"
            await query.edit_message_text(
                f"🔗 Sizning pakingiz:\n{link}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Pakni ochish", url=link)],
                    [InlineKeyboardButton("◀️ Orqaga", callback_data="menu_pack")],
                ]),
            )
        except Exception:
            await query.edit_message_text(
                "❌ Sizda hali pak yo'q.\n\nYangi pak yarating!",
                reply_markup=pack_menu_keyboard(),
            )

    # ── Admin panel ──
    elif data == "admin_panel":
        if user.id != ADMIN_ID:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        await query.edit_message_text(
            "👑 *Admin panel*",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )

    elif data == "admin_stats":
        if user.id != ADMIN_ID:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        s = get_stats()
        await query.edit_message_text(
            f"📊 *Statistika*\n\n"
            f"👥 Jami foydalanuvchilar: *{s['total']}*\n"
            f"🟢 Bugun faol: *{s['today_active']}*\n"
            f"🆕 Bugun yangi: *{s['today_new']}*",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )

    elif data == "admin_broadcast":
        if user.id != ADMIN_ID:
            await query.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        context.user_data["mode"] = "broadcast"
        await query.edit_message_text(
            "📢 *Xabar yuborish*\n\n"
            "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)

    # Agar pak nom kutilayotgan bo'lsa
    mode = context.user_data.get("mode")
    if mode == "waiting_pack_title":
        await update.message.reply_text(
            "❌ Avval pak nomini matn ko'rinishida yozing.",
            reply_markup=cancel_keyboard(),
        )
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    context.user_data["photo"] = buf.getvalue()

    await update.message.reply_text(
        "✅ Rasm qabul qilindi! Nima qilishni tanlang:",
        reply_markup=photo_action_keyboard(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user)
    text = update.message.text or ""
    mode = context.user_data.get("mode")

    # Pak nomi kutilmoqda
    if mode == "waiting_pack_title":
        title = text.strip()[:64]
        context.user_data["pack_title"] = title
        context.user_data.pop("mode", None)
        await update.message.reply_text(
            f"✅ Pak nomi saqlandi: *{title}*\n\n"
            "Endi rasm yuboring — birinchi sticker pakni yaratadi!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Asosiy menyu", callback_data="back_main")]
            ]),
        )
        return

    # Broadcast matni kutilmoqda
    if mode == "broadcast" and user.id == ADMIN_ID:
        context.user_data.pop("mode", None)
        users = load_users()
        sent = 0
        failed = 0
        status_msg = await update.message.reply_text(
            f"📢 Xabar yuborilmoqda... (0/{len(users)})"
        )
        for i, uid_str in enumerate(users.keys()):
            try:
                await context.bot.send_message(
                    chat_id=int(uid_str),
                    text=f"📢 *Yangilik:*\n\n{text}",
                    parse_mode="Markdown",
                )
                sent += 1
            except Exception:
                failed += 1
            if (i + 1) % 20 == 0:
                try:
                    await status_msg.edit_text(
                        f"📢 Xabar yuborilmoqda... ({i+1}/{len(users)})"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.05)

        await status_msg.edit_text(
            f"✅ Xabar yuborildi!\n\n"
            f"✔️ Muvaffaqiyatli: *{sent}*\n"
            f"❌ Xatolik: *{failed}*",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return

    # Boshqa holatlarda menyu ko'rsat
    is_admin = user.id == ADMIN_ID
    await update.message.reply_text(
        "Quyidagi menyudan tanlang 👇",
        reply_markup=main_menu_keyboard(is_admin),
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username
    logger.info(f"Bot: @{BOT_USERNAME}")


# ─── Health check web server (Render + Uptime Robot uchun) ───────────────────

async def run_health_server():
    from aiohttp import web

    async def health(request):
        return web.Response(text="OK — Sticker Bot ishlayapti ✅")

    server = web.Application()
    server.router.add_get("/", health)
    server.router.add_get("/health", health)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server: http://0.0.0.0:{port}")


async def run_bot():
    if not BOT_TOKEN:
        logger.error("STICKER_BOT_TOKEN topilmadi!")
        return

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Sticker bot ishga tushdi...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Doim ishlab tursin
    await asyncio.Event().wait()


def main() -> None:
    async def run_all():
        await asyncio.gather(
            run_health_server(),
            run_bot(),
        )

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
