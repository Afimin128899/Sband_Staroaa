import asyncio
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from flyerapi import Flyer

load_dotenv()

# ---------- CONFIG ----------
@dataclass(frozen=True)
class Config:
    bot_token: str
    flyer_key: str
    admin_ids: set[int]
    default_task_reward: int
    ref_bonus: int
    daily_bonus: int
    min_withdraw: int
    db_path: str = "bot.db"


def _parse_admins(raw: str) -> set[int]:
    raw = (raw or "").strip()
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


CFG = Config(
    bot_token=os.environ["BOT_TOKEN"],
    flyer_key=os.environ["FLYER_KEY"],
    admin_ids=_parse_admins(os.getenv("ADMIN_IDS", "")),
    default_task_reward=int(os.getenv("DEFAULT_TASK_REWARD", "5")),
    ref_bonus=int(os.getenv("REF_BONUS", "20")),
    daily_bonus=int(os.getenv("DAILY_BONUS", "10")),
    min_withdraw=int(os.getenv("MIN_WITHDRAW", "200")),
)

flyer = Flyer(CFG.flyer_key)

# Небольшой in-memory кэш задач, чтобы достать reward/links по signature
TASK_CACHE: Dict[int, Dict[str, Dict[str, Any]]] = {}

# ---------- DB ----------
async def db_init() -> None:
    async with aiosqlite.connect(CFG.db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                referrer_id INTEGER,
                balance INTEGER NOT NULL DEFAULT 0,
                referrals_count INTEGER NOT NULL DEFAULT 0,
                last_daily TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS done_tasks (
                user_id INTEGER NOT NULL,
                signature TEXT NOT NULL,
                done_at TEXT NOT NULL,
                PRIMARY KEY (user_id, signature)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def ensure_user(user_id: int, referrer_id: Optional[int] = None) -> None:
    async with aiosqlite.connect(CFG.db_path) as db:
        cur = await db.execute("SELECT user_id, referrer_id FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users(user_id, referrer_id) VALUES(?, ?)",
                (user_id, referrer_id),
            )
            await db.commit()
        else:
            # если referrer_id уже есть — не перетираем
            pass


async def get_user(user_id: int) -> dict:
    async with aiosqlite.connect(CFG.db_path) as db:
        cur = await db.execute(
            "SELECT user_id, referrer_id, balance, referrals_count, last_daily FROM users WHERE user_id=?",
            (user_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return {"user_id": user_id, "referrer_id": None, "balance": 0, "referrals_count": 0, "last_daily": None}
        return {
            "user_id": row[0],
            "referrer_id": row[1],
            "balance": row[2],
            "referrals_count": row[3],
            "last_daily": row[4],
        }


async def add_balance(user_id: int, delta: int) -> None:
    async with aiosqlite.connect(CFG.db_path) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
        await db.commit()


async def inc_referrals(referrer_id: int) -> None:
    async with aiosqlite.connect(CFG.db_path) as db:
        await db.execute(
            "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?",
            (referrer_id,),
        )
        await db.commit()


async def mark_task_done(user_id: int, signature: str) -> bool:
    """Возвращает True если успешно отметили (т.е. раньше не было)."""
    async with aiosqlite.connect(CFG.db_path) as db:
        try:
            await db.execute(
                "INSERT INTO done_tasks(user_id, signature, done_at) VALUES(?,?,?)",
                (user_id, signature, date.today().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def create_withdraw_request(user_id: int, amount: int, details: str) -> None:
    async with aiosqlite.connect(CFG.db_path) as db:
        await db.execute(
            "INSERT INTO withdraw_requests(user_id, amount, details, created_at) VALUES(?,?,?,?)",
            (user_id, amount, details, date.today().isoformat()),
        )
        await db.commit()


# ---------- UI ----------
def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Задания", callback_data="tasks")
    kb.button(text="💰 Баланс", callback_data="balance")
    kb.button(text="👥 Рефералы", callback_data="refs")
    kb.button(text="🎁 Ежедневный бонус", callback_data="daily")
    kb.button(text="🏦 Вывод", callback_data="withdraw")
    kb.button(text="ℹ️ Правила", callback_data="rules")
    kb.adjust(2, 2, 2)
    return kb.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")]])


def tasks_kb(tasks: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tasks:
        sig = str(t.get("signature", ""))
        title = (t.get("title") or t.get("name") or t.get("text") or "Задание").strip()
        title = title.replace("\n", " ")
        kb.button(text=title[:50], callback_data=f"t:{sig}")
    kb.button(text="⬅️ Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def task_actions_kb(signature: str, url: Optional[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if url:
        kb.add(InlineKeyboardButton(text="🔗 Открыть задание", url=url))
    kb.button(text="✅ Проверить", callback_data=f"c:{signature}")
    kb.button(text="⬅️ К заданиям", callback_data="tasks")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Flyer helpers ----------
async def flyer_gate(user_id: int, language_code: str) -> bool:
    """
    Проверка обязательной подписки/ограничений Flyer.
    По примерам flyerapi: если check() вернул False — просто выходим из хендлера.
    """
    try:
        ok = await flyer.check(user_id, language_code=language_code)
        return bool(ok)
    except Exception:
        # На проде лучше логировать. Здесь — не блокируем пользователя при временном сбое.
        return True


def normalize_task_url(task: dict) -> Optional[str]:
    # Flyer может отдавать разные поля; пробуем самые типичные.
    for key in ("url", "link", "target_url", "invite_link"):
        v = task.get(key)
        if isinstance(v, str) and v.startswith(("http://", "https://", "tg://", "t.me/")):
            return v
    return None


def is_done(status: Any) -> bool:
    if isinstance(status, bool):
        return status
    if isinstance(status, int):
        return status == 1
    if isinstance(status, str):
        return status.strip().lower() in {"ok", "done", "success", "completed", "true", "1"}
    if isinstance(status, dict):
        v = status.get("status") or status.get("result") or status.get("done")
        return is_done(v)
    return False


def task_reward(task: dict) -> int:
    for key in ("reward", "price", "payout"):
        v = task.get(key)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return CFG.default_task_reward


# ---------- BOT ----------
router = Router()


@router.message(CommandStart())
async def start(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    lang = message.from_user.language_code or "ru"

    # gate
    if not await flyer_gate(user_id, lang):
        return

    # parse ref
    referrer_id: Optional[int] = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].isdigit():
            ref = int(parts[1])
            if ref != user_id:
                referrer_id = ref

    # create user
    await ensure_user(user_id, referrer_id=referrer_id)

    # if new user with valid referrer — начислим бонус рефереру (1 раз)
    user = await get_user(user_id)
    if user.get("referrer_id") and user.get("balance") == 0 and user.get("referrals_count") == 0:
        # Это простой эвристический критерий "первый запуск".
        # На проде лучше хранить отдельный флаг "is_new".
        await ensure_user(user["referrer_id"])
        await add_balance(user["referrer_id"], CFG.ref_bonus)
        await inc_referrals(user["referrer_id"])

    me = await bot.get_me()
    await message.answer(
        f"Привет! Я бот с заданиями и бонусами.\n\n"
        f"• Выполняй задания — получай баллы\n"
        f"• Приглашай друзей — бонус за рефералов\n\n"
        f"Твоя реф-ссылка:\nhttps://t.me/{me.username}?start={user_id}",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "menu")
async def menu(call: CallbackQuery) -> None:
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()


@router.callback_query(F.data == "rules")
async def rules(call: CallbackQuery) -> None:
    txt = (
        "Правила:\n"
        "1) Баллы начисляются только за подтверждённые задания.\n"
        "2) За одно задание — один раз.\n"
        "3) Вывод — через заявку (проверка вручную админом).\n\n"
        "Важно: мы не обещаем «бесплатные Telegram Stars». Здесь внутренняя система баллов."
    )
    await call.message.edit_text(txt, reply_markup=back_menu())
    await call.answer()


@router.callback_query(F.data == "balance")
async def balance(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    u = await get_user(user_id)
    await call.message.edit_text(
        f"💰 Баланс: {u['balance']} баллов\n👥 Рефералов: {u['referrals_count']}",
        reply_markup=back_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "refs")
async def refs(call: CallbackQuery, bot: Bot) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    me = await bot.get_me()
    u = await get_user(user_id)
    await call.message.edit_text(
        f"👥 Рефералы\n\n"
        f"Твоя ссылка:\nhttps://t.me/{me.username}?start={user_id}\n\n"
        f"Приглашено: {u['referrals_count']}\n"
        f"Бонус за реферала: +{CFG.ref_bonus} баллов (начисляется пригласившему).",
        reply_markup=back_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "daily")
async def daily(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    u = await get_user(user_id)
    today = date.today().isoformat()
    if u["last_daily"] == today:
        await call.answer("Сегодня бонус уже получен ✅", show_alert=True)
        return

    async with aiosqlite.connect(CFG.db_path) as db:
        await db.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
        await db.commit()

    await add_balance(user_id, CFG.daily_bonus)
    await call.answer(f"+{CFG.daily_bonus} баллов 🎁", show_alert=True)


@router.callback_query(F.data == "tasks")
async def tasks(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    try:
        tasks_list = await flyer.get_tasks(user_id=user_id, language_code=lang, limit=5)
    except Exception:
        tasks_list = []

    # cache
    TASK_CACHE[user_id] = {}
    for t in tasks_list or []:
        sig = str(t.get("signature", ""))
        if sig:
            TASK_CACHE[user_id][sig] = t

    if not tasks_list:
        await call.message.edit_text("Сейчас нет доступных заданий. Попробуй позже.", reply_markup=back_menu())
        await call.answer()
        return

    await call.message.edit_text("🎁 Доступные задания:", reply_markup=tasks_kb(tasks_list))
    await call.answer()


@router.callback_query(F.data.startswith("t:"))
async def open_task(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    sig = call.data.split(":", 1)[1]
    task = TASK_CACHE.get(user_id, {}).get(sig, {})
    title = (task.get("title") or task.get("name") or "Задание").strip()
    url = normalize_task_url(task)
    reward = task_reward(task)

    await call.message.edit_text(
        f"🧩 {title}\n"
        f"Награда: +{reward} баллов\n\n"
        f"1) Открой задание и выполни условия\n"
        f"2) Вернись и нажми «Проверить»",
        reply_markup=task_actions_kb(sig, url),
    )
    await call.answer()


@router.callback_query(F.data.startswith("c:"))
async def check_task(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    sig = call.data.split(":", 1)[1]

    try:
        status = await flyer.check_task(user_id=user_id, signature=sig)
    except Exception:
        await call.answer("Ошибка проверки. Попробуй ещё раз позже.", show_alert=True)
        return

    if not is_done(status):
        await call.answer("Пока не засчитано ⏳ (попробуй через минуту)", show_alert=True)
        return

    # защита от повторного начисления
    first_time = await mark_task_done(user_id, sig)
    if not first_time:
        await call.answer("Это задание уже засчитано ранее ✅", show_alert=True)
        return

    task = TASK_CACHE.get(user_id, {}).get(sig, {})
    reward = task_reward(task)
    await add_balance(user_id, reward)
    await call.answer(f"Задание засчитано! +{reward} баллов ✅", show_alert=True)


@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    lang = call.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        await call.answer()
        return

    u = await get_user(user_id)
    await call.message.edit_text(
        f"🏦 Вывод\n\n"
        f"Баланс: {u['balance']} баллов\n"
        f"Минимум: {CFG.min_withdraw}\n\n"
        f"Чтобы создать заявку, отправь команду:\n"
        f"/withdraw <сумма> <реквизиты/комментарий>\n"
        f"Пример:\n/withdraw 500 @username",
        reply_markup=back_menu(),
    )
    await call.answer()


@router.message(Command("withdraw"))
async def withdraw_cmd(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    lang = message.from_user.language_code or "ru"
    if not await flyer_gate(user_id, lang):
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Формат: /withdraw <сумма> <реквизиты/комментарий>")
        return

    amount = int(parts[1])
    details = parts[2].strip()

    u = await get_user(user_id)
    if amount < CFG.min_withdraw:
        await message.answer(f"Минимальная сумма вывода: {CFG.min_withdraw}")
        return
    if u["balance"] < amount:
        await message.answer("Недостаточно баллов на балансе.")
        return

    # списываем сразу (так проще от дублей), админ потом одобрит/вернёт при отказе
    await add_balance(user_id, -amount)
    await create_withdraw_request(user_id, amount, details)

    await message.answer("✅ Заявка создана. Ожидай обработки админом.")

    # уведомим админов
    if CFG.admin_ids:
        text = f"🆕 Заявка на вывод\nuser_id={user_id}\namount={amount}\ndetails={details}"
        for aid in CFG.admin_ids:
            try:
                await bot.send_message(aid, text)
            except Exception:
                pass


@router.message(Command("admin"))
async def admin_help(message: Message) -> None:
    if message.from_user.id not in CFG.admin_ids:
        return
    await message.answer(
        "Админ-команды:\n"
        "/pending — список ожидающих заявок\n"
        "/approve <id> — одобрить\n"
        "/reject <id> <причина> — отклонить (вернёт баллы)\n"
    )


@router.message(Command("pending"))
async def admin_pending(message: Message) -> None:
    if message.from_user.id not in CFG.admin_ids:
        return

    async with aiosqlite.connect(CFG.db_path) as db:
        cur = await db.execute(
            "SELECT id, user_id, amount, details, created_at FROM withdraw_requests WHERE status='pending' ORDER BY id DESC LIMIT 20"
        )
        rows = await cur.fetchall()

    if not rows:
        await message.answer("Пусто.")
        return

    lines = ["⏳ Pending заявки:"]
    for r in rows:
        lines.append(f"#{r[0]} user={r[1]} amount={r[2]} details={r[3]} date={r[4]}")
    await message.answer("\n".join(lines))


@router.message(Command("approve"))
async def admin_approve(message: Message, bot: Bot) -> None:
    if message.from_user.id not in CFG.admin_ids:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /approve <id>")
        return
    req_id = int(parts[1])

    async with aiosqlite.connect(CFG.db_path) as db:
        cur = await db.execute(
            "SELECT user_id, amount, status FROM withdraw_requests WHERE id=?",
            (req_id,),
        )
        row = await cur.fetchone()
        if not row:
            await message.answer("Не найдено.")
            return
        if row[2] != "pending":
            await message.answer(f"Уже обработано: {row[2]}")
            return

        await db.execute("UPDATE withdraw_requests SET status='approved' WHERE id=?", (req_id,))
        await db.commit()

    await message.answer(f"✅ Одобрено #{req_id}")
    try:
        await bot.send_message(row[0], f"✅ Ваша заявка #{req_id} одобрена. Сумма: {row[1]}")
    except Exception:
        pass


@router.message(Command("reject"))
async def admin_reject(message: Message, bot: Bot) -> None:
    if message.from_user.id not in CFG.admin_ids:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Формат: /reject <id> <причина>")
        return
    req_id = int(parts[1])
    reason = parts[2] if len(parts) == 3 else "без причины"

    async with aiosqlite.connect(CFG.db_path) as db:
        cur = await db.execute(
            "SELECT user_id, amount, status FROM withdraw_requests WHERE id=?",
            (req_id,),
        )
        row = await cur.fetchone()
        if not row:
            await message.answer("Не найдено.")
            return
        if row[2] != "pending":
            await message.answer(f"Уже обработано: {row[2]}")
            return

        await db.execute("UPDATE withdraw_requests SET status='rejected' WHERE id=?", (req_id,))