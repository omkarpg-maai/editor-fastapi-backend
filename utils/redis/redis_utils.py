import aioredis
import json

class RedisManager:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
    
    async def get(self, key: str):
        return await self.redis.get(key)

    async def set(self, key: str, value: str, expiration: int):
        await self.redis.set(key, value, ex=expiration)

    async def delete(self, key: str):
        await self.redis.delete(key)

    async def get_json(self, key: str):
        data = await self.get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value: dict, expiration: int):
        await self.set(key, json.dumps(value), expiration)
