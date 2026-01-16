import os
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =======================
# ENV (Render / локально)
# =======================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
PHOTO_URL = os.environ.get("PHOTO_URL", "").strip()  # опціонально

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Set environment variable BOT_TOKEN.")
if not ADMIN_CHAT_ID:
    raise RuntimeError("ADMIN_CHAT_ID is empty. Set environment variable ADMIN_CHAT_ID (your Telegram ID).")

DB_PATH = os.environ.get("DB_PATH", "bot.db")

# =======================
# DATA
# =======================
@dataclass(frozen=True)
class Flavor:
    id: int
    name: str
    tag: str  # "", "NEW", "LIMITED"
    desc: str

FLAVORS: List[Flavor] = [
    Flavor(1,  "ЧЕРЕШНЯ",            "NEW",     "Солодка черешня з яскравим ягідним профілем."),
    Flavor(2,  "ГРЕЙПФРУТ",          "LIMITED", "Соковитий грейпфрут із легкою гірчинкою."),
    Flavor(3,  "КАКТУС",             "LIMITED", "Екзотичний кактус, освіжаючий та незвичний."),
    Flavor(4,  "ЛІЧІ",               "LIMITED", "Ніжний солодкий лічі з фруктовим післясмаком."),
    Flavor(5,  "ВИНОГРАД",           "",        "Стиглий солодкий виноград."),
    Flavor(6,  "ВИШНЯ",              "",        "Класична соковита вишня."),
    Flavor(7,  "ВИШНЯ МЕНТОЛ",       "",        "Вишня + холодок ментолу."),
    Flavor(8,  "ГРАНАТ",             "",        "Насичений кисло-солодкий гранат."),
    Flavor(9,  "ДИНЯ",               "",        "Солодка стигла диня."),
    Flavor(10, "ЖОВТА МАЛИНА",       "",        "Ніжна жовта малина, солодко-ягідна."),
    Flavor(11, "ЖОВТА ЧЕРЕШНЯ",      "",        "М’яка солодка жовта черешня."),
    Flavor(12, "ЖОВТИЙ ДРАГОНФРУТ",  "",        "Екзотичний драгонфрут з фруктовою свіжістю."),
    Flavor(13, "КАВУН",              "",        "Літній соковитий кавун."),
    Flavor(14, "КАВУН МЕНТОЛ",       "",        "Кавун + ментоловий холодок."),
    Flavor(15, "ЛИМОН",              "",        "Яскравий цитрусовий лимон."),
    Flavor(16, "КІВІ",               "",        "Кисло-солодкий ківі."),
    Flavor(17, "М'ЯТА",              "",        "Чиста м’ята, максимально свіжа."),
    Flavor(18, "ПЕРСИК",             "",        "Ніжний солодкий персик."),
    Flavor(19, "ПОЛУНИЦЯ",           "",        "Соковита солодка полуниця."),
    Flavor(20, "СМОРОДИНА МЕНТОЛ",   "",        "Смородина + холодок."),
    Flavor(21, "ЯГОДИ",              "",        "Мікс ягід: яскраво та насичено."),
]

FLAVOR_BY_ID: Dict[int, Flavor] = {f.id: f for f in FLAVORS}


# =======================
# DB
# =======================
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db() -> None:
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            flavor_id INTEGER PRIMARY KEY,
            qty INTEGER NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS carts (
            user_id INTEGER NOT NULL,
            flavor_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            PRIMARY KEY (user_id, flavor_id)
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        # default stock if empty
        cur = con.execute("SELECT COUNT(*) AS c FROM stock")
        if cur.fetchone()["c"] == 0:
            for f in FLAVORS:
                con.execute("INSERT OR REPLACE INTO stock(flavor_id, qty) VALUES(?, ?)", (f.id, 5))
        con.commit()

def get_stock(flavor_id: int) -> int:
    with db() as con:
        row = con.execute("SELECT qty FROM stock WHERE flavor_id=?", (flavor_id,)).fetchone()
        return int(row["qty"]) if row else 0

def set_stock(flavor_id: int, qty: int) -> None:
    with db() as con:
        con.execute("INSERT OR REPLACE INTO stock(flavor_id, qty) VALUES(?, ?)", (flavor_id, qty))
        con.commit()

def add_cart(user_id: int, flavor_id: int, add_qty: int) -> None:
    with db() as con:
        row = con.execute("SELECT qty FROM carts WHERE user_id=? AND flavor_id=?", (user_id, flavor_id)).fetchone()
        if row:
            new_qty = int(row["qty"]) + add_qty
            if new_qty <= 0:
                con.execute("DELETE FROM carts WHERE user_id=? AND flavor_id=?", (user_id, flavor_id))
            else:
                con.execute("UPDATE carts SET qty=? WHERE user_id=? AND flavor_id=?", (new_qty, user_id, flavor_id))
        else:
            if add_qty > 0:
                con.execute("INSERT INTO carts(user_id, flavor_id, qty) VALUES(?, ?, ?)", (user_id, flavor_id, add_qty))
        con.commit()

def get_cart(user_id: int) -> List[Tuple[int, int]]:
    with db() as con:
        rows = con.execute("SELECT flavor_id, qty FROM carts WHERE user_id=? ORDER BY flavor_id", (user_id,)).fetchall()
        return [(int(r["flavor_id"]), int(r["qty"])) for r in rows]

def clear_cart(user_id: int) -> None:
    with db() as con:
        con.execute("DELETE FROM carts WHERE user_id=?", (user_id,))
        con.commit()

def set_setting(key: str, value: str) -> None:
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value))
        con.commit()

def get_setting(key: str) -> Optional[str]:
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None


# =======================
# PHOTO helper
# =======================
def get_product_photo() -> Optional[str]:
    """
    Return either:
    - Telegram file_id (saved in DB) OR
    - PHOTO_URL from env
    """
    file_id = get_setting("PHOTO_FILE_ID")
    if file_id:
        return file_id
    if PHOTO_URL:
        return PHOTO_URL
    return None


# =======================
# UI builders
# =======================
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Chaser 30 мл", callback_data="menu:flavors")],
        [InlineKeyboardButton("🧺 Корзина", callback_data="menu:cart")],
    ])

def kb_flavors() -> InlineKeyboardMarkup:
    buttons = []
    for f in FLAVORS:
        qty = get_stock(f.id)
        if qty <= 0:
            continue  # автоматично ховаємо зі списку
        tag = f" ✅ {f.tag}" if f.tag else ""
        text = f"{f.name}{tag} ({qty} шт.)"
        buttons.append([InlineKeyboardButton(text, callback_data=f"flavor:{f.id}")])
    buttons.append([InlineKeyboardButton("🧺 Корзина", callback_data="menu:cart")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)

def kb_flavor_detail(flavor_id: int) -> InlineKeyboardMarkup:
    qty = get_stock(flavor_id)
    can_add = qty > 0
    row1 = []
    if can_add:
        row1.append(InlineKeyboardButton("➕ В корзину", callback_data=f"cart:add:{flavor_id}"))
    row1.append(InlineKeyboardButton("🧺 Корзина", callback_data="menu:cart"))
    return InlineKeyboardMarkup([
        row1,
        [InlineKeyboardButton("⬅️ До смаків", callback_data="menu:flavors")],
    ])

def kb_cart(user_id: int) -> InlineKeyboardMarkup:
    cart = get_cart(user_id)
    buttons = []
    for fid, q in cart:
        f = FLAVOR_BY_ID.get(fid)
        if not f:
            continue
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"cart:dec:{fid}"),
            InlineKeyboardButton(f"{f.name} x{q}", callback_data=f"flavor:{fid}"),
            InlineKeyboardButton("➕", callback_data=f"cart:inc:{fid}"),
        ])
    if cart:
        buttons.append([InlineKeyboardButton("✅ Оформити замовлення", callback_data="order:checkout")])
        buttons.append([InlineKeyboardButton("🗑 Очистити корзину", callback_data="cart:clear")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(buttons)


# =======================
# Handlers
# =======================
def is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    return uid == ADMIN_CHAT_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Привіт! 👋\n"
        "Вибери товар:"
    )
    await update.message.reply_text(text, reply_markup=kb_main())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (
        "Команди:\n"
        "/start — меню\n"
        "\nАдмін:\n"
        "/list — список смаків з ID\n"
        "/stock — склад\n"
        "/setstock <id> <кількість>\n"
        "/setphoto — (відповісти на фото) встановити фото товарів\n"
    )
    await update.message.reply_text(txt)

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    lines = ["Смаки Chaser 30 мл (ID):"]
    for f in FLAVORS:
        tag = f" ✅ {f.tag}" if f.tag else ""
        lines.append(f"{f.id}. {f.name}{tag}")
    await update.message.reply_text("\n".join(lines))

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    lines = ["📦 Склад (30 мл):"]
    for f in FLAVORS:
        lines.append(f"• {f.id}. {f.name}: {get_stock(f.id)}")
    await update.message.reply_text("\n".join(lines))

async def setstock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return

    # /setstock <id> <qty>
    if len(context.args) != 2:
        await update.message.reply_text("Формат: /setstock <id> <кількість>\nНапр: /setstock 7 20")
        return

    try:
        fid = int(context.args[0])
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("ID і кількість мають бути числами. Напр: /setstock 7 20")
        return

    if fid not in FLAVOR_BY_ID:
        await update.message.reply_text("Нема такого ID. Дивись /list")
        return

    if qty < 0:
        qty = 0

    set_stock(fid, qty)
    await update.message.reply_text(f"✅ Встановлено: {fid}. {FLAVOR_BY_ID[fid].name} = {qty}")

async def setphoto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Зроби так: відправ фото сюди і ВІДПОВІДЬ на нього командою /setphoto")
        return
    file_id = update.message.reply_to_message.photo[-1].file_id
    set_setting("PHOTO_FILE_ID", file_id)
    await update.message.reply_text("✅ Фото встановлено. Тепер воно буде під кожним товаром.")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    user = update.effective_user
    user_id = user.id

    data = q.data or ""

    # MENU
    if data == "menu:main":
        await q.edit_message_text("Вибери товар:", reply_markup=kb_main())
        return

    if data == "menu:flavors":
        await q.edit_message_text("Смаки Chaser 30 мл (показує тільки те, що є на складі):", reply_markup=kb_flavors())
        return

    if data == "menu:cart":
        cart = get_cart(user_id)
        if not cart:
            await q.edit_message_text("🧺 Корзина порожня.", reply_markup=kb_main())
        else:
            # summary text
            lines = ["🧺 Твоя корзина:"]
            for fid, qty in cart:
                f = FLAVOR_BY_ID.get(fid)
                if f:
                    lines.append(f"• {f.name} x{qty}")
            await q.edit_message_text("\n".join(lines), reply_markup=kb_cart(user_id))
        return

    # FLAVOR DETAIL
    if data.startswith("flavor:"):
        fid = int(data.split(":")[1])
        f = FLAVOR_BY_ID.get(fid)
        if not f:
            await q.edit_message_text("Не знайдено.", reply_markup=kb_flavors())
            return

        qty = get_stock(fid)
        tag = f" ✅ {f.tag}" if f.tag else ""
        caption = (
            f"*Chaser 30 мл*\n"
            f"*{f.name}{tag}*\n\n"
            f"{f.desc}\n\n"
            f"На складі: {qty} шт."
        )

        photo = get_product_photo()
        if photo:
            # If current message has no photo, better to send a new photo message.
            # We'll try edit media if possible, else send new and delete old.
            try:
                await q.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=caption, parse_mode="Markdown"),
                    reply_markup=kb_flavor_detail(fid),
                )
            except Exception:
                await q.message.delete()
                await context.bot.send_photo(
                    chat_id=q.message.chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=kb_flavor_detail(fid),
                )
        else:
            await q.edit_message_text(caption, parse_mode="Markdown", reply_markup=kb_flavor_detail(fid))
        return

    # CART OPS
    if data.startswith("cart:add:"):
        fid = int(data.split(":")[2])
        if get_stock(fid) <= 0:
            await q.answer("Немає на складі.", show_alert=True)
            return
        add_cart(user_id, fid, 1)
        await q.answer("Додано в корзину ✅", show_alert=False)
        # refresh detail
        await on_callback(update, context)
        return

    if data.startswith("cart:inc:"):
        fid = int(data.split(":")[2])
        # дозволяємо додати тільки якщо є залишок
        current_in_cart = dict(get_cart(user_id)).get(fid, 0)
        if current_in_cart + 1 > get_stock(fid):
            await q.answer("Більше нема на складі.", show_alert=True)
            return
        add_cart(user_id, fid, 1)
        await q.edit_message_text("🧺 Твоя корзина:", reply_markup=kb_cart(user_id))
        return

    if data.startswith("cart:dec:"):
        fid = int(data.split(":")[2])
        add_cart(user_id, fid, -1)
        cart = get_cart(user_id)
        if not cart:
            await q.edit_message_text("🧺 Корзина порожня.", reply_markup=kb_main())
        else:
            await q.edit_message_text("🧺 Твоя корзина:", reply_markup=kb_cart(user_id))
        return

    if data == "cart:clear":
        clear_cart(user_id)
        await q.edit_message_text("🧺 Корзина очищена.", reply_markup=kb_main())
        return

    # CHECKOUT
    if data == "order:checkout":
        cart = get_cart(user_id)
        if not cart:
            await q.answer("Корзина порожня.", show_alert=True)
            return

        # перевірка складу перед списанням
        for fid, qty in cart:
            if qty > get_stock(fid):
                await q.answer("Хтось уже забрав частину товару. Онови корзину.", show_alert=True)
                return

        # списуємо зі складу
        for fid, qty in cart:
            set_stock(fid, get_stock(fid) - qty)

        # формуємо повідомлення адміну з "профілем"
        u = update.effective_user
        full_name = (u.full_name or "").strip()
        username = f"@{u.username}" if u.username else "(нема username)"
        mention = f"[{full_name}](tg://user?id={u.id})" if full_name else f"[Клієнт](tg://user?id={u.id})"

        lines = [
            "🛒 *НОВЕ ЗАМОВЛЕННЯ*",
            f"Клієнт: {mention}",
            f"ID: `{u.id}`",
            f"Username: {username}",
            "",
            "*Позиції:*",
        ]
        for fid, qty in cart:
            f = FLAVOR_BY_ID.get(fid)
            if f:
                lines.append(f"• Chaser 30 мл — {f.name} x{qty}")

        msg_admin = "\n".join(lines)

        # шлем адміну
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=msg_admin,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

        # чистимо корзину
        clear_cart(user_id)

        # відповідь клієнту
        await q.edit_message_text("✅ Замовлення прийнято! Чекайте повідомлення від менеджера.", reply_markup=kb_main())
        return

    # fallback
    await q.answer("Невідома дія.", show_alert=False)


# =======================
# MAIN
# =======================
def main() -> None:
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # admin commands
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("stock", stock_cmd))
    app.add_handler(CommandHandler("setstock", setstock_cmd))
    app.add_handler(CommandHandler("setphoto", setphoto_cmd))

    app.add_handler(CallbackQueryHandler(on_callback))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
