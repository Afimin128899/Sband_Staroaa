
from aiogram import Dispatcher
from app.handlers.start import router as start_router
from app.handlers.balance import router as balance_router
from app.handlers.tasks import router as tasks_router
from app.handlers.withdraw import router as withdraw_router
from app.handlers.admin import router as admin_router

dp = Dispatcher()
dp.include_router(start_router)
dp.include_router(balance_router)
dp.include_router(tasks_router)
dp.include_router(withdraw_router)
dp.include_router(admin_router)
