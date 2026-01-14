from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🎯 Задания", callback_data="tasks")],
        [InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw")]
    ])
