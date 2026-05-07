import asyncio
import sys
import os
import uuid


sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import AsyncSessionLocal
from backend.models import ReviewQueue, CandidatePair, ScoredPair

async def main():
    async with AsyncSessionLocal() as db:
        # Just grab any candidate pair
        from sqlalchemy import select
        res = await db.execute(select(CandidatePair).limit(1))
        pair = res.scalar()
        
        # Grab any scored pair
        res = await db.execute(select(ScoredPair).limit(1))
        scored = res.scalar()
        
        # Create a new ReviewQueue item
        item_id = uuid.uuid4()
        queue_item = ReviewQueue(
            id=item_id,
            pair_id=pair.id,
            scored_pair_id=scored.id,
            confidence_score=0.99,
            status="pending"
        )
        db.add(queue_item)
        await db.commit()
        print(f"Created pending item: {item_id}")
        
        return str(item_id)

if __name__ == "__main__":
    item_id = asyncio.run(main())
    
    # Now simulate the frontend request
    import urllib.request
    import json
    
    url = 'http://127.0.0.1:8000/api/review-queue/action'
    data = {
        "queue_item_id": item_id,
        "decision": "confirm_match",
        "reviewer_id": "admin",
        "justification": ""
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            print("Response:", response.read().decode('utf-8'))
    except Exception as e:
        print("Error:", e)
