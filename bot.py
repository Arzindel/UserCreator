from __future__ import annotations

import asyncio
import html
import os

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.error import TimedOut, BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN missing")

from app import goldenott_create

ASK_USERNAME, ASK_PASSWORD, ASK_COUNTRY, ASK_ADULT = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi\\! I’ll create a user for you\\.\n"
        "Send me the *username* you want\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return ASK_USERNAME

async def got_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candidate = update.message.text.strip()
    if not (candidate.isalnum() and len(candidate) >= 7):
        await update.message.reply_text(
            "🚫 *Invalid username*: only letters/numbers, at least 7 chars\\."
            "Please send another one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ASK_USERNAME

    context.user_data["username"] = candidate
    await update.message.reply_text(
        "Now the *password*:", parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_PASSWORD

async def got_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["password"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Auto", callback_data="country_auto"),
         InlineKeyboardButton("🔒 VPN", callback_data="country_vpn")]
    ])
    await update.message.reply_text(
        "Choose *Location*:", reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_COUNTRY

async def got_country_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # Safely acknowledge the button press (ignoring slow‑network timeouts)
    try:
        await q.answer()
    except TimedOut:
        pass

    context.user_data["forced_country"] = "" if q.data == "country_auto" else "ALL"

    # Remove the inline keyboard; ignore if already modified by a double‑tap
    try:
        await q.edit_message_reply_markup(None)
    except BadRequest:
        pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes", callback_data="adult_yes"),
         InlineKeyboardButton("🚫 No",  callback_data="adult_no")]
    ])
    await q.message.reply_text(
        "Mark as *adult*?", reply_markup=kb, parse_mode=ParseMode.MARKDOWN_V2
    )
    return ASK_ADULT

async def got_adult_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except TimedOut:
        pass

    adult_flag = "1" if q.data == "adult_yes" else "0"
    u = context.user_data["username"]
    p = context.user_data["password"]
    fc = context.user_data["forced_country"]

    try:
        await q.edit_message_reply_markup(None)
    except BadRequest:
        pass

    await q.message.reply_text("⏳ Working…")

    try:
        html_response = await asyncio.to_thread(goldenott_create, u, p, adult_flag, fc)

        soup = BeautifulSoup(html_response, "html.parser")
        err_div = soup.select_one("div.alert-danger")
        if err_div:
            text = err_div.get_text(" ", strip=True)
            await q.message.reply_text(f"❌ Error: {text}")
        else:
            await q.message.reply_text("✅ User created successfully!")

    except Exception as exc:
        await q.message.reply_text(f"❌ Error: {exc}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Conversation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    builder = Application.builder().token(BOT_TOKEN)
    # Older python‑telegram‑bot versions (<21) don't have .httpx_timeout()
    if hasattr(builder, "httpx_timeout"):
        builder = builder.httpx_timeout(20)
    app = builder.build()
    convo = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_username)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_password)],
            ASK_COUNTRY: [CallbackQueryHandler(got_country_button, pattern="^country_(auto|vpn)$")],
            ASK_ADULT: [CallbackQueryHandler(got_adult_button, pattern="^adult_(yes|no)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="goldenott_convo",
        allow_reentry=True,
    )
    app.add_handler(convo)
    app.add_handler(CommandHandler("cancel", cancel))
    print("Bot is running – Ctrl+C to stop")
    app.run_polling()

if __name__ == "__main__":
    main()