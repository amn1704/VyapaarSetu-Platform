import asyncio
import uuid
import random
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import AsyncSessionLocal, engine, Base
from backend.models import (
    RawRecord, NormalizedRecord, UBID, UBIDActivity, RecordLink, 
    CandidatePair, ScoredPair, ReviewQueue
)
from backend.services.normalization import normalize_record, compute_checksum
from backend.services.ubid_service import generate_ubid_code

BUSINESS_NAMES = [
    "Engineering", "Solutions", "Industries", "Chemicals", "Electronics", 
    "Systems", "Precision", "Global", "Enterprises", "Logistics", "Manufacturing",
    "Automation", "Tools", "Components", "Fab", "Plastics", "Metal", "Power"
]
PREFIXES = ["Sri", "New", "Royal", "Balaji", "Global", "Karnataka", "Modern", "Classic", "Apex", "Zenith", "National"]
DEPARTMENTS = ["municipal", "tax", "water", "electricity", "labor", "pollution"]

def generate_business_name():
    return f"{random.choice(PREFIXES)} {random.choice(BUSINESS_NAMES)} {random.choice(['Works', 'Ltd', 'Pvt Ltd', 'Corp', 'Services'])}"

def generate_pan():
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5)) + \
           "".join(random.choices("0123456789", k=4)) + \
           random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

def get_sector(name):
    name = name.upper()
    if any(k in name for k in ["ENGINEERING", "TOOLS", "WORKS", "METAL"]): return "Engineering"
    if any(k in name for k in ["CHEMICALS", "PLASTICS"]): return "Chemicals & Pharma"
    if any(k in name for k in ["ELECTRONICS", "AUTOMATION", "SYSTEMS"]): return "Electronics/IT"
    if any(k in name for k in ["LOGISTICS", "SERVICES", "SOLUTIONS"]): return "Services"
    return "Others"

KARNATAKA_HUBS = [
    {"name": "Peenya (Bengaluru)", "pincode": "560058", "lat": 13.0329, "lon": 77.5273, "spread": 0.05},
    {"name": "Bengaluru (Central)", "pincode": "560001", "lat": 12.9716, "lon": 77.5946, "spread": 0.35},
    {"name": "Mysuru", "pincode": "570001", "lat": 12.2958, "lon": 76.6394, "spread": 0.25},
    {"name": "Hubballi-Dharwad", "pincode": "580001", "lat": 15.3647, "lon": 75.1240, "spread": 0.25},
    {"name": "Mangaluru", "pincode": "575001", "lat": 12.9141, "lon": 74.8560, "spread": 0.20},
    {"name": "Belagavi", "pincode": "590001", "lat": 15.8497, "lon": 74.4977, "spread": 0.25},
    {"name": "Kalaburagi", "pincode": "585101", "lat": 17.3297, "lon": 76.8343, "spread": 0.25},
    {"name": "Ballari", "pincode": "583101", "lat": 15.1394, "lon": 76.9214, "spread": 0.25},
    {"name": "Vijayapura", "pincode": "586101", "lat": 16.8302, "lon": 75.7100, "spread": 0.25},
    {"name": "Shivamogga", "pincode": "577201", "lat": 13.9299, "lon": 75.5681, "spread": 0.25},
    {"name": "Tumakuru", "pincode": "572101", "lat": 13.3392, "lon": 77.1016, "spread": 0.25},
    {"name": "Raichur", "pincode": "584101", "lat": 16.2076, "lon": 77.3616, "spread": 0.25},
    {"name": "Bidar", "pincode": "585401", "lat": 17.9104, "lon": 77.5199, "spread": 0.20},
    {"name": "Davanagere", "pincode": "577001", "lat": 14.4644, "lon": 75.9218, "spread": 0.25},
    {"name": "Udupi", "pincode": "576101", "lat": 13.3409, "lon": 74.7421, "spread": 0.15},
    {"name": "Hassan", "pincode": "573201", "lat": 13.0015, "lon": 76.1023, "spread": 0.25},
    {"name": "Chitradurga", "pincode": "577501", "lat": 14.2251, "lon": 76.4010, "spread": 0.25},
    {"name": "Kolar", "pincode": "563101", "lat": 13.1367, "lon": 78.1292, "spread": 0.25},
    {"name": "Mandya", "pincode": "571401", "lat": 12.5218, "lon": 76.8951, "spread": 0.20},
    {"name": "Chikkamagaluru", "pincode": "577101", "lat": 13.3153, "lon": 75.7754, "spread": 0.25},
    {"name": "Bagalkot", "pincode": "587101", "lat": 16.1817, "lon": 75.6958, "spread": 0.25},
    {"name": "Karwar", "pincode": "581301", "lat": 14.8185, "lon": 74.1416, "spread": 0.15},
    {"name": "Madikeri", "pincode": "571201", "lat": 12.4244, "lon": 75.7382, "spread": 0.15},
    {"name": "Chamarajanagar", "pincode": "571313", "lat": 11.9261, "lon": 76.9400, "spread": 0.20}
]

async def seed_mass_data(count=1000):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        print(f"--- Starting Mass Seed: {count} Businesses ---")
        
        for i in range(count):
            base_name = generate_business_name()
            pan = generate_pan()
            pincode = "560058" # Peenya
            
            # Create UBID
            ubid_code = generate_ubid_code(i + 1)
            ubid = UBID(ubid_code=ubid_code, pan=pan)
            db.add(ubid)
            await db.flush()
            
            status = random.choices(["Active", "Dormant", "Closed"], weights=[80, 15, 5])[0]
            db.add(UBIDActivity(
                ubid_id=ubid.id,
                status=status,
                score=random.uniform(0.1, 1.0),
                evidence_timeline=[{"event": "Initial Linkage", "date": (datetime.utcnow() - timedelta(days=random.randint(1, 300))).isoformat()}]
            ))

            # Linked Departments (1 to 5)
            num_depts = random.randint(1, 5)
            selected_depts = random.sample(DEPARTMENTS, num_depts)
            
            for dept in selected_depts:
                # Add slight variations to name for some departments
                variant_name = base_name if random.random() > 0.3 else base_name.replace("Pvt Ltd", "").replace("Ltd", "").strip()
                payload = {
                    "name": variant_name,
                    "pan": pan,
                    "address": f"Plot {random.randint(1, 500)}, Phase {random.randint(1, 4)}, Industrial Area",
                    "pincode": pincode
                }
                raw = RawRecord(
                    source_system=dept,
                    source_record_id=f"{dept[:3].upper()}-{random.randint(10000, 99999)}",
                    raw_payload=payload,
                    checksum=compute_checksum(payload)
                )
                db.add(raw)
                await db.flush()
                
                # Select a random hub for this business cluster
                hub = random.choice(KARNATAKA_HUBS)
                pincode = hub["pincode"]
                base_lat = hub["lat"]
                base_lon = hub["lon"]
                spread = hub["spread"]
                
                lat = base_lat + random.uniform(-spread, spread)
                lon = base_lon + random.uniform(-spread, spread)
                
                norm = NormalizedRecord(
                    raw_record_id=raw.id,
                    normalized_name=variant_name.upper(),
                    pincode=pincode,
                    pan=pan,
                    latitude=lat,
                    longitude=lon,
                    sector=get_sector(variant_name)
                )
                db.add(norm)
                await db.flush()
                
                db.add(RecordLink(
                    ubid_id=ubid.id,
                    raw_record_id=raw.id,
                    source_system=dept,
                    source_record_id=raw.source_record_id,
                    confidence=1.0,
                    decision_type="auto_link"
                ))
            
            if i % 100 == 0:
                print(f"  Processed {i} businesses...")
                await db.commit()

        # 2. Add Ambiguous Pairs for Review Queue (50 items)
        print("--- Adding 50 Ambiguous Review Queue Items ---")
        for j in range(50):
            base_name = generate_business_name()
            pan = generate_pan()
            
            # Record A (Municipal)
            pay_a = {"name": base_name, "address": "Phase 1 Industrial Area", "pan": pan}
            raw_a = RawRecord(source_system="municipal", source_record_id=f"MUC-Q{j}", raw_payload=pay_a, checksum=compute_checksum(pay_a))
            db.add(raw_a)
            await db.flush()
            hub = random.choice(KARNATAKA_HUBS)
            base_lat = hub["lat"]
            base_lon = hub["lon"]
            spread = hub["spread"]
            lat = base_lat + random.uniform(-spread, spread)
            lon = base_lon + random.uniform(-spread, spread)
            
            norm_a = NormalizedRecord(
                raw_record_id=raw_a.id, 
                normalized_name=base_name.upper(), 
                pincode=hub["pincode"], 
                pan=pan,
                latitude=lat,
                longitude=lon,
                sector=get_sector(base_name)
            )
            db.add(norm_a)
            
            # Record B (Tax - slightly different name)
            pay_b = {"name": base_name.replace(" ", "  "), "address": "Industrial Hub", "pan": pan}
            raw_b = RawRecord(source_system="tax", source_record_id=f"TAX-Q{j}", raw_payload=pay_b, checksum=compute_checksum(pay_b))
            db.add(raw_b)
            await db.flush()
            norm_b = NormalizedRecord(
                raw_record_id=raw_b.id, 
                normalized_name=base_name.upper(), 
                pincode=hub["pincode"], 
                pan=pan,
                latitude=lat,
                longitude=lon,
                sector=get_sector(base_name)
            )
            db.add(norm_b)
            await db.flush()

            pair = CandidatePair(record_a_id=norm_a.id, record_b_id=norm_b.id, blocking_strategy="pan_match")
            db.add(pair)
            await db.flush()
            
            conf = random.uniform(0.65, 0.88)
            scored = ScoredPair(
                pair_id=pair.id, record_a_id=norm_a.id, record_b_id=norm_b.id,
                feature_vector={"name": conf, "pan": 1.0}, confidence_score=conf,
                evidence_object={"name_similarity": conf, "pan_exact": 1.0}, weight_version="v1.0"
            )
            db.add(scored)
            await db.flush()
            db.add(ReviewQueue(pair_id=pair.id, scored_pair_id=scored.id, confidence_score=conf, priority=random.randint(0, 3), status="pending"))

        await db.commit()
        print("--- Mass Seed Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(seed_mass_data(1000))
