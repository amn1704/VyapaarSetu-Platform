import asyncio
import sys
import os

sys.path.append(os.getcwd())

from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models import ReviewQueue

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ReviewQueue.id, ReviewQueue.status))
        for row in res.all():
            print(f"ID: {row.id}, Status: {row.status}")

if __name__ == "__main__":
    asyncio.run(main())
