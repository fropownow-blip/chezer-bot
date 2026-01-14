import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("8132009354:AAGLa-XWYqNQp9tO8MJ_-leVoUm4uAlLiiw", "")
ADMIN_CHAT_ID = int(os.getenv("8155012442", "0"))

# --- Каталог товарів ---
CATALOG = {
    "30": {
        "title": "Cheezer 30 мл",
        "flavors": {
            "vishnya_mentol": {
                "name": "Вишня ментол",
                "desc": "Соковита вишня з прохолодним ментоловим фінішем."
            },
            "kavun_mentol": {
                "name": "Кавун ментол",
                "desc": "Солодкий кавун + холодок ментолу. Свіжий і яскравий смак."
            },
            "banan": {
                "name": "Банан",
                "desc": "Ніжний солодкий банан, м’який і приємний на кожен день."
            },
            "myata": {
                "name": "М'ята",
                "desc": "Чистий м’ятний холодок, максимально освіжає."
            },
            "kivi": {
                "name": "Ківі",
                "desc": "Кисло-солодкий ківі з легким фруктовим післясмаком."
            },
            "blakytnamalyna": {
                "name": "Блакитна малина",
                "desc": "Яскрава солодка малина з легенькою кислинкою."
            },
        }
    },
    "10": {
        "title": "Cheezer 10 мл",
        "flavors": {
            # ті самі смаки
            "vishnya_mentol": {"name": "Вишня ментол", "desc": "Соковита вишня з прохолодним ментоловим фінішем."},
            "kavun_mentol": {"name": "Кавун ментол", "desc": "Солодкий кавун + холодок ментолу. Свіжий і яскравий смак."},
            "banan": {"name": "Банан", "desc": "Ніжний солодкий банан, м’який і приємний на кожен день."},
            "myata": {"name": "М'ята", "desc": "Чистий м’ятний холодок, максимально освіжає."},
            "kivi": {"name": "Ківі", "desc": "Кисло-солодкий ківі з легким фруктовим післясмаком."},
            "blakytnamalyna": {"name": "Блакитна малина", "desc": "Яскрава солодка малина з легенькою кислинкою."},
        }
    }
}


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cheezer 30 мл", callback_data="size:30")],
        [InlineKeyboardButton("Cheezer 10 мл", callback_data="size:10")],
    ])


def flavors_kb(size_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for flavor_key, flavor in CATALOG[size_key]["flavors"].items():
        buttons.append([InlineKeyboardButton(flavor["name"], callback_data=f"flavor:{size_key}:{flavor_key}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(buttons)


def order_kb(size_key: str, flavor_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Замовити", callback_data=f"order:{size_key}:{flavor_key}")],
        [InlineKeyboardButton("⬅️ До смаків", callback_data=f"back:flavors:{size_key}")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! 👋\nВибери товар:",
        reply_markup=main_menu_kb()
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # Вибір об'єму
    if data.startswith("size:"):
        size_key = data.split(":")[1]
        title = CATALOG[size_key]["title"]
        await query.edit_message_text(
            f"Ось всі смаки для **{title}**. Обери смак:",
            reply_markup=flavors_kb(size_key),
            parse_mode="Markdown"
        )
        return

    # Вибір смаку (показ опису + кнопка замовити)
    if data.startswith("flavor:"):
        _, size_key, flavor_key = data.split(":")
        title = CATALOG[size_key]["title"]
        flavor = CATALOG[size_key]["flavors"][flavor_key]
        text = (
            f"**{title} — {flavor['name']}**\n\n"
            f"{flavor['desc']}\n\n"
            "Натисни «Замовити», щоб відправити заявку менеджеру."
        )
        await query.edit_message_text(
            text,
            reply_markup=order_kb(size_key, flavor_key),
            parse_mode="Markdown"
        )
        return

    # Назад
    if data == "back:main":
        await query.edit_message_text("Вибери товар:", reply_markup=main_menu_kb())
        return

    if data.startswith("back:flavors:"):
        size_key = data.split(":")[2]
        title = CATALOG[size_key]["title"]
        await query.edit_message_text(
            f"Ось всі смаки для **{title}**. Обери смак:",
            reply_markup=flavors_kb(size_key),
            parse_mode="Markdown"
        )
        return

    # Замовлення
    if data.startswith("order:"):
        _, size_key, flavor_key = data.split(":")
        title = CATALOG[size_key]["title"]
        flavor = CATALOG[size_key]["flavors"][flavor_key]["name"]

        user = query.from_user
        username = f"@{user.username}" if user.username else "(без юзернейму)"
        user_line = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Користувач"

        # Повідомлення адміну
        if ADMIN_CHAT_ID != 0:
            admin_text = (
                "🧾 **Нове замовлення**\n\n"
                f"👤 Клієнт: {user_line}\n"
                f"🔗 Username: {username}\n"
                f"🆔 ID: `{user.id}`\n\n"
                f"📦 Товар: **{title}**\n"
                f"🍓 Смак: **{flavor}**\n\n"
                "Напиши клієнту в особисті."
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                parse_mode="Markdown"
            )

        # Відповідь клієнту
        await query.edit_message_text(
            "✅ Замовлення прийнято!\nОчікуйте повідомлення від менеджера."
        )
        return


def run():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Set environment variable BOT_TOKEN.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run()

