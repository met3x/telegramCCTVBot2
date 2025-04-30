from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def get_main_keyboard():
    """Keyboard with menu button"""
    return ReplyKeyboardMarkup(
        [["📋 Список камер"]],  # One button in one row
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_cameras_keyboard(cameras):
    """Keyboard with camera buttons"""
    buttons = [
        [InlineKeyboardButton(desc, callback_data=f"camera_{id}")] for id, (desc, _) in cameras.items()
    ]
    return InlineKeyboardMarkup(buttons)


def get_refresh_keyboard(camera_id):
    """Keyboard with refresh button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{camera_id}")]
    ])
