# 🎨 UZ Sticker Bot

Telegram bot - rasmlardan sticker yasaydi, fon o'chiradi, cartoon avatar qiladi va sticker pak yaratadi.

## Funksiyalar

- 🖼 **Sticker yasash** — rasmni 512x512 WebP formatga o'zgartiradi
- 🪄 **Fon o'chirish** — AI yordamida orqa fonni olib tashlaydi
- 🎨 **Cartoon avatar** — rasmni anime/cartoon uslubiga o'zgartiradi
- 📦 **Sticker pak** — foydalanuvchi o'z sticker pakini yaratadi

## O'rnatish

```bash
pip install -r requirements.txt
```

## Ishga tushirish

```bash
export STICKER_BOT_TOKEN="your_bot_token_here"
python3 bot.py
```

## Admin

Admin ID ni `bot.py` faylidagi `ADMIN_ID` ga o'zgartiring.

Admin imkoniyatlari:
- 📊 Statistika (jami, bugungi faol va yangi foydalanuvchilar)
- 📢 Hammaga xabar yuborish (broadcast)
