"""
Seed script to populate VyapaarSetu database with sample business data.
Run this to populate the database with realistic demo data.
"""

import asyncio
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.database import engine, AsyncSessionLocal, Base
from backend.services.ubid_service import generate_ubid_code


async def init_db():
    """Create all database tables if they don't exist."""
    try:
        # Import models to register them with Base
        from backend import models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"⚠️ Database init warning (tables may already exist): {e}")


async def seed_database():
    """Populate database with sample business data for demo purposes."""
    # First ensure tables exist
    await init_db()
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if data already exists
            result = await db.execute(text("SELECT COUNT(*) FROM raw_records"))
            count = result.scalar_one()
            if count > 0:
                print(f"Database already has {count} records. Skipping seed.")
                return

            print("Seeding database with sample business data...")

            # Generate 1000+ sample businesses programmatically
            import random
            
            first_names = ["Ravi", "Priya", "Suresh", "Kumar", "Mehta", "Sharma", "Patel", "Reddy", "Gupta", 
                          "Ibrahim", "Naidu", "Verma", "Krishna", "Lakshmi", "Rao", "Singh", "Kaur", "Das", 
                          "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Roy", "Sen", "Bose", "Acharya",
                          "Malhotra", "Kapoor", "Khanna", "Agarwal", "Goel", "Jain", "Bhatia", "Chopra",
                          "Rajan", "Venkat", "Subramanian", "Iyer", "Menon", "Nair", "Pillai", "Rao",
                          "Joshi", "Deshmukh", "Patil", "Kulkarni", "Gowda", "Reddy", "Naik", "Prasad"]
            
            business_suffixes = ["Engineering Works", "Electronics Pvt Ltd", "Industries", "Manufacturing Co", 
                                "IT Solutions", "Chemical Works", "Auto Parts", "Software Ltd", "Pharma Labs",
                                "Tech Services", "Metal Works", "Consultancy", "Trading Co", "Enterprises",
                                "Systems Ltd", "Components", "Digital Solutions", "Process Industries", "Corp"]
            
            sectors = ["Engineering", "Electronics/IT", "Chemicals & Pharma", "Textiles", "Food Processing",
                      "Automotive", "Construction", "Renewable Energy"]
            
            pincodes = ["560001", "560002", "560003", "560010", "560020", "560025", "560038", "560040",
                       "560050", "560058", "560060", "560066", "560070", "560076", "560080", "560090",
                       "560100", "560102", "560103", "560107", "560300", "560500", "560600", "560800"]
            
            sources = ["gst", "mca", "epf", "esic", "customs", "state_tax"]
            
            areas = ["Industrial Area", "Tech Park", "Pharma City", "Factory Road", "Software Park",
                    "Chemical Zone", "Auto Street", "Tech Hub", "Lab Road", "Industrial Estate",
                    "Digital Park", "Chemical Park", "Metal Street", "Silicon Valley", "Medicine Hub",
                    "Business District", "Commercial Complex", "SEZ", "Export Zone", "Manufacturing Hub"]
            
            cities = ["Bangalore", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Ahmedabad", "Kolkata"]
            
            def generate_business(i):
                first = first_names[i % len(first_names)]
                suffix = business_suffixes[i % len(business_suffixes)]
                name = f"{first} {suffix}" if random.random() > 0.3 else f"{first} & Co {suffix}"
                
                area = areas[i % len(areas)]
                city = cities[i % len(cities)]
                pincode = pincodes[i % len(pincodes)]
                address = f"{i+1} {area}, {city} {pincode}"
                
                # Generate PAN: 5 letters + 4 digits + 1 letter
                pan_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                pan = f"{pan_letters[i % 26]}{pan_letters[(i+1) % 26]}{pan_letters[(i+2) % 26]}{pan_letters[(i+3) % 26]}{pan_letters[(i+4) % 26]}{(i+1000):04d}{pan_letters[(i+5) % 26]}"
                
                # Generate GSTIN: 2 digit state + PAN + 3 digits + Z + check
                state_code = f"{(i % 37):02d}"
                gstin = f"{state_code}{pan}1Z5"
                
                return {
                    "name": name,
                    "address": address,
                    "pan": pan[:10],  # PAN is 10 chars
                    "gstin": gstin[:15],  # GSTIN is 15 chars
                    "sector": sectors[i % len(sectors)],
                    "pincode": pincode,
                    "source_system": sources[i % len(sources)],
                }
            
            TOTAL_RECORDS = 1200  # Generate 1200 businesses
            sample_businesses = [generate_business(i) for i in range(TOTAL_RECORDS)]
            normalized_ids = []

            # Insert raw records
            for i, business in enumerate(sample_businesses):
                # Create raw record
                raw_payload = json.dumps({
                    "name": business["name"],
                    "address": business["address"],
                    "pan": business["pan"],
                    "gstin": business["gstin"],
                })

                # Generate UUID and checksum for raw record
                raw_record_id = str(uuid.uuid4())
                checksum = hashlib.md5(raw_payload.encode()).hexdigest()
                
                await db.execute(
                    text("""
                        INSERT INTO raw_records (id, source_system, source_record_id, raw_payload, extracted_at, checksum)
                        VALUES (:id, :source, :record_id, :payload, :extracted, :checksum)
                    """),
                    {
                        "id": raw_record_id,
                        "source": business["source_system"],
                        "record_id": f"DEMO-{i+1:04d}",
                        "payload": raw_payload,
                        "extracted": datetime.now() - timedelta(days=i*7),
                        "checksum": checksum,
                    }
                )

                # Create normalized record
                normalized_id = str(uuid.uuid4())
                normalized_ids.append(normalized_id)
                await db.execute(
                    text("""
                        INSERT INTO normalized_records 
                        (id, raw_record_id, normalized_name, pincode, sector, pan, gstin, normalized_at)
                        VALUES (:id, :raw_id, :name, :pincode, :sector, :pan, :gstin, :normalized)
                    """),
                    {
                        "id": normalized_id,
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
                ubid_id = str(uuid.uuid4())
                ubid_code = generate_ubid_code(i + 1000)  # Pass sequential number
                await db.execute(
                    text("""
                        INSERT INTO ubids (id, ubid_code, is_canonical, pan, gstin, created_at, updated_at)
                        VALUES (:id, :ubid, 1, :pan, :gstin, :created, :updated)
                    """),
                    {
                        "id": ubid_id,
                        "ubid": ubid_code,
                        "pan": business["pan"],
                        "gstin": business["gstin"],
                        "created": datetime.now() - timedelta(days=i*7 + 2),
                        "updated": datetime.now() - timedelta(days=i*3),
                    }
                )

                # Create record link
                link_id = str(uuid.uuid4())
                source_record_id = f"DEMO-{i+1:04d}"
                await db.execute(
                    text("""
                        INSERT INTO record_links 
                        (id, raw_record_id, ubid_id, source_system, source_record_id, confidence, decision_type, linked_at)
                        VALUES (:id, :raw_id, :ubid_id, :source, :source_record_id, :confidence, :decision, :linked)
                    """),
                    {
                        "id": link_id,
                        "raw_id": raw_record_id,
                        "ubid_id": ubid_id,
                        "source": business["source_system"],
                        "source_record_id": source_record_id,
                        "confidence": 0.85 + (i % 10) / 100,  # 0.85-0.94
                        "decision": "auto_match" if i % 3 == 0 else "reviewer_approved",
                        "linked": datetime.now() - timedelta(days=i*3 + 1),
                    }
                )

                # Create UBID activity
                status = ["Active", "Active", "Active", "Dormant", "Active"][i % 5]
                activity_score = 0.82 if status == "Active" else 0.34
                await db.execute(
                    text("""
                        INSERT INTO ubid_activity
                        (ubid_id, status, score, evidence_timeline, computed_at)
                        VALUES (:ubid_id, :status, :score, :evidence, :computed_at)
                    """),
                    {
                        "ubid_id": ubid_id,
                        "status": status,
                        "score": activity_score,
                        "evidence": json.dumps([
                            {
                                "event": "demo_activity_baseline",
                                "status": status,
                                "observed_at": (datetime.now() - timedelta(days=30 + i*5)).isoformat(),
                            }
                        ]),
                        "computed_at": datetime.now() - timedelta(days=30 + i*5),
                    }
                )

                # Create some events
                for j, event_type in enumerate(["registration", "filing", "inspection"]):
                    if j <= i % 3:
                        event_id = str(uuid.uuid4())
                        await db.execute(
                            text("""
                                INSERT INTO events 
                                (id, source_system, source_record_id, ubid_id, event_type, event_date, payload, ingested_at)
                                VALUES (:id, :source, :record_id, :ubid_id, :type, :date, :payload, :ingested)
                            """),
                            {
                                "id": event_id,
                                "source": business["source_system"],
                                "record_id": f"DEMO-{i+1:04d}-EVT{j}",
                                "ubid_id": ubid_id,
                                "type": event_type,
                                "date": datetime.now() - timedelta(days=i*10 + j*20),
                                "payload": json.dumps({"event_outcome": "completed"}),
                                "ingested": datetime.now() - timedelta(days=i*10 + j*20 - 1),
                            }
                        )

            # Create pending review items (more realistic distribution)
            review_count = min(200, TOTAL_RECORDS // 6)  # ~200 review items
            for i in range(review_count):
                # Vary the status distribution: 60% approved, 20% pending, 20% rejected
                rand = i % 10
                if rand < 6:
                    status = "approved"
                    reviewer = f"reviewer_{i % 5 + 1}"
                    decided = datetime.now() - timedelta(days=i % 30 + 1)
                elif rand < 8:
                    status = "pending"
                    reviewer = None
                    decided = None
                else:
                    status = "rejected"
                    reviewer = f"reviewer_{i % 5 + 1}"
                    decided = datetime.now() - timedelta(days=i % 30 + 1)
                
                queue_id = str(uuid.uuid4())
                pair_id = str(uuid.uuid4())
                scored_pair_id = str(uuid.uuid4())
                record_a_id = normalized_ids[(i * 2) % TOTAL_RECORDS]
                record_b_id = normalized_ids[(i * 2 + 1) % TOTAL_RECORDS]
                queue_status = "resolved" if status in ("approved", "rejected") else "pending"

                await db.execute(
                    text("""
                        INSERT INTO candidate_pairs
                        (id, record_a_id, record_b_id, blocking_strategy, created_at)
                        VALUES (:id, :record_a_id, :record_b_id, :blocking_strategy, :created_at)
                    """),
                    {
                        "id": pair_id,
                        "record_a_id": record_a_id,
                        "record_b_id": record_b_id,
                        "blocking_strategy": "demo_seed",
                        "created_at": datetime.now() - timedelta(days=i % 60 + 1),
                    }
                )

                await db.execute(
                    text("""
                        INSERT INTO scored_pairs
                        (id, pair_id, record_a_id, record_b_id, feature_vector, confidence_score, evidence_object, weight_version, scored_at)
                        VALUES (:id, :pair_id, :record_a_id, :record_b_id, :feature_vector, :confidence_score, :evidence_object, :weight_version, :scored_at)
                    """),
                    {
                        "id": scored_pair_id,
                        "pair_id": pair_id,
                        "record_a_id": record_a_id,
                        "record_b_id": record_b_id,
                        "feature_vector": json.dumps({"name_similarity": 0.72, "address_similarity": 0.68}),
                        "confidence_score": 0.55 + (i % 40) / 100,
                        "evidence_object": json.dumps({"reason": "Demo seeded review candidate"}),
                        "weight_version": "demo-v1",
                        "scored_at": datetime.now() - timedelta(days=i % 60 + 1),
                    }
                )

                await db.execute(
                    text("""
                        INSERT INTO review_queue 
                        (id, pair_id, scored_pair_id, confidence_score, priority, status, reviewer_notes, queued_at, resolved_at)
                        VALUES (:id, :pair_id, :scored_pair_id, :confidence_score, :priority, :status, :reviewer_notes, :queued_at, :resolved_at)
                    """),
                    {
                        "id": queue_id,
                        "pair_id": pair_id,
                        "scored_pair_id": scored_pair_id,
                        "confidence_score": 0.55 + (i % 40) / 100,  # Scores from 0.55 to 0.95
                        "priority": 1 + (i % 5),
                        "status": queue_status,
                        "reviewer_notes": f"Demo review status: {status}" if reviewer else None,
                        "queued_at": datetime.now() - timedelta(days=i % 60 + 1),
                        "resolved_at": decided,
                    }
                )

            await db.commit()
            print(f"✅ Successfully seeded database with {len(sample_businesses)} businesses!")
            print(f"   - {TOTAL_RECORDS} raw records")
            print(f"   - {TOTAL_RECORDS} UBIDs")
            print(f"   - Multiple sectors: {', '.join(set(b['sector'] for b in sample_businesses[:50]))}")
            print(f"   - Multiple pincodes: {len(set(b['pincode'] for b in sample_businesses))} unique locations")
            print("Dashboard should now show rich demo data!")

        except Exception as e:
            await db.rollback()
            print(f"❌ Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
