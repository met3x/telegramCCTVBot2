import cv2
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TOKEN')

cameras = {}
for key, value in os.environ.items():
    if key.startswith('CAMERA_'):
        cam_id = key.split('_')[1]
        cameras[cam_id] = value.split(', ')


def get_image(update: Update, context: CallbackContext) -> None:
    try:
        camera_number = int(context.args[0]) if context.args else 0

        if str(camera_number) not in cameras['cameras']:
            update.message.reply_text(f"Камера {camera_number} не найдена в конфигурации.")
            return

        camera_desc, camera_source = cameras['cameras'][str(camera_number)].split(', ')

        if camera_source.isdigit():
            cap = cv2.VideoCapture(int(camera_source))
        else:
            cap = cv2.VideoCapture(camera_source)

        if not cap.isOpened():
            update.message.reply_text(f"Ошибка: Не удалось подключиться к камере {camera_number} ({camera_desc}).")
            return

        ret, frame = cap.read()
        cap.release()

        if not ret:
            update.message.reply_text("Ошибка: Не удалось получить изображение.")
            return

        temp_file = f"camera_{camera_number}.jpg"
        cv2.imwrite(temp_file, frame)

        with open(temp_file, 'rb') as photo:
            update.message.reply_photo(photo, caption=f"Камера: {camera_desc}")

        os.remove(temp_file)

    except (IndexError, ValueError):
        update.message.reply_text("Использование: /get_image <номер_камеры>")
    except Exception as e:
        update.message.reply_text(f"Ошибка: {str(e)}")


def main():
    updater = Updater(TOKEN)
    updater.dispatcher.add_handler(CommandHandler("get_image", get_image))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()