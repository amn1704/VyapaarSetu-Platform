from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


READ_MODEL_SQL = [
    "DROP VIEW IF EXISTS ubid_registry",
    """
    CREATE VIEW ubid_registry AS
    SELECT
        u.ubid_code AS ubid,
        COALESCE(
            MIN(json_extract(rr.raw_payload, '$.name')),
            MIN(n.normalized_name),
            'Unknown Business'
        ) AS business_name,
        u.pan AS pan_anchor,
        u.gstin AS gstin_anchor,
        COALESCE(a.status, 'Unknown') AS status,
        COALESCE(
            MIN(CASE WHEN n.sector IN ('Engineering', 'Electronics/IT', 'Chemicals & Pharma') THEN n.sector END),
            MIN(n.sector),
            'Unknown'
        ) AS sector,
        MIN(n.pincode) AS pin_code,
        NULL AS district,
        MAX(l.confidence) AS confidence_score,
        COUNT(DISTINCT l.raw_record_id) AS source_record_count,
        COUNT(DISTINCT l.source_system) AS department_count,
        date(MIN(u.created_at)) AS assigned_on,
        MAX(u.updated_at) AS last_updated
    FROM ubids u
    LEFT JOIN ubid_activity a ON a.ubid_id = u.id
    LEFT JOIN record_links l ON l.ubid_id = u.id AND l.unlinked_at IS NULL
    LEFT JOIN raw_records rr ON rr.id = l.raw_record_id
    LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
    WHERE u.is_canonical = 1
    GROUP BY u.id, u.ubid_code, u.pan, u.gstin, a.status
    """,
    "DROP VIEW IF EXISTS source_records",
    """
    CREATE VIEW source_records AS
    SELECT
        rr.id,
        u.ubid_code AS ubid,
        rr.source_system,
        rr.source_record_id,
        COALESCE(json_extract(rr.raw_payload, '$.name'), n.normalized_name, 'Unknown Business') AS raw_name,
        json_extract(rr.raw_payload, '$.address') AS raw_address,
        n.pincode AS pin_code,
        n.sector,
        n.pan,
        n.gstin,
        l.confidence AS link_confidence,
        l.decision_type AS link_type,
        l.linked_at,
        rr.extracted_at
    FROM raw_records rr
    LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
    LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
    LEFT JOIN ubids u ON u.id = l.ubid_id
    """,
    "DROP VIEW IF EXISTS activity_events",
    """
    CREATE VIEW activity_events AS
    SELECT
        e.id,
        u.ubid_code AS ubid,
        e.source_system,
        e.event_type,
        e.event_date,
        json_extract(e.payload, '$.event_outcome') AS event_outcome,
        e.ingested_at
    FROM events e
    LEFT JOIN ubids u ON u.id = e.ubid_id
    """,
    "DROP VIEW IF EXISTS audit_log",
    """
    CREATE VIEW audit_log AS
    SELECT
        id,
        entity_id AS ubid,
        action,
        actor,
        entity_type,
        created_at
    FROM audit_logs
    """,
]


async def ensure_read_model(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for statement in READ_MODEL_SQL:
            await conn.execute(text(statement))
