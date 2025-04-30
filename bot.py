import os
import subprocess
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from keyboards import *

# Load vars from .env
load_dotenv()


def load_allowed_users():
    """Load list of allowed users from access.conf"""
    with open("access.conf", "r") as file:
        return [line.strip() for line in file if line.strip() and not line.startswith("#")]


ALLOWED_USERS = load_allowed_users()


async def check_access(update: Update) -> bool:
    """Check if user in allowed list"""
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("🚫 Доступ запрещён.")
        return False
    return True


async def grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add user in access.conf (only for admins)"""
    admin_id = os.getenv("ADMIN_ID")  # Admin ID
    if str(update.effective_user.id) != admin_id:
        await update.message.reply_text("Недостаточно прав.")
        return

    new_user_id = context.args[0] if context.args else None
    if not new_user_id or not new_user_id.isdigit():
        await update.message.reply_text("Использование: /grant_access <ID>")
        return

    with open("access.conf", "a") as file:
        file.write(f"\n{new_user_id}")

    global ALLOWED_USERS
    ALLOWED_USERS = load_allowed_users()  # Обновляем список
    await update.message.reply_text(f"Пользователь {new_user_id} добавлен.")


# Get cameras from .env
def load_cameras():
    cameras = {}
    for key, value in os.environ.items():
        if key.startswith("CAMERA_"):
            cam_id = key.split("_")[1]
            desc, source = value.split(", ")
            cameras[cam_id] = (desc, source)
    return cameras


CAMERAS = load_cameras()
TOKEN = os.getenv("TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        return

    keyboard = get_main_keyboard()
    await update.message.reply_text("Доступ к камерам наблюдения открыт", reply_markup=keyboard)


async def show_cameras_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of cameras"""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    chat_id = update.effective_chat.id

    # Try delete old menu
    if 'last_menu_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=context.user_data['last_menu_message_id']
            )
        except:
            pass

    # Send new menu
    message = await context.bot.send_message(
        chat_id=chat_id,
        text="📷 Выберите камеру:",
        reply_markup=get_cameras_keyboard(CAMERAS)
    )

    # Save new menu ID
    context.user_data['last_menu_message_id'] = message.message_id

    if query:
        await query.answer()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📋 Список камер":
        # Delete message from Reply-button
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
        except Exception as e:
            print(f"Не удалось удалить сообщение: {e}")
        await show_cameras_menu(update, context)


async def handle_camera_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle of camera button"""

    query = update.callback_query

    camera_id = query.data.split("_")[1]
    desc, source = CAMERAS[camera_id]

    try:
        if camera_id not in CAMERAS:
            await query.answer(f"Камера {camera_id} не найдена.", show_alert=True)
            return

        # Save and send photo
        temp_file = f"camera_{camera_id}.jpg"

        # Capture photo
        await query.answer(f"🔄 Захватываю {desc}...")

        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-skip_frame", "nokey",  # Skip nokey frames
            "-i", source,
            "-frames:v", "1",  # Get just 1 frame
            "-q:v", "2",  # JPEG quality (1-31, where 2 — best)
            # "-c:v", "libx265",  # HEVC decode
            "-y",  # Rewrite file if exists
            temp_file
        ]
        try:
            subprocess.run(ffmpeg_cmd, check=True)
        except subprocess.CalledProcessError as e:
            await query.answer(f"Ошибка FFmpeg: {e}", show_alert=True)
            return

        await context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        # Send photo
        keyboard = get_refresh_keyboard(camera_id)
        with open(temp_file, "rb") as photo:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=temp_file, caption=f"📷 {desc}", reply_markup=keyboard)

        os.remove(temp_file)

    except Exception as e:
        await query.answer(f"Ошибка: {e}", show_alert=True)


async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refresh button"""
    query = update.callback_query
    user_data = context.user_data.setdefault("cameras", {})
    last_update_time = user_data.get("last_update", datetime(1970, 1, 1))

    # Just for stable working
    if datetime.now() - last_update_time < timedelta(seconds=5):
        await query.answer("Подождите 5 секунд!", show_alert=True)
        return

    await query.answer("Обновляю...")

    camera_id = query.data.split("_")[1]
    desc, source = CAMERAS[camera_id]

    # Get another one photo
    temp_file = f"camera_{camera_id}.jpg"

    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-skip_frame", "nokey",  # Skip nokey frames
        "-i", source,
        "-frames:v", "1",  # Get just 1 frame
        "-q:v", "2",  # JPEG quality (1-31, where 2 — best)
        # "-c:v", "libx265",  # HEVC decode
        "-y",  # Rewrite file if exists
        temp_file
    ]
    try:
        subprocess.run(ffmpeg_cmd, check=True)
    except subprocess.CalledProcessError as e:
        await query.answer(f"Ошибка FFmpeg: {e}", show_alert=True)
        return

    user_data["last_update"] = datetime.now()

    # Renew message
    with open(temp_file, "rb") as photo:
        await context.bot.edit_message_media(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            media=InputMediaPhoto(photo),
            reply_markup=get_refresh_keyboard(camera_id)  # Save button
        )
    time_str = datetime.now().strftime("%H:%M:%S")
    await context.bot.edit_message_caption(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        caption=f"📸 {desc} (обновлено: {time_str})",
        reply_markup=get_refresh_keyboard(camera_id)
    )


def main():
    app = Application.builder().token(TOKEN).build()

    # Registering handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_camera_selection, pattern="^camera_"))
    app.add_handler(CommandHandler("grant_access", grant_access))
    app.add_handler(CallbackQueryHandler(handle_refresh, pattern="^refresh_"))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
