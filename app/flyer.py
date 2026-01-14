import aiohttp
from app.config import FLYER_API_URL, FLYER_API_KEY

async def check_task(user_id: int, task_id: int) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            FLYER_API_URL,
            json={"telegram_id": user_id, "task_id": task_id},
            headers={"Authorization": f"Bearer {FLYER_API_KEY}"},
            timeout=10
        ) as r:
            data = await r.json()
            return data.get("completed", False)
