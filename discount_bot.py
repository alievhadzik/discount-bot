"""
Telegram-бот "Скидки и промокоды"
==================================

Что делает бот:
- показывает пользователю меню категорий (одежда, электроника, красота и т.д.)
- по нажатию на категорию присылает список актуальных скидок с твоими партнёрскими ссылками
- у тебя (админа) есть команды, чтобы добавлять/удалять скидки без изменения кода
- считает подписчиков и показывает статистику по команде /stats (только для админа)

Установка (один раз):
1. Установи Python 3.10+
2. В терминале: pip install python-telegram-bot==22.8
3. Получи токен бота у @BotFather в Telegram (команда /newbot)
4. Узнай свой Telegram ID у бота @userinfobot — это нужно, чтобы только ты
   мог добавлять/удалять скидки
5. Впиши токен и свой ID в переменные ниже (BOT_TOKEN и ADMIN_IDS)
6. Запусти: python discount_bot.py

Хранилище данных:
Все скидки хранятся в файле discounts.json рядом со скриптом.
Все подписчики хранятся в файле users.json рядом со скриптом.
Файлы создадутся автоматически при первом запуске.
"""

import json
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============ НАСТРОЙКИ (заполни перед запуском) ============

from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Telegram ID пользователей, которым разрешено добавлять/удалять скидки.
# Узнать свой ID можно у бота @userinfobot
ADMIN_IDS = [6708840511]  # замени на свой ID

DATA_FILE = "discounts.json"
USERS_FILE = "users.json"

CATEGORIES = ["Одежда", "Электроника", "Красота", "Дом и быт", "Путешествия"]

# ==============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_data():
    if not os.path.exists(DATA_FILE):
        data = {cat: [] for cat in CATEGORIES}
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users():
    if not os.path.exists(USERS_FILE):
        save_users([])
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def register_user(user_id: int, username: str, first_name: str):
    """Сохраняет пользователя в базу, если его там ещё нет."""
    users = load_users()
    for u in users:
        if u["id"] == user_id:
            return  # уже есть
    users.append({
        "id": user_id,
        "username": username or "",
        "first_name": first_name or "",
    })
    save_users(users)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------- Команды пользователя ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in CATEGORIES
    ]
    await update.message.reply_text(
        "Привет! Я собираю свежие скидки и промокоды 🎁\n\n"
        "Выбери категорию, чтобы посмотреть актуальные предложения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]

    data = load_data()
    items = data.get(category, [])

    if not items:
        text = f"В категории «{category}» пока нет скидок. Загляни позже!"
    else:
        lines = [f"🔥 Скидки: {category}\n"]
        for item in items:
            lines.append(f"• {item['title']}\n  {item['link']}\n")
        text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in CATEGORIES
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
    )


# ---------------- Команды администратора ----------------

async def add_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Использование:
    /add Категория | Название скидки | Ссылка

    Пример:
    /add Электроника | Наушники -30% на Ozon | https://ozon.ru/xxxxx
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    text = update.message.text.partition(" ")[2]
    parts = [p.strip() for p in text.split("|")]

    if len(parts) != 3:
        await update.message.reply_text(
            "Формат команды:\n/add Категория | Название | Ссылка\n\n"
            "Пример:\n/add Электроника | Наушники -30% на Ozon | https://ozon.ru/xxxxx"
        )
        return

    category, title, link = parts

    if category not in CATEGORIES:
        await update.message.reply_text(
            f"Неизвестная категория. Доступные: {', '.join(CATEGORIES)}"
        )
        return

    data = load_data()
    data[category].append({"title": title, "link": link})
    save_data(data)

    await update.message.reply_text(f"Добавлено в «{category}»: {title}")


async def list_discounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все скидки с номерами — для удаления."""
    if not is_admin(update.effective_user.id):
        return

    data = load_data()
    lines = []
    for cat, items in data.items():
        if items:
            lines.append(f"\n{cat}:")
            for i, item in enumerate(items):
                lines.append(f"  [{cat}:{i}] {item['title']}")

    text = "\n".join(lines) if lines else "Скидок пока нет."
    await update.message.reply_text(text)


async def remove_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Использование: /remove Категория:номер
    Номер смотри в /list
    """
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args or ":" not in args[0]:
        await update.message.reply_text("Формат: /remove Категория:номер (номер бери из /list)")
        return

    category, _, idx_str = args[0].partition(":")
    data = load_data()

    try:
        idx = int(idx_str)
        removed = data[category].pop(idx)
        save_data(data)
        await update.message.reply_text(f"Удалено: {removed['title']}")
    except (KeyError, IndexError, ValueError):
        await update.message.reply_text("Не нашёл такую скидку. Проверь /list.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает количество подписчиков бота (только для админа)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    users = load_users()
    total = len(users)

    if total == 0:
        await update.message.reply_text("Пока ни одного подписчика.")
        return

    lines = [f"👥 Всего подписчиков: {total}\n"]
    lines.append("Последние 10:")
    for u in users[-10:]:
        name = u.get("username") or u.get("first_name") or str(u["id"])
        lines.append(f"• {name} (ID: {u['id']})")

    await update.message.reply_text("\n".join(lines))


async def search_discounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Поиск скидок по ключевому слову.
    Использование: /search наушники
    """
    query_text = " ".join(context.args).strip().lower()
    if not query_text:
        await update.message.reply_text(
            "Напиши, что ищешь. Пример:\n/search наушники"
        )
        return

    data = load_data()
    found = []
    for category, items in data.items():
        for item in items:
            if query_text in item["title"].lower():
                found.append((category, item))

    if not found:
        await update.message.reply_text(
            f"По запросу «{query_text}» ничего не нашлось. Попробуй другое слово."
        )
        return

    lines = [f"🔍 Результаты по запросу «{query_text}»:\n"]
    for category, item in found:
        lines.append(f"• [{category}] {item['title']}\n  {item['link']}\n")

    await update.message.reply_text(
        "\n".join(lines), disable_web_page_preview=True
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Рассылка сообщения всем подписчикам (только для админа).
    Использование: /broadcast Текст сообщения
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await update.message.reply_text(
            "Напиши текст рассылки после команды.\nПример:\n/broadcast Новые скидки уже в боте!"
        )
        return

    users = load_users()
    if not users:
        await update.message.reply_text("Пока нет ни одного подписчика для рассылки.")
        return

    await update.message.reply_text(f"Начинаю рассылку для {len(users)} человек...")

    sent = 0
    failed = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["id"], text=text)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"Рассылка завершена.\nДоставлено: {sent}\nНе доставлено: {failed}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Команды:\n"
        "/start — открыть меню категорий\n"
        "/search слово — найти скидку по названию\n"
    )
    if is_admin(update.effective_user.id):
        text += (
            "\nАдмин-команды:\n"
            "/add Категория | Название | Ссылка — добавить скидку\n"
            "/list — посмотреть все скидки с номерами\n"
            "/remove Категория:номер — удалить скидку\n"
            "/stats — посмотреть число подписчиков\n"
            "/broadcast Текст — разослать сообщение всем подписчикам\n"
        )
    await update.message.reply_text(text)


def main():
    if BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
        print("⚠️  Сначала впиши свой токен в переменную BOT_TOKEN!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_discount))
    app.add_handler(CommandHandler("list", list_discounts))
    app.add_handler(CommandHandler("remove", remove_discount))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("search", search_discounts))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(show_category, pattern=r"^cat:"))

    print("Бот запущен. Останови через Ctrl+C.")
    app.run_polling()


if __name__ == "__main__":
    main()
