# CodeSpark Bot - Upgraded Version (with BMC webhook, language handling, and premium automation)
# File: bot.py
import asyncio
import json
import random
import os
from datetime import datetime
from aiohttp import web
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 123456789  # Your Telegram ID
QUIZ_FILE = "quizzes.json"
USER_FILE = "users.json"
PREMIUM_FILE = "premium_users.json"
LANG_FILE = "user_languages.json"
MSG_FILE = "messages.json"
EMAIL_MAP_FILE = "user_emails.json"

# --- File Helpers ---
def load_json(path):
    """This function reads a JSON file from the given path and returns it as a Python dictionary.
     If the file is missing or unreadable, it returns an empty dictionary."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Localization ---
def get_lang(user_id):
    """returns a value like "en" or "fa" """
    langs = load_json(LANG_FILE)
    return langs.get(str(user_id), "en")

def t(user_id, key):
    """due to the structure of k, v s in the MSG file
    here "key" plays a crucial role in retrival
    * here the parameter user_id is just needed for the function
    get_lang used in messages var """
    lang = get_lang(user_id) # "en" or "fa"
    messages = load_json(MSG_FILE)
    return messages.get(key, {}).get(lang, key)

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = t(user_id, "start")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("☕ Support Us", url="https://buymeacoffee.com/yourname")],
        [InlineKeyboardButton("🇮🇷 فارسی / English", callback_data="change_lang")],
        [InlineKeyboardButton("🚀 Upgrade to Pro", callback_data="upgrade")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(update.effective_user.id, "help"))

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """apparently we store the question id in both callback and user info
    (so we could use it later, for clarity sace)"""
    user_id = str(update.effective_user.id)
    quizzes = load_json(QUIZ_FILE)  # now a list of dicts
    users = load_json(USER_FILE)
    premium = load_json(PREMIUM_FILE)
    lang = get_lang(user_id)  # "en" or "fa"

    if user_id not in users:
        users[user_id] = {"score": 0, "current_q": None}

    question = random.choice(quizzes)

    # Check if it's a premium question and user is not premium
    if question.get("premium") and user_id not in premium:
        await update.message.reply_text(t(user_id, "premium_required"))
        return

    users[user_id]["current_q"] = question["id"]
    save_json(USER_FILE, users)

    # Get question and options in user's language
    q_text = question["question"].get(lang, question["question"]["en"])
    q_options = question["options"].get(lang, question["options"]["en"])

    # Create button list
    buttons = [
        [InlineKeyboardButton(opt, callback_data=f"answer:{question['id']}:{opt}")]
        for opt in q_options
    ]

    await update.message.reply_text(
        f"🧠 {q_text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USER_FILE)
    score = users.get(str(update.effective_user.id), {}).get("score", 0)
    # the parallel value to key "ID" are "score" "current_q"
    await update.message.reply_text(f"🏆 {t(update.effective_user.id, 'score')} {score}")

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # we use this because we are expecting a button click response
    await query.answer()
    # by this we tell telegram that ok thank you
    # you've sent us the call_back and we've received it!
    user_id = str(query.from_user.id)
    lang = get_lang(user_id)  # "en" or "fa"

    _, question_id, selected_option = query.data.split(":") # multiple assignment
    quizzes = load_json(QUIZ_FILE) # a list of dicts which also include dicts!
    question = next((q for q in quizzes if q["id"] == question_id), None)
    if not question:
        await query.edit_message_text("❌ Question not found.")
        return
    # This line sends an error message to the user and stops the function (return)
    # to avoid running the rest of the logic on a nonexistent question.

    users = load_json(USER_FILE)
    correct = question["answer"].get(lang, question["answer"]["en"])
    if selected_option == correct:
        users[user_id]["score"] += 1
        text = t(user_id, "correct") + "\n\n" + question["explanation"].get(lang, question["explanation"]["en"])
    else:
        text = t(user_id, "wrong") + f" {correct}\n\n" + question["explanation"].get(lang, question["explanation"]["en"])
    users[user_id]["current_q"] = None
    save_json(USER_FILE, users)
    await query.edit_message_text(text)

async def upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """probably this function sends message when a premium content
     tried to get reached by an ordinary user """
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(t(update.effective_user.id, "upgrade"))

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """the function to change users' languages (obviously after they initialized their language at first)"""
    user_id = str(update.effective_user.id)
    langs = load_json(LANG_FILE)
    current = langs.get(user_id, "en")
    langs[user_id] = "fa" if current == "en" else "en"
    save_json(LANG_FILE, langs)
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(t(user_id, "lang_set"))

async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """an async Telegram bot command handler that
    Gets and stores the user's email using their Telegram ID"""
    user_id = str(update.effective_user.id)
    email = " ".join(context.args).strip()
    emails = load_json(EMAIL_MAP_FILE)
    emails[user_id] = email
    save_json(EMAIL_MAP_FILE, emails)
    await update.callback_query.message.reply_text(t(update.effective_user.id, "email_received"))

# --- Admin Broadcast ---
async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """This function:
    Can only be triggered by the admin.
    Sends the remaining message (after removing /broadcast)
    to every user ID in your stored JSON file.
    e.g usage: (telegram message) -> /broadcast Hello all! """
    if update.effective_user.id != ADMIN_ID:
        return
    msg = update.message.text.replace("/broadcast", "").strip()
    users = load_json(USER_FILE)
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
        except:
            continue

    # context.bot.send_message(chat_id=int(uid), text=msg):
    # Sends a message to that user. int(uid) is used because JSON keys are strings,
    # but chat_id needs to be an integer. msg is the message you want to send.

# --- Webhook for Buy Me a Coffee ---
async def bmc_webhook(request):
    data = await request.json()
    email = data.get("payer_email")
    amount = float(data.get("amount", 0))

    emails = load_json(EMAIL_MAP_FILE)
    premium = load_json(PREMIUM_FILE)

    for uid, saved_email in emails.items():
        if saved_email == email:
            premium[uid] = {
                "email": email,
                "amount": amount,
                #"timestamp": datetime.datetime. datetime. now(datetime. UTC).isoformat()
            }
            save_json(PREMIUM_FILE, premium)
            break

    return web.Response(text="OK")

# --- Main ---
async def main():
    # Build bot app
    app = ApplicationBuilder().token(TOKEN).build()

    # Add Telegram command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("setemail", set_email))
    app.add_handler(CommandHandler("broadcast", handle_admin_broadcast))

    # Add Telegram callback query handlers
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer:"))
    app.add_handler(CallbackQueryHandler(upgrade_callback, pattern="^upgrade$"))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^change_lang$"))

    # Init + Start the Telegram bot
    await app.initialize()
    await app.start()
    await app.bot.set_webhook(f"https://codespark-6p27.onrender.com/{TOKEN}")

    # Setup aiohttp web app for handling webhooks
    web_app = web.Application()
    web_app.add_routes([
        web.post("/bmc_webhook", bmc_webhook),
        web.post(f"/{TOKEN}", app.update_queue.put_nowait),  # Telegram webhook handler
    ])

    # Run aiohttp server (instead of using _run_app which is internal/private API)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8443)))
    await site.start()

    print("Bot is running on webhook...")

    # Keep process alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ BOT CRASHED:", e)
