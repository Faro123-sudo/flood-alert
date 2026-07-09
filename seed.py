import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import Community, Base
from app.db.database import engine

COMMUNITIES = [
    {"name": "Lokoja", "lat": 7.803, "lon": 6.739, "bank_height_m": 8.0, "rain_to_rise_ratio": 0.015},
    {"name": "Makurdi", "lat": 7.732, "lon": 8.539, "bank_height_m": 6.5, "rain_to_rise_ratio": 0.018},
    {"name": "Patigi", "lat": 8.737, "lon": 5.759, "bank_height_m": 4.0, "rain_to_rise_ratio": 0.025},
    {"name": "Idah", "lat": 7.113, "lon": 6.738, "bank_height_m": 7.0, "rain_to_rise_ratio": 0.012},
    {"name": "Shagamu", "lat": 6.843, "lon": 3.646, "bank_height_m": 3.5, "rain_to_rise_ratio": 0.03},
    {"name": "Abeokuta", "lat": 7.151, "lon": 3.354, "bank_height_m": 4.0, "rain_to_rise_ratio": 0.02},
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for c in COMMUNITIES:
            session.add(Community(**c))
        await session.commit()
        print(f"Seeded {len(COMMUNITIES)} communities")


asyncio.run(seed())
