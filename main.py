from io import BytesIO
import zipfile
from PIL import Image
from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

TOKEN = "8712164558:AAEQfE8UAaJDa3_5fGGhWzSZ6tAfcUK7gWM"
OWNER = "@sagarkun0 and @sagarkunx"

# Conversation states
SELECTING_FORMAT, COLLECTING_TEXT, ASKING_FILENAME = range(3)
WAITING_FOR_ZIP_FILES, WAITING_NEW_NAME = range(3, 5)

user_sessions = {}

# ---------- Format list and keyboards ----------
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

# ---------- Helper functions ----------
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
                clean_line = line.encode('latin-1', errors='ignore').decode('latin-1')
                pdf.multi_cell(0, 10, clean_line)
            pdf_output = pdf.output(dest='S')
            if isinstance(pdf_output, str):
                bio.write(pdf_output.encode('latin1'))
            elif isinstance(pdf_output, bytes):
                bio.write(pdf_output)
            elif isinstance(pdf_output, bytearray):
                bio.write(bytes(pdf_output))
            else:
                bio.write(str(pdf_output).encode('latin1'))
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

# ---------- Start and format selection ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✨ *File Maker Bot* ✨\n\n"
        "Send text → get a file (txt, pdf, py, etc.)\n"
        "Send image → convert & save\n\n"
        "👇 *Choose format* to begin\n"
        "Or type /more for extra tools."
    )
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📁 Select Format", callback_data="select_format")
        ]])
    )

async def select_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📂 *Choose file type:*",
        parse_mode="Markdown",
        reply_markup=get_format_keyboard()
    )
    return SELECTING_FORMAT

async def format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# ---------- Handle text and images ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("✨ Press /start to make a new file ✨")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}. Contact {OWNER}")

# ---------- Finish text batch ----------
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def receive_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("✨ Press /start to make a new file ✨")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}. Contact {OWNER}")
    return ConversationHandler.END

async def skip_filename(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.message.reply_text("✨ Press /start to make a new file ✨")
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}. Contact {OWNER}")
    return ConversationHandler.END

# ---------- Back and Cancel ----------
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def fallback_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_sessions.pop(uid, None)
    await update.message.reply_text("Cancelled. Press /start to begin again.")

# ---------- /more command (only ZIP and rename) ----------
async def more_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🔧 *More Features* 🔧\n\n"
        "• *Make a zip* – collect multiple files → send as ZIP\n"
        "• *Name Changer* – rename any file"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Make a zip", callback_data="more_zip")],
        [InlineKeyboardButton("✏️ Name Changer", callback_data="more_rename")],
        [InlineKeyboardButton("🔙 Back to main", callback_data="back_to_start")]
    ])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)
    await query.delete_message()

# --- ZIP creator ---
async def start_zip_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions[uid] = {"zip_files": [], "mode": "zip_collect"}
    await query.edit_message_text(
        "📦 *ZIP Creator* 📦\n\nSend me **files** (documents, images).\n"
        "Type `/donezip` when finished.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_zip")]])
    )
    return WAITING_FOR_ZIP_FILES

async def collect_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or session.get("mode") != "zip_collect":
        await update.message.reply_text("Use /more → Make a zip first.")
        return
    if update.message.document:
        file_obj = await update.message.document.get_file()
        filename = update.message.document.file_name
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        filename = f"photo_{len(session['zip_files'])+1}.jpg"
    else:
        await update.message.reply_text("Send a file (document or photo).")
        return
    data = await file_obj.download_as_bytearray()
    session["zip_files"].append((filename, data))
    count = len(session["zip_files"])
    await update.message.reply_text(f"✅ Added ({count}). Send more or `/donezip`.")

async def finish_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or not session.get("zip_files"):
        await update.message.reply_text("No files collected. Use /more → Make a zip.")
        return
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in session["zip_files"]:
            zf.writestr(name, data)
    zip_buffer.seek(0)
    await update.message.reply_document(
        document=zip_buffer,
        filename=f"archive_{uid}.zip",
        caption=f"✅ ZIP with {len(session['zip_files'])} files."
    )
    user_sessions.pop(uid, None)
    await update.message.reply_text("✨ Press /start to make a new file ✨")
    return ConversationHandler.END

async def cancel_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions.pop(uid, None)
    await query.edit_message_text("❌ ZIP cancelled. Use /more again.")

# --- Name changer ---
async def start_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions[uid] = {"mode": "rename_waiting"}
    await query.edit_message_text(
        "✏️ *Name Changer* ✏️\n\nSend me a **file**.\nThen I'll ask for the new name.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_rename")]])
    )
    return WAITING_NEW_NAME

async def collect_file_for_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or session.get("mode") != "rename_waiting":
        await update.message.reply_text("Use /more → Name Changer first.")
        return
    if update.message.document:
        file_obj = await update.message.document.get_file()
        original_name = update.message.document.file_name
        ext = original_name.split('.')[-1] if '.' in original_name else ''
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        ext = "jpg"
    else:
        await update.message.reply_text("Send a document or photo.")
        return
    data = await file_obj.download_as_bytearray()
    session["rename_data"] = data
    session["rename_ext"] = ext
    await update.message.reply_text("📝 Send the new **filename** (without extension).\nExample: `my_document`")
    return WAITING_NEW_NAME

async def receive_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or "rename_data" not in session:
        await update.message.reply_text("No file found. Start again with /more.")
        return
    new_name = update.message.text.strip()
    if not new_name:
        await update.message.reply_text("Send a valid name.")
        return
    ext = session.get("rename_ext", "")
    final = f"{new_name}.{ext}" if ext else new_name
    file_io = BytesIO(session["rename_data"])
    file_io.name = final
    await update.message.reply_document(document=file_io, filename=final)
    user_sessions.pop(uid, None)
    await update.message.reply_text("✨ Press /start to make a new file ✨")
    return ConversationHandler.END

async def cancel_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user_sessions.pop(uid, None)
    await query.edit_message_text("❌ Rename cancelled.")

# ---------- Main ----------
def main():
    app = Application.builder().token(TOKEN).build()

    # Main conversion conversation
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

    # /more and its tools
    app.add_handler(CommandHandler("more", more_command))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))

    zip_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_zip_collection, pattern="^more_zip$")],
        states={
            WAITING_FOR_ZIP_FILES: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, collect_zip_file),
                CommandHandler("donezip", finish_zip),
                CallbackQueryHandler(cancel_zip, pattern="^cancel_zip$")
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(zip_conv)

    rename_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_rename, pattern="^more_rename$")],
        states={
            WAITING_NEW_NAME: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, collect_file_for_rename),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_name),
                CallbackQueryHandler(cancel_rename, pattern="^cancel_rename$")
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(rename_conv)

    print("Bot running... @sagarkun0")
    app.run_polling()

if __name__ == "__main__":
    main()
