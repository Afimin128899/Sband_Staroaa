from app.services.rewards import add_reward, REFERRAL_REWARD

async def reward_referrer(referrer_id: int):
    await add_reward(referrer_id, REFERRAL_REWARD, "referral")

