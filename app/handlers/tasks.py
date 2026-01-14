from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.services.tasks import get_tasks, is_completed, mark_completed
from app.flyer import check_task
from app.services.rewards import add_reward

router = Router()

@router.callback_query(F.data == "tasks")
async def tasks(call: CallbackQuery):
    tasks = await get_tasks()
    for t in tasks:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Проверить",
                callback_data=f"check:{t.id}"
            )]
        ])
        await call.message.answer(
            f"{t.title}\nНаграда: 0.25 ⭐",
            reply_markup=kb
        )

@router.callback_query(F.data.startswith("check:"))
async def check(call: CallbackQuery):
    task_id = int(call.data.split(":")[1])

    if await is_completed(call.from_user.id, task_id):
        await call.answer("⛔ Уже выполнено", show_alert=True)
        return

    if await check_task(call.from_user.id, task_id):
        await mark_completed(call.from_user.id, task_id)
        await add_reward(call.from_user.id, 1)
        await call.message.answer("✅ Выполнено")
    else:
        await call.answer("❌ Не выполнено", show_alert=True)

