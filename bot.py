import os
import json
from typing import Dict, Any, Tuple

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Set environment variable BOT_TOKEN.")
if ADMIN_CHAT_ID == 0:
    raise RuntimeError("ADMIN_CHAT_ID is empty. Set environment variable ADMIN_CHAT_ID (your numeric Telegram id).")

# -----------------------------
# Налаштування товарів
# -----------------------------

# Ключ товару: (об'єм, смак)
# Об'єм: "30" або "10"
FLAVORS = [
    ("вишня ментол", "Вишня + ментоловий холодок. Соковито і свіже."),
    ("кавун ментол", "Кавун + холодок. Легкий і дуже освіжаючий."),
    ("банан", "Солодкий банан. М’який післясмак."),
    ("мята", "Чиста м'ята. Холодна класика."),
    ("ківі", "Ківі з кислинкою. Яскравий смак."),
    ("блакитна малина", "Blue Raspberry. Кисло-солодко, топчик."),
]

# Склад (ліміти). Можеш змінювати командами /setstock та /addstock
# Формат: { "30|вишня ментол": 5, ... }
DEFAULT_STOCK = {
    f"30|{name}": 5 for (name, _) in FLAVORS
} | {
    f"10|{name}": 5 for (name, _) in FLAVORS
}

STOCK_FILE = "stock.json"  # локальний файл. На Render може скидатись при новому деплої.

def load_stock() -> Dict[str, int]:
    try:
        with open(STOCK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # гарантуємо, що всі ключі існують
        for k, v in DEFAULT_STOCK.items():
            data.setdefault(k, v)
        # прибираємо зайве, але можна лишити — не критично
        return {k: int(v) for k, v in data.items()}
    except Exception:
        return dict(DEFAULT_STOCK)

def save_stock(stock: Dict[str, int]) -> None:
    try:
        with open(STOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(stock, f, ensure_ascii=False, indent=2)
    except Exception:
        # якщо файлової системи нема/readonly — нічого, буде триматись у пам'яті
        pass

STOCK: Dict[str, int] = load_stock()

def item_key(volume: str, flavor: str) -> str:
    return f"{volume}|{flavor}"

def parse_item_key(k: str) -> Tuple[str, str]:
    vol, flav = k.split("|", 1)
    return vol, flav

def flavor_desc(flavor: str) -> str:
    for name, desc in FLAVORS:
        if name == flavor:
            return desc
    return "Опис скоро буде 🙂"

# -----------------------------
# Корзина в user_data
# -----------------------------
def get_cart(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, int]:
    cart = context.user_data.get("cart")
    if not isinstance(cart, dict):
        cart = {}
        context.user_data["cart"] = cart
    return cart

def cart_total_items(cart: Dict[str, int]) -> int:
    return sum(int(q) for q in cart.values())

# -----------------------------
# UI клавіатури
# -----------------------------
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Відкрити магазин", callback_data="open_shop")],
        [InlineKeyboardButton("🧺 Корзина", callback_data="cart")],
    ])

def kb_choose_volume() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cheezer 30 мл", callback_data="vol:30")],
        [InlineKeyboardButton("Cheezer 10 мл", callback_data="vol:10")],
        [InlineKeyboardButton("🧺 Корзина", callback_data="cart")],
    ])

def kb_flavors(volume: str) -> InlineKeyboardMarkup:
    rows = []
    for name, _ in FLAVORS:
        k = item_key(volume, name)
        qty = int(STOCK.get(k, 0))
        if qty <= 0:
            continue  # немає на складі — кнопки нема
        rows.append([InlineKeyboardButton(f"{name} ({qty} шт.)", callback_data=f"item:{k}")])

    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="open_shop")])
    rows.append([InlineKeyboardButton("🧺 Корзина", callback_data="cart")])
    return InlineKeyboardMarkup(rows)

def kb_item_actions(k: str) -> InlineKeyboardMarkup:
    vol, flav = parse_item_key(k)
    qty = int(STOCK.get(k, 0))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Додати в корзину", callback_data=f"add:{k}")],
        [InlineKeyboardButton("🧺 Корзина", callback_data="cart")],
        [InlineKeyboardButton("⬅️ До смаків", callback_data=f"vol:{vol}")],
        [InlineKeyboardButton(f"ℹ️ В наявності: {qty} шт.", callback_data="noop")],
    ])

def kb_cart(cart: Dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    if cart:
        # кнопки мінус для кожної позиції
        for k, q in cart.items():
            vol, flav = parse_item_key(k)
            rows.append([
                InlineKeyboardButton(f"➖ {vol}мл · {flav} (x{q})", callback_data=f"rm:{k}")
            ])
        rows.append([InlineKeyboardButton("✅ Замовити", callback_data="checkout")])
        rows.append([InlineKeyboardButton("🗑 Очистити корзину", callback_data="clear_cart")])
    rows.append([InlineKeyboardButton("🛒 До магазину", callback_data="open_shop")])
    return InlineKeyboardMarkup(rows)

# -----------------------------
# Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привіт! 👋\n"
        "Вибери товар і додай у корзину, а потім натисни *Замовити*."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_main())

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 Магазин: обери об'єм", reply_markup=kb_choose_volume())

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # показ складу (тільки адміну)
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔️ Команда доступна тільки адміну.")
        return

    lines = ["📦 *Склад:*"]
    for vol in ("30", "10"):
        lines.append(f"\n*{vol} мл*")
        for name, _ in FLAVORS:
            k = item_key(vol, name)
            lines.append(f"• {name}: `{int(STOCK.get(k, 0))}`")
    lines.append("\nКоманди:\n`/setstock 30|банан 10`\n`/addstock 10|мята 5`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def setstock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔️ Тільки адмін.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /setstock 30|банан 10")
        return

    k = context.args[0]
    try:
        qty = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Кількість має бути числом.")
        return

    STOCK[k] = max(0, qty)
    save_stock(STOCK)
    await update.message.reply_text(f"✅ Встановлено {k} = {STOCK[k]}")

async def addstock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔️ Тільки адмін.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /addstock 30|банан 5")
        return

    k = context.args[0]
    try:
        add = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Кількість має бути числом.")
        return

    STOCK[k] = max(0, int(STOCK.get(k, 0)) + add)
    save_stock(STOCK)
    await update.message.reply_text(f"✅ Додано. Тепер {k} = {STOCK[k]}")

async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    cart = get_cart(context)

    if data == "noop":
        return

    if data in ("open_shop",):
        await query.edit_message_text("🛒 Обери об'єм:", reply_markup=kb_choose_volume())
        return

    if data.startswith("vol:"):
        vol = data.split(":", 1)[1]
        await query.edit_message_text(f"Смаки Cheezer {vol} мл (показує тільки те, що є на складі):",
                                      reply_markup=kb_flavors(vol))
        return

    if data.startswith("item:"):
        k = data.split(":", 1)[1]
        vol, flav = parse_item_key(k)
        qty = int(STOCK.get(k, 0))
        if qty <= 0:
            await query.edit_message_text("😕 Цього товару вже немає на складі.", reply_markup=kb_choose_volume())
            return
        desc = flavor_desc(flav)
        text = (
            f"*{flav}* — *{vol} мл*\n"
            f"{desc}\n\n"
            f"📦 В наявності: *{qty}* шт.\n"
            f"🧺 У корзині всього: *{cart_total_items(cart)}*"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_item_actions(k))
        return

    if data.startswith("add:"):
        k = data.split(":", 1)[1]
        available = int(STOCK.get(k, 0))
        in_cart = int(cart.get(k, 0))
        if available <= 0:
            await query.edit_message_text("😕 Немає в наявності.", reply_markup=kb_choose_volume())
            return
        if in_cart >= available:
            await query.answer("Ліміт: більше немає на складі.", show_alert=True)
            return
        cart[k] = in_cart + 1

        vol, flav = parse_item_key(k)
        await query.answer(f"Додано в корзину: {flav} {vol}мл")
        # оновимо карточку товару
        desc = flavor_desc(flav)
        text = (
            f"*{flav}* — *{vol} мл*\n"
            f"{desc}\n\n"
            f"📦 В наявності: *{available}* шт.\n"
            f"✅ Додано в корзину. Тепер у корзині цього: *{cart[k]}*\n"
            f"🧺 У корзині всього: *{cart_total_items(cart)}*"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_item_actions(k))
        return

    if data == "cart":
        if not cart:
            await query.edit_message_text("🧺 Корзина порожня.", reply_markup=kb_cart(cart))
            return
        lines = ["🧺 *Твоя корзина:*"]
        for k, q in cart.items():
            vol, flav = parse_item_key(k)
            lines.append(f"• {vol} мл — {flav} × *{q}*")
        lines.append("\nНатисни ✅ *Замовити* коли готово.")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cart(cart))
        return

    if data.startswith("rm:"):
        k = data.split(":", 1)[1]
        if k in cart:
            cart[k] = int(cart[k]) - 1
            if cart[k] <= 0:
                cart.pop(k, None)
        await query.answer("Прибрано 1 шт.")
        # перерендер корзини
        if not cart:
            await query.edit_message_text("🧺 Корзина порожня.", reply_markup=kb_cart(cart))
        else:
            lines = ["🧺 *Твоя корзина:*"]
            for kk, q in cart.items():
                vol, flav = parse_item_key(kk)
                lines.append(f"• {vol} мл — {flav} × *{q}*")
            lines.append("\nНатисни ✅ *Замовити* коли готово.")
            await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=kb_cart(cart))
        return

    if data == "clear_cart":
        cart.clear()
        await query.edit_message_text("🧺 Корзина очищена.", reply_markup=kb_cart(cart))
        return

    if data == "checkout":
        if not cart:
            await query.answer("Корзина порожня.", show_alert=True)
            return

        # перевірка складу ще раз (щоб не замовили більше, ніж є)
        for k, q in list(cart.items()):
            available = int(STOCK.get(k, 0))
            if q > available:
                vol, flav = parse_item_key(k)
                await query.answer(f"Немає стільки на складі: {flav} {vol}мл (є {available})", show_alert=True)
                return

        # списуємо зі складу
        for k, q in cart.items():
            STOCK[k] = max(0, int(STOCK.get(k, 0)) - int(q))
        save_stock(STOCK)

        # формуємо повідомлення адміна з клікабельним профілем (працює навіть без username)
        user = update.effective_user
        mention = user.mention_html()  # клікабельне ім'я
        user_id = user.id

        order_lines = ["🛎️ <b>НОВЕ ЗАМОВЛЕННЯ</b>"]
        order_lines.append(f"👤 Клієнт: {mention}")
        order_lines.append(f"🆔 ID: <code>{user_id}</code>")

        if user.username:
            order_lines.append(f"🔗 Username: @{user.username}")

        order_lines.append("\n<b>Позиції:</b>")
        for k, q in cart.items():
            vol, flav = parse_item_key(k)
            order_lines.append(f"• {vol} мл — {flav} × <b>{q}</b>")

        # надсилаємо адміну
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="\n".join(order_lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

        # клієнту — підтвердження
        cart.clear()
        await query.edit_message_text(
            "✅ *Замовлення прийнято!*\n"
            "Чекайте повідомлення від менеджера 🙂",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main(),
        )
        return

    # якщо натиснули щось невідоме
    await query.answer("Невідома дія.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shop", shop_cmd))

    # адмінські:
    app.add_handler(CommandHandler("stock", stock_cmd))
    app.add_handler(CommandHandler("setstock", setstock_cmd))
    app.add_handler(CommandHandler("addstock", addstock_cmd))

    app.add_handler(CallbackQueryHandler(on_cb))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
