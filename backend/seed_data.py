"""
Seed script to populate VyapaarSetu database with sample business data.
Run this to populate the database with realistic demo data.
"""

import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.database import engine, AsyncSessionLocal
from backend.services.ubid_service import generate_ubid_code


async def seed_database():
    """Populate database with sample business data for demo purposes."""
    async with AsyncSessionLocal() as db:
        try:
            # Check if data already exists
            result = await db.execute(text("SELECT COUNT(*) FROM raw_records"))
            count = result.scalar_one()
            if count > 0:
                print(f"Database already has {count} records. Skipping seed.")
                return

            print("Seeding database with sample business data...")

            # Sample business data
            sample_businesses = [
                {
                    "name": "Ravi Engineering Works",
                    "address": "123 Industrial Area, Bangalore 560058",
                    "pan": "AABCR1234A",
                    "gstin": "29AABCR1234A1Z5",
                    "sector": "Engineering",
                    "pincode": "560058",
                    "source_system": "gst",
                },
                {
                    "name": "Priya Electronics Pvt Ltd",
                    "address": "45 Tech Park, Bangalore 560066",
                    "pan": "AACCP5678B",
                    "gstin": "29AACCP5678B1Z2",
                    "sector": "Electronics/IT",
                    "pincode": "560066",
                    "source_system": "gst",
                },
                {
                    "name": "Suresh Pharma Industries",
                    "address": "78 Pharma City, Bangalore 560001",
                    "pan": "AAAPS9012C",
                    "gstin": "29AAAPS9012C1Z8",
                    "sector": "Chemicals & Pharma",
                    "pincode": "560001",
                    "source_system": "mca",
                },
                {
                    "name": "Kumar Manufacturing Co",
                    "address": "456 Factory Road, Bangalore 560058",
                    "pan": "AAACK3456D",
                    "gstin": "29AAACK3456D1Z9",
                    "sector": "Engineering",
                    "pincode": "560058",
                    "source_system": "mca",
                },
                {
                    "name": "Mehta IT Solutions",
                    "address": "789 Software Park, Bangalore 560066",
                    "pan": "AAAM7890E",
                    "gstin": "29AAAM7890E1Z1",
                    "sector": "Electronics/IT",
                    "pincode": "560066",
                    "source_system": "epf",
                },
                {
                    "name": "Sharma Chemical Works",
                    "address": "321 Chemical Zone, Bangalore 560001",
                    "pan": "AAAS2345F",
                    "gstin": "29AAAS2345F1Z3",
                    "sector": "Chemicals & Pharma",
                    "pincode": "560001",
                    "source_system": "epf",
                },
                {
                    "name": "Patel Auto Parts",
                    "address": "654 Auto Street, Bangalore 560058",
                    "pan": "AAAP6789G",
                    "gstin": "29AAAP6789G1Z6",
                    "sector": "Engineering",
                    "pincode": "560058",
                    "source_system": "gst",
                },
                {
                    "name": "Reddy Software Ltd",
                    "address": "987 Tech Hub, Bangalore 560066",
                    "pan": "AAAR1234H",
                    "gstin": "29AAAR1234H1Z4",
                    "sector": "Electronics/IT",
                    "pincode": "560066",
                    "source_system": "mca",
                },
                {
                    "name": "Gupta Pharma Labs",
                    "address": "147 Lab Road, Bangalore 560001",
                    "pan": "AAAG5678I",
                    "gstin": "29AAAG5678I1Z7",
                    "sector": "Chemicals & Pharma",
                    "pincode": "560001",
                    "source_system": "epf",
                },
                {
                    "name": "Ibrahim Engineering",
                    "address": "258 Industrial Estate, Bangalore 560058",
                    "pan": "AAAI9012J",
                    "gstin": "29AAAI9012J1Z2",
                    "sector": "Engineering",
                    "pincode": "560058",
                    "source_system": "gst",
                },
                {
                    "name": "Naidu Tech Services",
                    "address": "369 Digital Park, Bangalore 560066",
                    "pan": "AAAN3456K",
                    "gstin": "29AAAN3456K1Z5",
                    "sector": "Electronics/IT",
                    "pincode": "560066",
                    "source_system": "mca",
                },
                {
                    "name": "Verma Chemicals",
                    "address": "753 Chemical Park, Bangalore 560001",
                    "pan": "AAAV7890L",
                    "gstin": "29AAAV7890L1Z8",
                    "sector": "Chemicals & Pharma",
                    "pincode": "560001",
                    "source_system": "epf",
                },
                {
                    "name": "Krishna Metal Works",
                    "address": "159 Metal Street, Bangalore 560058",
                    "pan": "AAAK2345M",
                    "gstin": "29AAAK2345M1Z1",
                    "sector": "Engineering",
                    "pincode": "560058",
                    "source_system": "gst",
                },
                {
                    "name": "Lakshmi IT Consultancy",
                    "address": "357 Silicon Valley, Bangalore 560066",
                    "pan": "AAAL6789N",
                    "gstin": "29AAAL6789N1Z4",
                    "sector": "Electronics/IT",
                    "pincode": "560066",
                    "source_system": "mca",
                },
                {
                    "name": "Rao Pharma Solutions",
                    "address": "852 Medicine Hub, Bangalore 560001",
                    "pan": "AAAR9012O",
                    "gstin": "29AAAR9012O1Z7",
                    "sector": "Chemicals & Pharma",
                    "pincode": "560001",
                    "source_system": "epf",
                },
            ]

            # Insert raw records
            for i, business in enumerate(sample_businesses):
                # Create raw record
                raw_payload = json.dumps({
                    "name": business["name"],
                    "address": business["address"],
                    "pan": business["pan"],
                    "gstin": business["gstin"],
                })

                result = await db.execute(
                    text("""
                        INSERT INTO raw_records (source_system, source_record_id, raw_payload, extracted_at)
                        VALUES (:source, :record_id, :payload, :extracted)
                        RETURNING id
                    """),
                    {
                        "source": business["source_system"],
                        "record_id": f"DEMO-{i+1:04d}",
                        "payload": raw_payload,
                        "extracted": datetime.now() - timedelta(days=i*7),
                    }
                )
                raw_record_id = result.scalar_one()

                # Create normalized record
                await db.execute(
                    text("""
                        INSERT INTO normalized_records 
                        (raw_record_id, normalized_name, pincode, sector, pan, gstin, normalized_at)
                        VALUES (:raw_id, :name, :pincode, :sector, :pan, :gstin, :normalized)
                    """),
                    {
                        "raw_id": raw_record_id,
                        "name": business["name"],
                        "pincode": business["pincode"],
                        "sector": business["sector"],
                        "pan": business["pan"],
                        "gstin": business["gstin"],
                        "normalized": datetime.now() - timedelta(days=i*7 + 1),
                    }
                )

                # Create UBID
                ubid_code = generate_ubid_code()
                result = await db.execute(
                    text("""
                        INSERT INTO ubids (ubid_code, is_canonical, pan, gstin, created_at, updated_at)
                        VALUES (:ubid, 1, :pan, :gstin, :created, :updated)
                        RETURNING id
                    """),
                    {
                        "ubid": ubid_code,
                        "pan": business["pan"],
                        "gstin": business["gstin"],
                        "created": datetime.now() - timedelta(days=i*7 + 2),
                        "updated": datetime.now() - timedelta(days=i*3),
                    }
                )
                ubid_id = result.scalar_one()

                # Create record link
                await db.execute(
                    text("""
                        INSERT INTO record_links 
                        (raw_record_id, ubid_id, source_system, confidence, decision_type, linked_at)
                        VALUES (:raw_id, :ubid_id, :source, :confidence, :decision, :linked)
                    """),
                    {
                        "raw_id": raw_record_id,
                        "ubid_id": ubid_id,
                        "source": business["source_system"],
                        "confidence": 0.85 + (i % 10) / 100,  # 0.85-0.94
                        "decision": "auto_match" if i % 3 == 0 else "reviewer_approved",
                        "linked": datetime.now() - timedelta(days=i*3 + 1),
                    }
                )

                # Create UBID activity
                status = ["Active", "Active", "Active", "Dormant", "Active"][i % 5]
                await db.execute(
                    text("""
                        INSERT INTO ubid_activity (ubid_id, status, status_since)
                        VALUES (:ubid_id, :status, :since)
                    """),
                    {
                        "ubid_id": ubid_id,
                        "status": status,
                        "since": datetime.now() - timedelta(days=30 + i*5),
                    }
                )

                # Create some events
                for j, event_type in enumerate(["registration", "filing", "inspection"]):
                    if j <= i % 3:
                        await db.execute(
                            text("""
                                INSERT INTO events 
                                (ubid_id, source_system, event_type, event_date, payload, ingested_at)
                                VALUES (:ubid_id, :source, :type, :date, :payload, :ingested)
                            """),
                            {
                                "ubid_id": ubid_id,
                                "source": business["source_system"],
                                "type": event_type,
                                "date": datetime.now() - timedelta(days=i*10 + j*20),
                                "payload": json.dumps({"event_outcome": "completed"}),
                                "ingested": datetime.now() - timedelta(days=i*10 + j*20 - 1),
                            }
                        )

            # Create some pending review items
            for i in range(5):
                await db.execute(
                    text("""
                        INSERT INTO review_queue 
                        (record_a_id, record_b_id, similarity_score, status, created_at, reviewer_id, decided_at)
                        VALUES (:a, :b, :score, :status, :created, :reviewer, :decided)
                    """),
                    {
                        "a": i + 1,
                        "b": i + 2,
                        "score": 0.72 + i / 100,
                        "status": "pending" if i < 3 else "approved",
                        "created": datetime.now() - timedelta(days=i + 1),
                        "reviewer": "admin" if i >= 3 else None,
                        "decided": datetime.now() - timedelta(days=1) if i >= 3 else None,
                    }
                )

            await db.commit()
            print(f"✅ Successfully seeded database with {len(sample_businesses)} businesses!")
            print("Dashboard should now show real data.")

        except Exception as e:
            await db.rollback()
            print(f"❌ Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
