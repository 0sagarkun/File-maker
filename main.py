from io import BytesIO
from PIL import Image
from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = "8712164558:AAEQfE8UAaJDa3_5fGGhWzSZ6tAfcUK7gWM"
OWNER = "@sagarkun0"

SELECTING_FORMAT, COLLECTING_TEXT, ASKING_FILENAME = range(3)
user_sessions = {}

formats = [
    ("📄 txt", "txt"), ("📄 pdf", "pdf"), ("🐍 py", "py"),
    ("🌐 html", "html"), ("🎨 css", "css"),
    ("📦 json", "json"), ("📜 js", "js"),
    ("📄 xml", "xml"), ("📊 csv", "csv"),
    ("⚙️ yaml", "yaml"), ("🐘 php", "php"),
    ("💻 sh", "sh"), ("📘 md", "md"),
    ("🖼 svg", "svg"),
    ("🖼 png", "png"), ("📸 jpg", "jpg"), ("🌐 webp", "webp")
]

def get_format_keyboard():
    keyboard = []
    for i in range(0, len(formats), 2):
        row = [InlineKeyboardButton(formats[i][0], callback_data=formats[i][1])]
        if i+1 < len(formats):
            row.append(InlineKeyboardButton(formats[i+1][0], callback_data=formats[i+1][1]))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]])

def get_filename_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏩ Skip", callback_data="skip_filename"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

def get_user_count(user_id):
    return user_sessions.get(user_id, {}).get("file_count", 0)

def increment_count(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"file_count": 0}
    user_sessions[user_id]["file_count"] += 1

def auto_filename(user, ext, user_id):
    first = user.first_name or "User"
    last = user.last_name or ""
    name = f"{first}_{last}".strip("_") or "file"
    count = get_user_count(user_id) + 1
    return f"{name}_{count}.{ext}"

def text_to_file(content, ext):
    bio = BytesIO()
    try:
        if ext == "pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("helvetica", size=12)
            for line in content.split("\n"):
                pdf.multi_cell(0, 10, line)
            # Get PDF as bytes
            pdf_bytes = pdf.output(dest='S').encode('latin1')
            bio.write(pdf_bytes)
        else:
            bio.write(content.encode("utf-8"))
        bio.seek(0)
        return bio
    except Exception as e:
        raise Exception(f"File generation error: {e}")

def image_to_bytes(img_bytes, target):
    img = Image.open(BytesIO(img_bytes))
    out = BytesIO()
    if target == "jpg":
        img = img.convert("RGB")
        img.save(out, "JPEG", quality=95)
    elif target == "webp":
        img.save(out, "WEBP", quality=95)
    else:
        img.save(out, "PNG")
    out.seek(0)
    return out

async def start(update, context):
    msg = (
        "✨ *File Maker Bot* ✨\n\n"
        "Send text → get a file (txt, pdf, py, etc.)\n"
        "Send image → convert & save\n\n"
        "👇 *Choose format*"
    )
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📁 Select Format", callback_data="select_format")
        ]])
    )

async def select_format(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📂 *Choose file type:*",
        parse_mode="Markdown",
        reply_markup=get_format_keyboard()
    )
    return SELECTING_FORMAT

async def format_chosen(update, context):
    query = update.callback_query
    await query.answer()
    fmt = query.data
    uid = query.from_user.id
    if uid not in user_sessions:
        user_sessions[uid] = {"file_count": 0}
    user_sessions[uid]["format"] = fmt
    user_sessions[uid]["messages"] = []
    if fmt in ("png", "jpg", "webp"):
        await query.edit_message_text(
            f"📸 Send an **image** to convert to .{fmt}",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
        return COLLECTING_TEXT
    else:
        await query.edit_message_text(
            f"📝 *.{fmt}* selected. Send text messages. Type `/done` when ready.",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
        return COLLECTING_TEXT

async def handle_text(update, context):
    uid = update.effective_user.id
    if uid not in user_sessions or "format" not in user_sessions[uid]:
        await update.message.reply_text(
            "⚠️ Choose a format first.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📁 Select Format", callback_data="select_format")
            ]])
        )
        return
    fmt = user_sessions[uid]["format"]
    if fmt in ("png", "jpg", "webp"):
        await update.message.reply_text("Send an **image**, not text.")
        return
    user_sessions[uid].setdefault("messages", []).append(update.message.text)
    count = len(user_sessions[uid]["messages"])
    await update.message.reply_text(f"✅ Saved ({count}). Send more or `/done`.", reply_markup=get_back_keyboard())

async def handle_photo(update, context):
    uid = update.effective_user.id
    if uid not in user_sessions or "format" not in user_sessions[uid]:
        await update.message.reply_text(
            "⚠️ Choose a format first.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📁 Select Format", callback_data="select_format")
            ]])
        )
        return
    fmt = user_sessions[uid]["format"]
    if fmt not in ("png", "jpg", "webp"):
        await update.message.reply_text("Format is for text. Choose PNG/JPG/WebP.")
        return
    try:
        photo = await update.message.photo[-1].get_file()
        img_bytes = await photo.download_as_bytearray()
        file_io = image_to_bytes(img_bytes, fmt)
        filename = auto_filename(update.effective_user, fmt, uid)
        file_io.name = filename
        await update.message.reply_document(document=file_io, filename=filename)
        increment_count(uid)
        user_sessions.pop(uid, None)
    except Exception as e:
        await update.message.reply_text(f"❌ Image conversion failed: {e}. Contact {OWNER}")

async def done(update, context):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or not session.get("messages"):
        await update.message.reply_text("No messages to save. Send text first.")
        return
    await update.message.reply_text(
        "📝 Send **filename** (without extension) or press **Skip**:",
        parse_mode="Markdown",
        reply_markup=get_filename_keyboard()
    )
    return ASKING_FILENAME

async def receive_filename(update, context):
    uid = update.effective_user.id
    name = update.message.text.strip()
    session = user_sessions.get(uid)
    if not session:
        await update.message.reply_text("Session expired. Use /start again.")
        return ConversationHandler.END
    fmt = session["format"]
    combined = "\n---\n".join(session["messages"])
    if name and not name.startswith("/"):
        final = f"{name}.{fmt}"
    else:
        final = auto_filename(update.effective_user, fmt, uid)
    try:
        file_io = text_to_file(combined, fmt)
        file_io.name = final
        await update.message.reply_document(document=file_io, filename=final)
        increment_count(uid)
        user_sessions.pop(uid, None)
    except Exception as e:
        await update.message.reply_text(f"❌ File creation failed: {e}. Contact {OWNER}")
    return ConversationHandler.END

async def skip_filename(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    session = user_sessions.get(uid)
    if not session:
        await query.edit_message_text("Session expired. Use /start again.")
        return ConversationHandler.END
    fmt = session["format"]
    combined = "\n---\n".join(session["messages"])
    final = auto_filename(query.from_user, fmt, uid)
    try:
        file_io = text_to_file(combined, fmt)
        file_io.name = final
        await query.message.reply_document(document=file_io, filename=final)
        increment_count(uid)
        user_sessions.pop(uid, None)
        await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"❌ File creation failed: {e}. Contact {OWNER}")
    return ConversationHandler.END

async def back(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions.pop(uid, None)
    await query.edit_message_text(
        "📂 *Choose file type:*",
        parse_mode="Markdown",
        reply_markup=get_format_keyboard()
    )
    return SELECTING_FORMAT

async def cancel(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions.pop(uid, None)
    await query.edit_message_text("❌ Cancelled. Send /start to begin again.")
    return ConversationHandler.END

async def fallback_cancel(update, context):
    uid = update.effective_user.id
    user_sessions.pop(uid, None)
    await update.message.reply_text("❌ Cancelled. Use /start.")

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(select_format, pattern="^select_format$")
        ],
        states={
            SELECTING_FORMAT: [
                CallbackQueryHandler(format_chosen, pattern="^(txt|pdf|py|html|css|json|js|xml|csv|yaml|php|sh|md|svg|png|jpg|webp)$"),
                CallbackQueryHandler(back, pattern="^back$"),
                CallbackQueryHandler(cancel, pattern="^cancel$")
            ],
            COLLECTING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                MessageHandler(filters.PHOTO, handle_photo),
                CommandHandler("done", done),
                CallbackQueryHandler(back, pattern="^back$"),
                CallbackQueryHandler(cancel, pattern="^cancel$")
            ],
            ASKING_FILENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_filename),
                CallbackQueryHandler(skip_filename, pattern="^skip_filename$"),
                CallbackQueryHandler(cancel, pattern="^cancel$")
            ]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", fallback_cancel)]
    )
    app.add_handler(conv)
    print("Bot running... @sagarkun0")
    app.run_polling()

if __name__ == "__main__":
    main()
