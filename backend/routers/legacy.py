import json
import re
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services.llm_service import llm_service
from ..services.pseudonymiser import pseudonymiser
from ..services.ubid_service import generate_ubid_code
from ..auth import sanitize_reviewer_id

router = APIRouter()


def _json_loads(value: Any, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _payload(row: Any) -> dict:
    return _json_loads(getattr(row, "raw_payload", None), {}) or {}


def _address(row: Any) -> str:
    payload = _payload(row)
    parsed = _json_loads(getattr(row, "parsed_address", None), None)
    if isinstance(parsed, dict):
        parts = [str(v) for v in parsed.values() if v]
        if parts:
            return ", ".join(parts)
    return payload.get("address") or getattr(row, "pincode", None) or "N/A"


def _fmt_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value).split("T", 1)[0].split(" ", 1)[0]


def _unique(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: Any) -> set[str]:
    return {token for token in re.split(r"[^A-Z0-9]+", _clean_text(value).upper()) if token}


def _ratio_pct(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100)


def _evidence_percent(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number * 100 if number <= 1 else number)


def _decision_band(score: float | None) -> str:
    score = float(score or 0)
    if score >= 0.85:
        return "Good match"
    if score >= 0.70:
        return "Needs officer check"
    if score >= 0.55:
        return "Needs more proof"
    return "Likely separate"


def _simple_review_summary(record_a: dict, record_b: dict, evidence: dict, confidence_score: float | None) -> str:
    same_pan = evidence.get("matches", {}).get("pan")
    same_pin = evidence.get("matches", {}).get("pincode")
    same_sector = evidence.get("matches", {}).get("sector")
    name_overlap = evidence.get("token_overlap", {}).get("name", 0)
    address_overlap = evidence.get("token_overlap", {}).get("address", 0)
    missing_gstin = record_a.get("gstin") in (None, "", "N/A") or record_b.get("gstin") in (None, "", "N/A")

    positives = []
    if same_pan:
        positives.append("same PAN")
    if same_pin:
        positives.append("same PIN code")
    if same_sector:
        positives.append("same business type")
    if name_overlap >= 80:
        positives.append("very similar business name")
    elif name_overlap >= 50:
        positives.append("partly similar business name")

    cautions = []
    if address_overlap < 40:
        cautions.append("addresses do not fully match")
    if missing_gstin:
        cautions.append("GSTIN is missing")

    support = ", ".join(positives) if positives else "limited matching information"
    caution = ", ".join(cautions) if cautions else "no major warning sign is visible"
    action = (
        "approve if documents look genuine"
        if same_pan and same_pin and name_overlap >= 70 and float(confidence_score or 0) >= 0.6
        else "keep separate unless more proof is available"
    )
    return f"These records show {support}. Please note: {caution}. Recommended action: {action}."


def _review_evidence(record_a: dict, record_b: dict, evidence: dict, feature_vector: dict, confidence_score: float | None) -> dict:
    name_a = record_a.get("name")
    name_b = record_b.get("name")
    address_a = record_a.get("address")
    address_b = record_b.get("address")
    name_tokens_a = _tokens(name_a)
    name_tokens_b = _tokens(name_b)
    address_tokens_a = _tokens(address_a)
    address_tokens_b = _tokens(address_b)

    name_overlap = _ratio_pct(len(name_tokens_a & name_tokens_b), len(name_tokens_a | name_tokens_b))
    address_overlap = _ratio_pct(len(address_tokens_a & address_tokens_b), len(address_tokens_a | address_tokens_b))
    pan_match = record_a.get("pan") not in (None, "", "N/A") and record_a.get("pan") == record_b.get("pan")
    gstin_match = record_a.get("gstin") not in (None, "", "N/A") and record_a.get("gstin") == record_b.get("gstin")
    pincode_match = record_a.get("pincode") not in (None, "", "N/A") and record_a.get("pincode") == record_b.get("pincode")
    sector_match = record_a.get("sector") not in (None, "", "Unknown") and record_a.get("sector") == record_b.get("sector")

    feature_scores = [
        {"label": "Model confidence", "value": _evidence_percent(confidence_score), "tone": "warning"},
        {"label": "Name model score", "value": _evidence_percent(evidence.get("name_similarity") or evidence.get("fuzzy_name_similarity") or feature_vector.get("name") or name_overlap), "tone": "success" if name_overlap >= 70 else "warning"},
        {"label": "Address overlap", "value": _evidence_percent(evidence.get("address_overlap") or feature_vector.get("address") or address_overlap), "tone": "success" if address_overlap >= 50 else "warning"},
    ]

    signals = []
    cautions = []
    if pan_match:
        signals.append("Same PAN is present in both records.")
    elif record_a.get("pan") not in (None, "", "N/A") and record_b.get("pan") not in (None, "", "N/A"):
        cautions.append("PAN values are different. Keep separate unless a senior officer approves.")
    else:
        cautions.append("PAN is missing on at least one record.")

    if gstin_match:
        signals.append("Same GSTIN is present in both records.")
    elif record_a.get("gstin") not in (None, "", "N/A") and record_b.get("gstin") not in (None, "", "N/A"):
        cautions.append("GSTIN values differ.")
    else:
        cautions.append("GSTIN is missing, so verify using other documents.")

    if name_overlap >= 70:
        signals.append("Business names look very similar.")
    else:
        cautions.append("Business names are not very similar.")

    if address_overlap < 40:
        cautions.append("Addresses are not a strong match.")

    if pincode_match:
        signals.append("PIN code matches.")
    else:
        cautions.append("PIN code does not match or is missing.")

    if sector_match:
        signals.append("Business type matches.")
    else:
        cautions.append("Business type differs or is unavailable.")

    return {
        "band": "Likely same, verify" if pan_match and pincode_match and name_overlap >= 70 else _decision_band(confidence_score),
        "signals": signals,
        "cautions": cautions,
        "feature_scores": [score for score in feature_scores if score["value"] is not None],
        "matches": {
            "pan": bool(pan_match),
            "gstin": bool(gstin_match),
            "pincode": bool(pincode_match),
            "sector": bool(sector_match),
        },
        "token_overlap": {
            "name": name_overlap,
            "address": address_overlap,
            "shared_name_tokens": sorted(name_tokens_a & name_tokens_b),
        },
        "raw": evidence,
    }


@router.get("/api/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    industrial_sectors = ("Engineering", "Electronics/IT", "Chemicals & Pharma")
    industrial_sector_sql = ", ".join(f"'{sector}'" for sector in industrial_sectors)

    metrics = {
        "total_ingested": (await db.execute(text("SELECT COUNT(*) FROM raw_records"))).scalar_one(),
        "total_ubids": (await db.execute(text("SELECT COUNT(*) FROM ubids WHERE is_canonical = 1"))).scalar_one(),
        "active_businesses": (await db.execute(text("SELECT COUNT(*) FROM ubid_activity WHERE status = 'Active'"))).scalar_one(),
        "pending_review": (await db.execute(text("SELECT COUNT(*) FROM review_queue WHERE status IN ('pending', 'locked')"))).scalar_one(),
    }
    metrics.update(
        {
            "dormant_businesses": (
                await db.execute(text("SELECT COUNT(*) FROM ubid_activity WHERE status = 'Dormant'"))
            ).scalar_one(),
            "closed_businesses": (
                await db.execute(text("SELECT COUNT(*) FROM ubid_activity WHERE status = 'Closed'"))
            ).scalar_one(),
            "pan_anchored": (
                await db.execute(text("SELECT COUNT(*) FROM ubids WHERE is_canonical = 1 AND pan IS NOT NULL AND pan != ''"))
            ).scalar_one(),
            "gstin_anchored": (
                await db.execute(text("SELECT COUNT(*) FROM ubids WHERE is_canonical = 1 AND gstin IS NOT NULL AND gstin != ''"))
            ).scalar_one(),
            "linked_source_records": (
                await db.execute(text("SELECT COUNT(*) FROM record_links WHERE unlinked_at IS NULL"))
            ).scalar_one(),
            "pending_events": (
                await db.execute(text("SELECT COUNT(*) FROM pending_events"))
            ).scalar_one(),
        }
    )

    sources = [
        {"name": row.name.title(), "records": row.records}
        for row in (
            await db.execute(
                text(
                    """
                    SELECT source_system AS name, COUNT(*) AS records
                    FROM raw_records
                    GROUP BY source_system
                    ORDER BY records DESC
                    """
                )
            )
        ).all()
    ]
    sectors = [
        {
            "name": row.name or "Unknown",
            "value": row.value,
            "active": row.active or 0,
            "dormant": row.dormant or 0,
            "closed": row.closed or 0,
            "linked_records": row.linked_records or 0,
            "avg_confidence": round(row.avg_confidence or 0, 3),
            "pin_count": row.pin_count or 0,
        }
        for row in (
            await db.execute(
                text(
                    """
                    SELECT
                        COALESCE(u.sector, 'Unknown') AS name,
                        COUNT(DISTINCT u.ubid) AS value,
                        COUNT(DISTINCT CASE WHEN u.status = 'Active' THEN u.ubid END) AS active,
                        COUNT(DISTINCT CASE WHEN u.status = 'Dormant' THEN u.ubid END) AS dormant,
                        COUNT(DISTINCT CASE WHEN u.status = 'Closed' THEN u.ubid END) AS closed,
                        COUNT(DISTINCT u.pin_code) AS pin_count,
                        ROUND(AVG(u.confidence_score), 3) AS avg_confidence,
                        COUNT(sr.id) AS linked_records
                    FROM ubid_registry u
                    LEFT JOIN source_records sr ON sr.ubid = u.ubid
                    GROUP BY COALESCE(u.sector, 'Unknown')
                    ORDER BY value DESC
                    LIMIT 8
                    """
                )
            )
        ).all()
    ]
    activity = [
        {"name": row.name, "value": row.value}
        for row in (
            await db.execute(
                text(
                    """
                    SELECT status AS name, COUNT(*) AS value
                    FROM ubid_activity
                    GROUP BY status
                    ORDER BY value DESC
                    """
                )
            )
        ).all()
    ]
    pincode_hotspots = [
        {"name": row.pin_code or "Unknown", "value": row.value, "active": row.active}
        for row in (
            await db.execute(
                text(
                    """
                    SELECT u.pin_code, COUNT(*) AS value,
                           SUM(CASE WHEN u.status = 'Active' THEN 1 ELSE 0 END) AS active
                    FROM ubid_registry u
                    GROUP BY u.pin_code
                    ORDER BY value DESC
                    LIMIT 8
                    """
                )
            )
        ).all()
    ]
    confidence_bands = [
        {"name": row.band, "value": row.value}
        for row in (
            await db.execute(
                text(
                    """
                    SELECT
                        CASE
                            WHEN confidence >= 0.95 THEN 'Auto-link ready'
                            WHEN confidence >= 0.75 THEN 'Human review band'
                            ELSE 'Keep separate'
                        END AS band,
                        COUNT(*) AS value
                    FROM record_links
                    WHERE unlinked_at IS NULL
                    GROUP BY band
                    ORDER BY value DESC
                    """
                )
            )
        ).all()
    ]
    source_coverage = [
        {"name": row.name.title(), "linked": row.linked, "raw": row.raw}
        for row in (
            await db.execute(
                text(
                    """
                    SELECT rr.source_system AS name,
                           COUNT(*) AS raw,
                           SUM(CASE WHEN l.ubid_id IS NOT NULL THEN 1 ELSE 0 END) AS linked
                    FROM raw_records rr
                    LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                    GROUP BY rr.source_system
                    ORDER BY raw DESC
                    """
                )
            )
        ).all()
    ]

    top_pin_row = (
        await db.execute(
            text(
                f"""
                SELECT pin_code, COUNT(*) AS count
                FROM ubid_registry
                WHERE status = 'Active'
                  AND sector IN ({industrial_sector_sql})
                GROUP BY pin_code
                ORDER BY count DESC
                LIMIT 1
                """
            )
        )
    ).first()
    top_pin = top_pin_row.pin_code if top_pin_row else "560058"

    query_cards = [
        {
            "label": f"Active industrial UBIDs in pin {top_pin} with no inspection in the last 18 months",
            "question": f"Find all active factories in pin code {top_pin} with no inspection in the last 18 months",
            "source": "UBID Registry + Activity Events",
            "metric": (
                await db.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM ubid_registry u
                        LEFT JOIN activity_events ae
                          ON ae.ubid = u.ubid
                         AND ae.event_type = 'inspection'
                        WHERE u.pin_code = :pin_code
                          AND u.status = 'Active'
                          AND u.sector IN ({industrial_sector_sql})
                        GROUP BY u.pin_code
                        HAVING MAX(ae.event_date) < date('now', '-18 months')
                            OR MAX(ae.event_date) IS NULL
                        """
                    ),
                    {"pin_code": top_pin},
                )
            ).scalar()
            or 0,
            "unit": "UBIDs need inspection evidence",
            "tone": "primary",
        },
        {
            "label": "PAN anchored UBIDs without GSTIN anchor",
            "question": "Show businesses with PAN anchor but missing GSTIN anchor gap",
            "source": "Central identifier anchors",
            "metric": metrics["pan_anchored"] - metrics["gstin_anchored"],
            "unit": "identifier gaps",
            "tone": "warning",
        },
        {
            "label": "Ambiguous linkage decisions awaiting reviewer",
            "question": "Show ambiguous UBID matches in the human review queue",
            "source": "Reviewer workflow",
            "metric": metrics["pending_review"],
            "unit": "cases",
            "tone": "review",
        },
    ]

    return {
        "metrics": metrics,
        "charts": {
            "sources": sources,
            "sectors": sectors,
            "activity": activity,
            "pincode_hotspots": pincode_hotspots,
            "confidence_bands": confidence_bands,
            "source_coverage": source_coverage,
        },
        "query_cards": query_cards,
    }


@router.get("/api/map-data")
async def map_data(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            text(
                """
                SELECT
                    u.ubid_code,
                    MIN(n.normalized_name) AS name,
                    a.status,
                    AVG(n.latitude) AS lat,
                    AVG(n.longitude) AS lng
                FROM ubids u
                JOIN ubid_activity a ON a.ubid_id = u.id
                JOIN record_links l ON l.ubid_id = u.id AND l.unlinked_at IS NULL
                JOIN normalized_records n ON n.raw_record_id = l.raw_record_id
                WHERE n.latitude IS NOT NULL AND n.longitude IS NOT NULL
                GROUP BY u.id, u.ubid_code, a.status
                LIMIT 500
                """
            )
        )
    ).all()

    return [
        {
            "id": row.ubid_code,
            "name": row.name or "Unknown Business",
            "status": row.status,
            "lat": row.lat,
            "lng": row.lng,
        }
        for row in rows
    ]


@router.get("/api/raw-records")
async def raw_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    sector: str | None = None,
    status: str | None = None,
    linked: str | None = None,
    identifier: str | None = None,
    pincode: str | None = None,
    q: str | None = None,
    sort: str = "newest",
    db: AsyncSession = Depends(get_db),
):
    where = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if source and source != "all":
        source_map = {"labour": "labor", "kspcb": "pollution", "commercial_tax": "tax"}
        where.append("rr.source_system = :source")
        params["source"] = source_map.get(source, source)
    if sector and sector != "all":
        where.append("COALESCE(n.sector, 'Unknown') = :sector")
        params["sector"] = sector
    if status and status != "all":
        where.append("COALESCE(a.status, 'Unlinked') = :status")
        params["status"] = status
    if linked and linked != "all":
        if linked == "linked":
            where.append("l.ubid_id IS NOT NULL AND l.unlinked_at IS NULL")
        elif linked == "unlinked":
            where.append("(l.ubid_id IS NULL OR l.unlinked_at IS NOT NULL)")
    if identifier and identifier != "all":
        if identifier == "pan":
            where.append("n.pan IS NOT NULL AND n.pan != ''")
        elif identifier == "gstin":
            where.append("n.gstin IS NOT NULL AND n.gstin != ''")
        elif identifier == "missing_pan":
            where.append("(n.pan IS NULL OR n.pan = '')")
        elif identifier == "missing_gstin":
            where.append("(n.gstin IS NULL OR n.gstin = '')")
    if pincode and pincode != "all":
        where.append("n.pincode = :pincode")
        params["pincode"] = pincode
    if q:
        where.append(
            """
            (
                UPPER(rr.source_record_id) LIKE :q
                OR UPPER(COALESCE(json_extract(rr.raw_payload, '$.name'), n.normalized_name, '')) LIKE :q
                OR UPPER(COALESCE(json_extract(rr.raw_payload, '$.address'), '')) LIKE :q
                OR UPPER(COALESCE(n.pan, '')) LIKE :q
                OR UPPER(COALESCE(n.gstin, '')) LIKE :q
                OR UPPER(COALESCE(u.ubid_code, '')) LIKE :q
            )
            """
        )
        params["q"] = f"%{q.strip().upper()}%"

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sort_sql = {
        "newest": "rr.extracted_at DESC",
        "oldest": "rr.extracted_at ASC",
        "confidence": "COALESCE(l.confidence, 0) DESC, rr.extracted_at DESC",
        "name": "COALESCE(json_extract(rr.raw_payload, '$.name'), n.normalized_name, '') ASC",
    }.get(sort, "rr.extracted_at DESC")

    base_from = """
        FROM raw_records rr
        LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
        LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
        LEFT JOIN ubids u ON u.id = l.ubid_id
        LEFT JOIN ubid_activity a ON a.ubid_id = u.id
    """

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) {base_from} {where_sql}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
    ).scalar_one()

    summary_row = (
        await db.execute(
            text(
                f"""
                SELECT
                    SUM(CASE WHEN l.ubid_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_count,
                    SUM(CASE WHEN l.ubid_id IS NULL THEN 1 ELSE 0 END) AS unlinked_count,
                    SUM(CASE WHEN n.pan IS NOT NULL AND n.pan != '' THEN 1 ELSE 0 END) AS pan_count,
                    SUM(CASE WHEN n.gstin IS NOT NULL AND n.gstin != '' THEN 1 ELSE 0 END) AS gstin_count,
                    ROUND(AVG(COALESCE(l.confidence, 0)), 3) AS avg_confidence
                {base_from}
                {where_sql}
                """
            ),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
    ).first()

    rows = (
        await db.execute(
            text(
                f"""
                SELECT
                    rr.source_system,
                    rr.source_record_id,
                    rr.raw_payload,
                    rr.extracted_at,
                    n.normalized_name,
                    n.parsed_address,
                    n.pincode,
                    n.pan,
                    n.gstin,
                    n.sector,
                    l.confidence,
                    l.decision_type,
                    u.ubid_code,
                    a.status
                {base_from}
                {where_sql}
                ORDER BY {sort_sql}
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
    ).all()

    records = []
    for row in rows:
        payload = _payload(row)
        records.append(
            {
                "id": row.source_record_id,
                "source": row.source_system,
                "name": payload.get("name") or row.normalized_name or "Unknown",
                "address": payload.get("address") or _address(row),
                "pan": row.pan or payload.get("pan") or "N/A",
                "gstin": row.gstin or payload.get("gstin") or "N/A",
                "sector": row.sector or "Unknown",
                "pincode": row.pincode or "N/A",
                "ubid": row.ubid_code,
                "status": row.status or "Unlinked",
                "linked": bool(row.ubid_code),
                "confidence": round((row.confidence or 0) * 100) if row.confidence is not None else None,
                "decision_type": row.decision_type or "Unlinked",
                "date": _fmt_date(row.extracted_at),
            }
        )

    facet_rows = {}
    for facet_name, facet_sql in {
        "sources": "SELECT source_system AS name, COUNT(*) AS value FROM raw_records GROUP BY source_system ORDER BY value DESC",
        "sectors": "SELECT COALESCE(sector, 'Unknown') AS name, COUNT(*) AS value FROM normalized_records GROUP BY COALESCE(sector, 'Unknown') ORDER BY value DESC",
        "pincodes": "SELECT COALESCE(pincode, 'Unknown') AS name, COUNT(*) AS value FROM normalized_records GROUP BY COALESCE(pincode, 'Unknown') ORDER BY value DESC LIMIT 25",
        "statuses": "SELECT COALESCE(a.status, 'Unlinked') AS name, COUNT(*) AS value FROM raw_records rr LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL LEFT JOIN ubid_activity a ON a.ubid_id = l.ubid_id GROUP BY COALESCE(a.status, 'Unlinked') ORDER BY value DESC",
    }.items():
        facet_rows[facet_name] = [
            {"name": row.name, "value": row.value}
            for row in (await db.execute(text(facet_sql))).all()
        ]

    return {
        "records": records,
        "total": total,
        "summary": {
            "linked": summary_row.linked_count or 0,
            "unlinked": summary_row.unlinked_count or 0,
            "with_pan": summary_row.pan_count or 0,
            "with_gstin": summary_row.gstin_count or 0,
            "avg_confidence": round((summary_row.avg_confidence or 0) * 100),
        },
        "facets": facet_rows,
    }


@router.get("/api/review-queue")
async def review_queue(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            text(
                """
                SELECT
                    rq.id, rq.confidence_score, rq.priority, rq.queued_at,
                    cp.blocking_strategy,
                    sp.feature_vector, sp.evidence_object, sp.weight_version, sp.scored_at,
                    ra.source_system AS source_a, ra.source_record_id AS source_id_a, ra.raw_payload AS raw_payload_a,
                    na.normalized_name AS name_a, na.parsed_address AS parsed_address_a,
                    na.pincode AS pincode_a, na.pan AS pan_a, na.gstin AS gstin_a, na.sector AS sector_a,
                    rb.source_system AS source_b, rb.source_record_id AS source_id_b, rb.raw_payload AS raw_payload_b,
                    nb.normalized_name AS name_b, nb.parsed_address AS parsed_address_b,
                    nb.pincode AS pincode_b, nb.pan AS pan_b, nb.gstin AS gstin_b, nb.sector AS sector_b
                FROM review_queue rq
                JOIN candidate_pairs cp ON cp.id = rq.pair_id
                JOIN normalized_records na ON na.id = cp.record_a_id
                JOIN raw_records ra ON ra.id = na.raw_record_id
                JOIN normalized_records nb ON nb.id = cp.record_b_id
                JOIN raw_records rb ON rb.id = nb.raw_record_id
                LEFT JOIN scored_pairs sp ON sp.id = rq.scored_pair_id
                WHERE rq.status = 'pending'
                ORDER BY rq.priority DESC, rq.queued_at ASC
                LIMIT 100
                """
            )
        )
    ).all()

    def record(row: Any, side: str) -> dict:
        payload = _json_loads(getattr(row, f"raw_payload_{side}"), {}) or {}
        parsed = _json_loads(getattr(row, f"parsed_address_{side}"), None)
        address = "N/A"
        if isinstance(parsed, dict):
            address = ", ".join(str(v) for v in parsed.values() if v) or address
        address = payload.get("address") or address
        return {
            "id": getattr(row, f"source_id_{side}"),
            "source": getattr(row, f"source_{side}"),
            "name": payload.get("name") or getattr(row, f"name_{side}") or "Unknown",
            "address": address,
            "pan": getattr(row, f"pan_{side}") or payload.get("pan") or "N/A",
            "gstin": getattr(row, f"gstin_{side}") or payload.get("gstin") or "N/A",
            "pincode": getattr(row, f"pincode_{side}") or payload.get("pincode") or "N/A",
            "sector": getattr(row, f"sector_{side}") or payload.get("sector") or "Unknown",
        }

    items = []
    for row in rows:
        record_a = record(row, "a")
        record_b = record(row, "b")
        evidence = _json_loads(row.evidence_object, {}) or {}
        feature_vector = _json_loads(row.feature_vector, {}) or {}
        review_evidence = _review_evidence(record_a, record_b, evidence, feature_vector, row.confidence_score)
        items.append(
            {
                "id": row.id,
                "confidence_score": round((row.confidence_score or 0) * 100),
                "priority": row.priority or 0,
                "queued_at": _fmt_date(row.queued_at),
                "blocking_strategy": row.blocking_strategy,
                "model": {
                    "weight_version": row.weight_version or "N/A",
                    "scored_at": _fmt_date(row.scored_at),
                },
                "recordA": record_a,
                "recordB": record_b,
                "summary": _simple_review_summary(record_a, record_b, review_evidence, row.confidence_score),
                "recommendation": "approve" if review_evidence["matches"]["pan"] and review_evidence["matches"]["pincode"] and review_evidence["token_overlap"]["name"] >= 70 else "keep_separate",
                "evidence": review_evidence,
            }
        )
    return items


@router.get("/api/review-queue/{queue_item_id}/summary")
async def review_queue_summary(queue_item_id: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            text(
                """
                SELECT
                    rq.id, rq.confidence_score,
                    cp.blocking_strategy,
                    sp.feature_vector, sp.evidence_object,
                    ra.source_system AS source_a, ra.source_record_id AS source_id_a, ra.raw_payload AS raw_payload_a,
                    na.normalized_name AS name_a, na.parsed_address AS parsed_address_a,
                    na.pincode AS pincode_a, na.pan AS pan_a, na.gstin AS gstin_a, na.sector AS sector_a,
                    rb.source_system AS source_b, rb.source_record_id AS source_id_b, rb.raw_payload AS raw_payload_b,
                    nb.normalized_name AS name_b, nb.parsed_address AS parsed_address_b,
                    nb.pincode AS pincode_b, nb.pan AS pan_b, nb.gstin AS gstin_b, nb.sector AS sector_b
                FROM review_queue rq
                JOIN candidate_pairs cp ON cp.id = rq.pair_id
                JOIN normalized_records na ON na.id = cp.record_a_id
                JOIN raw_records ra ON ra.id = na.raw_record_id
                JOIN normalized_records nb ON nb.id = cp.record_b_id
                JOIN raw_records rb ON rb.id = nb.raw_record_id
                LEFT JOIN scored_pairs sp ON sp.id = rq.scored_pair_id
                WHERE rq.id = :id
                LIMIT 1
                """
            ),
            {"id": queue_item_id},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")

    def record(side: str) -> dict:
        payload = _json_loads(getattr(row, f"raw_payload_{side}"), {}) or {}
        parsed = _json_loads(getattr(row, f"parsed_address_{side}"), None)
        address = "N/A"
        if isinstance(parsed, dict):
            address = ", ".join(str(v) for v in parsed.values() if v) or address
        address = payload.get("address") or address
        return {
            "source": getattr(row, f"source_{side}"),
            "name": payload.get("name") or getattr(row, f"name_{side}") or "Unknown",
            "address": address,
            "pan": getattr(row, f"pan_{side}") or payload.get("pan") or "N/A",
            "gstin": getattr(row, f"gstin_{side}") or payload.get("gstin") or "N/A",
            "pincode": getattr(row, f"pincode_{side}") or payload.get("pincode") or "N/A",
            "sector": getattr(row, f"sector_{side}") or payload.get("sector") or "Unknown",
        }

    record_a = record("a")
    record_b = record("b")
    raw_evidence = _json_loads(row.evidence_object, {}) or {}
    feature_vector = _json_loads(row.feature_vector, {}) or {}
    evidence = _review_evidence(record_a, record_b, raw_evidence, feature_vector, row.confidence_score)
    fallback = _simple_review_summary(record_a, record_b, evidence, row.confidence_score)

    try:
        llm_input = {
            "record_a": pseudonymiser.pseudonymise_record(record_a),
            "record_b": pseudonymiser.pseudonymise_record(record_b),
            "plain_evidence": {
                "same_pan": evidence["matches"]["pan"],
                "same_gstin": evidence["matches"]["gstin"],
                "same_pin_code": evidence["matches"]["pincode"],
                "same_business_type": evidence["matches"]["sector"],
                "name_similarity_percent": evidence["token_overlap"]["name"],
                "address_similarity_percent": evidence["token_overlap"]["address"],
                "confidence_percent": round((row.confidence_score or 0) * 100),
                "blocking_reason": row.blocking_strategy,
            },
        }
        summary = await llm_service.summarise_evidence(llm_input)
        if not summary:
            summary = fallback
        source = "local_llm"
    except Exception:
        summary = fallback
        source = "rule_summary"

    recommendation = (
        "approve"
        if "approve" in summary.lower() or (evidence["matches"]["pan"] and evidence["matches"]["pincode"] and evidence["token_overlap"]["name"] >= 70)
        else "keep_separate"
    )
    return {
        "summary": summary,
        "recommendation": recommendation,
        "source": source,
    }


class ReviewAction(BaseModel):
    model_config = {"populate_by_name": True, "extra": "ignore"}

    queue_item_id: str = Field(..., alias="queueItemId")
    decision: str
    reviewer_id: str | None = Field(default=None, alias="reviewerId")
    justification: str | None = None


async def _next_ubid_code(db: AsyncSession) -> str:
    count = (await db.execute(text("SELECT COUNT(*) FROM ubids"))).scalar_one()
    sequence = int(count or 0) + 1
    year = datetime.utcnow().year
    while True:
        code = generate_ubid_code(sequence, year)
        exists = (await db.execute(text("SELECT 1 FROM ubids WHERE ubid_code = :code"), {"code": code})).first()
        if not exists:
            return code
        sequence += 1


def _uuid_hex() -> str:
    return uuid.uuid4().hex


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


async def _review_pair_context(db: AsyncSession, queue_item_id: str):
    return (
        await db.execute(
            text(
                """
                SELECT
                    rq.id AS queue_item_id,
                    rq.status AS queue_status,
                    rq.pair_id,
                    rq.scored_pair_id,
                    rq.confidence_score,
                    cp.record_a_id,
                    cp.record_b_id,
                    sp.feature_vector,
                    sp.evidence_object,
                    ra.id AS raw_a_id,
                    ra.source_system AS source_a,
                    ra.source_record_id AS source_record_id_a,
                    ra.raw_payload AS raw_payload_a,
                    na.normalized_name AS name_a,
                    na.pan AS pan_a,
                    na.gstin AS gstin_a,
                    na.sector AS sector_a,
                    na.pincode AS pincode_a,
                    rb.id AS raw_b_id,
                    rb.source_system AS source_b,
                    rb.source_record_id AS source_record_id_b,
                    rb.raw_payload AS raw_payload_b,
                    nb.normalized_name AS name_b,
                    nb.pan AS pan_b,
                    nb.gstin AS gstin_b,
                    nb.sector AS sector_b,
                    nb.pincode AS pincode_b
                FROM review_queue rq
                JOIN candidate_pairs cp ON cp.id = rq.pair_id
                JOIN normalized_records na ON na.id = cp.record_a_id
                JOIN raw_records ra ON ra.id = na.raw_record_id
                JOIN normalized_records nb ON nb.id = cp.record_b_id
                JOIN raw_records rb ON rb.id = nb.raw_record_id
                LEFT JOIN scored_pairs sp ON sp.id = rq.scored_pair_id
                WHERE rq.id = :id
                LIMIT 1
                """
            ),
            {"id": queue_item_id},
        )
    ).first()


async def _existing_link_ubid(db: AsyncSession, raw_ids: list[str]) -> str | None:
    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT ubid_id
                FROM record_links
                WHERE raw_record_id IN :raw_ids
                  AND unlinked_at IS NULL
                ORDER BY linked_at ASC
                """
            ).bindparams(__import__("sqlalchemy").bindparam("raw_ids", expanding=True)),
            {"raw_ids": raw_ids},
        )
    ).all()
    return rows[0].ubid_id if rows else None


async def _ensure_review_ubid(db: AsyncSession, ctx: Any) -> str:
    raw_ids = [ctx.raw_a_id, ctx.raw_b_id]
    ubid_id = await _existing_link_ubid(db, raw_ids)
    if ubid_id:
        return ubid_id

    ubid_id = _uuid_hex()
    ubid_code = await _next_ubid_code(db)
    pan = ctx.pan_a if ctx.pan_a and ctx.pan_a == ctx.pan_b else _first_value(ctx.pan_a, ctx.pan_b)
    gstin = ctx.gstin_a if ctx.gstin_a and ctx.gstin_a == ctx.gstin_b else _first_value(ctx.gstin_a, ctx.gstin_b)
    await db.execute(
        text(
            """
            INSERT INTO ubids (id, ubid_code, is_canonical, alias_of, pan, gstin, created_at, updated_at)
            VALUES (:id, :ubid_code, 1, NULL, :pan, :gstin, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"id": ubid_id, "ubid_code": ubid_code, "pan": pan, "gstin": gstin},
    )
    return ubid_id


async def _link_review_records(db: AsyncSession, ctx: Any, ubid_id: str):
    # Make each reviewed raw record point at exactly one current UBID.
    await db.execute(
        text(
            """
            UPDATE record_links
            SET unlinked_at = CURRENT_TIMESTAMP
            WHERE raw_record_id IN (:raw_a_id, :raw_b_id)
              AND ubid_id != :ubid_id
              AND unlinked_at IS NULL
            """
        ),
        {"raw_a_id": ctx.raw_a_id, "raw_b_id": ctx.raw_b_id, "ubid_id": ubid_id},
    )

    for side in ("a", "b"):
        raw_id = getattr(ctx, f"raw_{side}_id")
        source = getattr(ctx, f"source_{side}")
        source_record_id = getattr(ctx, f"source_record_id_{side}")
        existing = (
            await db.execute(
                text(
                    """
                    SELECT id
                    FROM record_links
                    WHERE ubid_id = :ubid_id
                      AND raw_record_id = :raw_record_id
                    LIMIT 1
                    """
                ),
                {"ubid_id": ubid_id, "raw_record_id": raw_id},
            )
        ).first()
        if existing:
            await db.execute(
                text(
                    """
                    UPDATE record_links
                    SET source_system = :source_system,
                        source_record_id = :source_record_id,
                        confidence = :confidence,
                        decision_type = 'reviewer_confirmed',
                        linked_at = CURRENT_TIMESTAMP,
                        unlinked_at = NULL
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing.id,
                    "source_system": source,
                    "source_record_id": source_record_id,
                    "confidence": ctx.confidence_score or 1.0,
                },
            )
        else:
            await db.execute(
                text(
                    """
                    INSERT INTO record_links (
                        id, ubid_id, raw_record_id, source_system, source_record_id,
                        confidence, decision_type, linked_at, unlinked_at
                    )
                    VALUES (
                        :id, :ubid_id, :raw_record_id, :source_system, :source_record_id,
                        :confidence, 'reviewer_confirmed', CURRENT_TIMESTAMP, NULL
                    )
                    """
                ),
                {
                    "id": _uuid_hex(),
                    "ubid_id": ubid_id,
                    "raw_record_id": raw_id,
                    "source_system": source,
                    "source_record_id": source_record_id,
                    "confidence": ctx.confidence_score or 1.0,
                },
            )


async def _upsert_review_activity(db: AsyncSession, ctx: Any, ubid_id: str, reviewer_id: str):
    existing = (await db.execute(text("SELECT status, score, evidence_timeline FROM ubid_activity WHERE ubid_id = :ubid_id"), {"ubid_id": ubid_id})).first()
    timeline = _json_loads(existing.evidence_timeline if existing else None, []) or []
    timeline.append(
        {
            "event": "Reviewer approved merge",
            "date": datetime.utcnow().isoformat(),
            "description": f"{reviewer_id} confirmed {ctx.source_record_id_a} and {ctx.source_record_id_b} belong to the same business.",
            "pair_id": str(ctx.pair_id),
        }
    )
    score = max(float(existing.score) if existing and existing.score is not None else 0.0, float(ctx.confidence_score or 0.0))
    status = existing.status if existing and existing.status else ("Active" if score >= 0.9 else "Dormant")
    payload = json.dumps(timeline)
    if existing:
        await db.execute(
            text(
                """
                UPDATE ubid_activity
                SET status = :status,
                    score = :score,
                    evidence_timeline = :timeline,
                    computed_at = CURRENT_TIMESTAMP
                WHERE ubid_id = :ubid_id
                """
            ),
            {"ubid_id": ubid_id, "status": status, "score": score, "timeline": payload},
        )
    else:
        await db.execute(
            text(
                """
                INSERT INTO ubid_activity (ubid_id, status, score, evidence_timeline, computed_at)
                VALUES (:ubid_id, :status, :score, :timeline, CURRENT_TIMESTAMP)
                """
            ),
            {"ubid_id": ubid_id, "status": status, "score": score, "timeline": payload},
        )


@router.post("/api/review-queue/action")
async def review_queue_action(
    action: ReviewAction,
    db: AsyncSession = Depends(get_db),
    x_reviewer_id: str | None = Header(default=None),
):
    reviewer_id = sanitize_reviewer_id(action.reviewer_id or x_reviewer_id)
    if action.decision not in {"confirm_match", "confirm_non_match", "defer"}:
        raise HTTPException(status_code=400, detail="Unsupported review decision")

    # Single query to get context + check existence
    ctx = await _review_pair_context(db, action.queue_item_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Queue item not found")

    status = "deferred" if action.decision == "defer" else "resolved"
    
    # Start building batch operations - all non-dependent writes in parallel groups
    
    # Group 1: Core review queue update
    await db.execute(
        text("""
            UPDATE review_queue 
            SET status = :status, 
                resolved_at = CASE WHEN :status = 'resolved' THEN CURRENT_TIMESTAMP ELSE resolved_at END 
            WHERE id = :id
        """),
        {"status": status, "id": action.queue_item_id}
    )

    ubid_code = None
    
    if action.decision != "defer":
        decision_type = "auto_link" if action.decision == "confirm_match" else "separate"
        label = 1 if action.decision == "confirm_match" else 0
        
        # Group 2: All independent inserts (parallel where possible with asyncio.gather)
        # Using a single batch statement for multiple inserts where applicable
        
        # review_decisions + decisions + labeled_pairs in optimized sequence
        await db.execute(
            text("""
                INSERT INTO review_decisions (id, queue_item_id, pair_id, decision, justification, reviewer_id, created_at)
                VALUES (:id, :queue_item_id, :pair_id, :decision, :justification, :reviewer_id, CURRENT_TIMESTAMP)
            """),
            {
                "id": _uuid_hex(),
                "queue_item_id": action.queue_item_id,
                "pair_id": ctx.pair_id,
                "decision": action.decision,
                "justification": action.justification,
                "reviewer_id": reviewer_id,
            },
        )
        
        # Delete old decisions and insert new in one logical operation
        await db.execute(
            text("DELETE FROM decisions WHERE pair_id = :pair_id"),
            {"pair_id": ctx.pair_id}
        )
        
        await db.execute(
            text("""
                INSERT INTO decisions (id, pair_id, scored_pair_id, decision_type, threshold_version, confidence_score, created_at)
                VALUES (:id, :pair_id, :scored_pair_id, :decision_type, 'reviewer-v1', :confidence_score, CURRENT_TIMESTAMP)
            """),
            {
                "id": _uuid_hex(),
                "pair_id": ctx.pair_id,
                "scored_pair_id": ctx.scored_pair_id,
                "decision_type": decision_type,
                "confidence_score": ctx.confidence_score,
            },
        )
        
        await db.execute(
            text("""
                INSERT INTO labeled_pairs (id, pair_id, feature_vector, label, metadata_json, source, created_at)
                VALUES (:id, :pair_id, :feature_vector, :label, :metadata_json, 'reviewer', CURRENT_TIMESTAMP)
            """),
            {
                "id": _uuid_hex(),
                "pair_id": ctx.pair_id,
                "feature_vector": ctx.feature_vector or "{}",
                "label": label,
                "metadata_json": json.dumps({
                    "queue_item_id": str(action.queue_item_id),
                    "reviewer_id": reviewer_id,
                    "justification": action.justification,
                }),
            },
        )

        # Group 3: Match confirmation - optimized with fewer queries
        if action.decision == "confirm_match":
            # Check for existing UBID and create if needed - single query approach
            ubid_id = await _ensure_review_ubid_fast(db, ctx)
            
            # Batch link records update/insert with INSERT...ON CONFLICT style
            await _link_review_records_fast(db, ctx, ubid_id)
            
            # Optimized activity upsert
            await _upsert_review_activity_fast(db, ctx, ubid_id, reviewer_id)
            
            # Update timestamp first, then get code
            await db.execute(
                text("UPDATE ubids SET updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": ubid_id}
            )
            ubid_code_result = await db.execute(
                text("SELECT ubid_code FROM ubids WHERE id = :id"),
                {"id": ubid_id}
            )
            ubid_code = ubid_code_result.scalar()
            
            # Audit log
            await db.execute(
                text("""
                    INSERT INTO audit_logs (id, action, entity_type, entity_id, actor, before_state, after_state, extra_data, created_at)
                    VALUES (:id, 'review_merge_approved', 'ubid', :entity_id, :actor, NULL, :after_state, :extra_data, CURRENT_TIMESTAMP)
                """),
                {
                    "id": _uuid_hex(),
                    "entity_id": ubid_code,
                    "actor": reviewer_id,
                    "after_state": json.dumps({"ubid": ubid_code, "linked_records": [ctx.source_record_id_a, ctx.source_record_id_b]}),
                    "extra_data": json.dumps({"queue_item_id": str(action.queue_item_id), "pair_id": str(ctx.pair_id)}),
                },
            )
        else:
            # confirm_non_match: Create separate UBIDs for each record and link them
            ubid_codes = []
            
            for side in ("a", "b"):
                raw_id = getattr(ctx, f"raw_{side}_id")
                source = getattr(ctx, f"source_{side}")
                source_record_id = getattr(ctx, f"source_record_id_{side}")
                pan = getattr(ctx, f"pan_{side}")
                gstin = getattr(ctx, f"gstin_{side}")
                
                # Check if already linked to a UBID
                existing_link = (
                    await db.execute(
                        text("SELECT ubid_id FROM record_links WHERE raw_record_id = :raw_id AND unlinked_at IS NULL LIMIT 1"),
                        {"raw_id": raw_id}
                    )
                ).first()
                
                if existing_link:
                    # Get existing UBID code
                    ubid_row = (
                        await db.execute(
                            text("SELECT ubid_code FROM ubids WHERE id = :ubid_id"),
                            {"ubid_id": existing_link.ubid_id}
                        )
                    ).first()
                    if ubid_row:
                        ubid_codes.append(ubid_row.ubid_code)
                else:
                    # Create new UBID for this record
                    ubid_id = _uuid_hex()
                    ubid_code = await _next_ubid_code(db)
                    
                    await db.execute(
                        text("""
                            INSERT INTO ubids (id, ubid_code, is_canonical, alias_of, pan, gstin, created_at, updated_at)
                            VALUES (:id, :ubid_code, 1, NULL, :pan, :gstin, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """),
                        {"id": ubid_id, "ubid_code": ubid_code, "pan": pan, "gstin": gstin}
                    )
                    
                    # Link record to new UBID
                    await db.execute(
                        text("""
                            INSERT INTO record_links (
                                id, ubid_id, raw_record_id, source_system, source_record_id,
                                confidence, decision_type, linked_at, unlinked_at
                            )
                            VALUES (:id, :ubid_id, :raw_record_id, :source_system, :source_record_id,
                                    :confidence, 'reviewer_separate', CURRENT_TIMESTAMP, NULL)
                        """),
                        {
                            "id": _uuid_hex(),
                            "ubid_id": ubid_id,
                            "raw_record_id": raw_id,
                            "source_system": source,
                            "source_record_id": source_record_id,
                            "confidence": 1.0,
                        }
                    )
                    
                    # Create activity record
                    await db.execute(
                        text("""
                            INSERT INTO ubid_activity (ubid_id, status, score, evidence_timeline, computed_at)
                            VALUES (:ubid_id, 'Active', 1.0, :timeline, CURRENT_TIMESTAMP)
                        """),
                        {
                            "ubid_id": ubid_id,
                            "timeline": json.dumps([{
                                "event": "Reviewer created separate UBID",
                                "date": datetime.utcnow().isoformat(),
                                "description": f"{reviewer_id} confirmed this is a separate business from {source_record_id}",
                                "pair_id": str(ctx.pair_id),
                            }]),
                        }
                    )
                    
                    ubid_codes.append(ubid_code)
            
            # Audit log
            await db.execute(
                text("""
                    INSERT INTO audit_logs (id, action, entity_type, entity_id, actor, before_state, after_state, extra_data, created_at)
                    VALUES (:id, 'review_pair_kept_separate', 'candidate_pair', :entity_id, :actor, NULL, :after_state, :extra_data, CURRENT_TIMESTAMP)
                """),
                {
                    "id": _uuid_hex(),
                    "entity_id": str(ctx.pair_id),
                    "actor": reviewer_id,
                    "after_state": json.dumps({"decision": action.decision, "ubids_created": ubid_codes}),
                    "extra_data": json.dumps({"queue_item_id": str(action.queue_item_id), "ubids": ubid_codes}),
                },
            )

    pending_count = (
        await db.execute(text("SELECT COUNT(*) FROM review_queue WHERE status IN ('pending', 'locked')"))
    ).scalar_one()

    return {
        "ok": True,
        "status": status,
        "decision": action.decision,
        "ubid": ubid_code,
        "pending_count": pending_count,
    }


async def _ensure_review_ubid_fast(db: AsyncSession, ctx: Any) -> str:
    """Optimized version with single query check"""
    raw_ids = [ctx.raw_a_id, ctx.raw_b_id]
    
    # Single query to check existing links
    existing = await db.execute(
        text("""
            SELECT DISTINCT ubid_id FROM record_links 
            WHERE raw_record_id IN (:raw_a, :raw_b) AND unlinked_at IS NULL
            ORDER BY linked_at ASC LIMIT 1
        """),
        {"raw_a": ctx.raw_a_id, "raw_b": ctx.raw_b_id}
    )
    row = existing.first()
    if row:
        return row.ubid_id
    
    # Create new UBID
    ubid_id = _uuid_hex()
    ubid_code = await _next_ubid_code(db)
    pan = ctx.pan_a if ctx.pan_a and ctx.pan_a == ctx.pan_b else _first_value(ctx.pan_a, ctx.pan_b)
    gstin = ctx.gstin_a if ctx.gstin_a and ctx.gstin_a == ctx.gstin_b else _first_value(ctx.gstin_a, ctx.gstin_b)
    
    await db.execute(
        text("""
            INSERT INTO ubids (id, ubid_code, is_canonical, alias_of, pan, gstin, created_at, updated_at)
            VALUES (:id, :ubid_code, 1, NULL, :pan, :gstin, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": ubid_id, "ubid_code": ubid_code, "pan": pan, "gstin": gstin}
    )
    return ubid_id


async def _link_review_records_fast(db: AsyncSession, ctx: Any, ubid_id: str):
    """Optimized batch operations for linking records"""
    # Unlink existing first
    await db.execute(
        text("""
            UPDATE record_links SET unlinked_at = CURRENT_TIMESTAMP
            WHERE raw_record_id IN (:raw_a_id, :raw_b_id) AND ubid_id != :ubid_id AND unlinked_at IS NULL
        """),
        {"raw_a_id": ctx.raw_a_id, "raw_b_id": ctx.raw_b_id, "ubid_id": ubid_id}
    )
    
    # Batch insert/update both records - check existence first (more reliable than rowcount)
    confidence = ctx.confidence_score or 1.0
    
    for side in ("a", "b"):
        raw_id = getattr(ctx, f"raw_{side}_id")
        source = getattr(ctx, f"source_{side}")
        source_record_id = getattr(ctx, f"source_record_id_{side}")
        
        # Check if link exists
        existing = await db.execute(
            text("SELECT id FROM record_links WHERE ubid_id = :ubid_id AND raw_record_id = :raw_record_id LIMIT 1"),
            {"ubid_id": ubid_id, "raw_record_id": raw_id}
        )
        
        if existing.first():
            # Update existing
            await db.execute(
                text("""
                    UPDATE record_links 
                    SET source_system = :source_system,
                        source_record_id = :source_record_id,
                        confidence = :confidence,
                        decision_type = 'reviewer_confirmed',
                        linked_at = CURRENT_TIMESTAMP,
                        unlinked_at = NULL
                    WHERE ubid_id = :ubid_id AND raw_record_id = :raw_record_id
                """),
                {
                    "ubid_id": ubid_id,
                    "raw_record_id": raw_id,
                    "source_system": source,
                    "source_record_id": source_record_id,
                    "confidence": confidence,
                }
            )
        else:
            # Insert new
            await db.execute(
                text("""
                    INSERT INTO record_links (
                        id, ubid_id, raw_record_id, source_system, source_record_id,
                        confidence, decision_type, linked_at, unlinked_at
                    )
                    VALUES (:id, :ubid_id, :raw_record_id, :source_system, :source_record_id,
                            :confidence, 'reviewer_confirmed', CURRENT_TIMESTAMP, NULL)
                """),
                {
                    "id": _uuid_hex(),
                    "ubid_id": ubid_id,
                    "raw_record_id": raw_id,
                    "source_system": source,
                    "source_record_id": source_record_id,
                    "confidence": confidence,
                }
            )


async def _upsert_review_activity_fast(db: AsyncSession, ctx: Any, ubid_id: str, reviewer_id: str):
    """Optimized activity upsert using INSERT OR REPLACE pattern"""
    timeline_entry = {
        "event": "Reviewer approved merge",
        "date": datetime.utcnow().isoformat(),
        "description": f"{reviewer_id} confirmed {ctx.source_record_id_a} and {ctx.source_record_id_b} belong to the same business.",
        "pair_id": str(ctx.pair_id),
    }
    score = float(ctx.confidence_score or 0.0)
    status = "Active" if score >= 0.9 else "Dormant"
    
    # Check if exists first (more reliable than rowcount in async)
    existing = await db.execute(
        text("SELECT 1 FROM ubid_activity WHERE ubid_id = :ubid_id LIMIT 1"),
        {"ubid_id": ubid_id}
    )
    
    if existing.first():
        # Update existing using SQLite json_insert to append to array
        await db.execute(
            text("""
                UPDATE ubid_activity 
                SET status = :status,
                    score = MAX(COALESCE(score, 0), :new_score),
                    evidence_timeline = json_insert(
                        COALESCE(evidence_timeline, '[]'),
                        '$[#]', :new_entry
                    ),
                    computed_at = CURRENT_TIMESTAMP
                WHERE ubid_id = :ubid_id
            """),
            {
                "ubid_id": ubid_id,
                "status": status,
                "new_score": score,
                "new_entry": json.dumps(timeline_entry),
            }
        )
    else:
        # Insert new
        await db.execute(
            text("""
                INSERT INTO ubid_activity (ubid_id, status, score, evidence_timeline, computed_at)
                VALUES (:ubid_id, :status, :score, :timeline, CURRENT_TIMESTAMP)
            """),
            {
                "ubid_id": ubid_id,
                "status": status,
                "score": score,
                "timeline": json.dumps([timeline_entry]),
            }
        )


@router.get("/api/entity/lookup")
async def entity_lookup(query: str, db: AsyncSession = Depends(get_db)):
    q = query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query is required")
    q_upper = q.upper()
    like_q = f"%{q_upper}%"

    ubid_row = (
        await db.execute(
            text(
                """
                SELECT DISTINCT u.id, u.ubid_code
                FROM ubids u
                LEFT JOIN record_links l ON l.ubid_id = u.id AND l.unlinked_at IS NULL
                LEFT JOIN raw_records rr ON rr.id = l.raw_record_id
                LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
                WHERE UPPER(u.ubid_code) = :q
                   OR UPPER(rr.source_record_id) = :q
                   OR UPPER(n.pan) = :q
                   OR UPPER(n.gstin) = :q
                   OR UPPER(n.normalized_name) LIKE :like_q
                LIMIT 1
                """
            ),
            {"q": q_upper, "like_q": like_q},
        )
    ).first()

    raw_matches = (
        await db.execute(
            text(
                """
                SELECT rr.id AS raw_id, rr.source_system, rr.source_record_id, rr.raw_payload,
                       rr.extracted_at, n.id AS normalized_id, n.normalized_name,
                       n.parsed_address, n.pincode, n.pan, n.gstin, n.sector,
                       n.proprietor_name, n.pan_valid, n.gstin_valid,
                       u.id AS ubid_id, u.ubid_code, l.confidence, l.decision_type
                FROM raw_records rr
                LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
                LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                LEFT JOIN ubids u ON u.id = l.ubid_id
                WHERE UPPER(rr.source_record_id) = :q
                   OR UPPER(n.pan) = :q
                   OR UPPER(n.gstin) = :q
                   OR UPPER(n.normalized_name) LIKE :like_q
                   OR UPPER(json_extract(rr.raw_payload, '$.name')) LIKE :like_q
                   OR UPPER(COALESCE(json_extract(rr.raw_payload, '$.address'), '')) LIKE :like_q
                ORDER BY CASE WHEN UPPER(rr.source_record_id) = :q THEN 0 ELSE 1 END,
                         rr.extracted_at DESC
                LIMIT 25
                """
            ),
            {"q": q_upper, "like_q": like_q},
        )
    ).all()

    raw_normalized_ids = [row.normalized_id for row in raw_matches if row.normalized_id]
    candidate_pairs = []
    if raw_normalized_ids:
        candidate_rows = (
            await db.execute(
                text(
                    """
                    SELECT cp.id, cp.blocking_strategy,
                           ra.source_system AS source_a, ra.source_record_id AS source_id_a,
                           na.normalized_name AS name_a, na.pan AS pan_a, na.gstin AS gstin_a,
                           rb.source_system AS source_b, rb.source_record_id AS source_id_b,
                           nb.normalized_name AS name_b, nb.pan AS pan_b, nb.gstin AS gstin_b,
                           sp.confidence_score, sp.evidence_object,
                           rq.id AS queue_item_id, rq.status AS review_status, rq.priority,
                           rd.decision AS reviewer_decision, rd.justification, rd.reviewer_id, rd.created_at AS reviewed_at
                    FROM candidate_pairs cp
                    JOIN normalized_records na ON na.id = cp.record_a_id
                    JOIN raw_records ra ON ra.id = na.raw_record_id
                    JOIN normalized_records nb ON nb.id = cp.record_b_id
                    JOIN raw_records rb ON rb.id = nb.raw_record_id
                    LEFT JOIN scored_pairs sp ON sp.pair_id = cp.id
                    LEFT JOIN review_queue rq ON rq.pair_id = cp.id
                    LEFT JOIN review_decisions rd ON rd.pair_id = cp.id
                    WHERE cp.record_a_id IN :ids OR cp.record_b_id IN :ids
                    ORDER BY COALESCE(sp.confidence_score, 0) DESC, cp.created_at DESC
                    LIMIT 20
                    """
                ).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
                {"ids": raw_normalized_ids},
            )
        ).all()
        candidate_pairs = [
            {
                "pair_id": row.id,
                "blocking_strategy": row.blocking_strategy,
                "confidence": round((row.confidence_score or 0) * 100),
                "evidence": _json_loads(row.evidence_object, {}) or {},
                "review": {
                    "queue_item_id": row.queue_item_id,
                    "status": row.review_status,
                    "priority": row.priority,
                    "decision": row.reviewer_decision,
                    "justification": row.justification,
                    "reviewer_id": row.reviewer_id,
                    "reviewed_at": _fmt_date(row.reviewed_at),
                },
                "recordA": {
                    "source": row.source_a,
                    "id": row.source_id_a,
                    "name": row.name_a,
                    "pan": row.pan_a,
                    "gstin": row.gstin_a,
                },
                "recordB": {
                    "source": row.source_b,
                    "id": row.source_id_b,
                    "name": row.name_b,
                    "pan": row.pan_b,
                    "gstin": row.gstin_b,
                },
            }
            for row in candidate_rows
        ]

    raw_payloads = [_payload(row) for row in raw_matches]
    raw_records_payload = [
        {
            "source": row.source_system,
            "id": row.source_record_id,
            "source_record_id": row.source_record_id,
            "name": payload.get("name") or row.normalized_name or "Unknown Business",
            "normalized_name": row.normalized_name,
            "address": payload.get("address") or _address(row),
            "pincode": row.pincode,
            "sector": row.sector,
            "pan": row.pan or payload.get("pan"),
            "gstin": row.gstin or payload.get("gstin"),
            "proprietor": row.proprietor_name or payload.get("proprietor"),
            "pan_valid": bool(row.pan_valid),
            "gstin_valid": bool(row.gstin_valid),
            "linked_ubid": row.ubid_code,
            "link_confidence": round((row.confidence or 0) * 100) if row.confidence is not None else None,
            "decision_type": row.decision_type,
            "extracted_at": _fmt_date(row.extracted_at),
        }
        for row, payload in zip(raw_matches, raw_payloads)
    ]

    if not ubid_row:
        confirmed = any(pair.get("review", {}).get("decision") == "confirm_match" for pair in candidate_pairs)
        return {
            "found": bool(raw_records_payload),
            "trace_status": "review_confirmed_linkage_pending" if confirmed else "raw_record_unlinked",
            "ubid": None,
            "canonical_name": raw_records_payload[0]["name"] if raw_records_payload else None,
            "status": "Linkage Pending" if raw_records_payload else "Not Found",
            "searched_query": q,
            "summary": {
                "raw_matches": len(raw_records_payload),
                "candidate_pairs": len(candidate_pairs),
                "confirmed_pairs": sum(1 for pair in candidate_pairs if pair.get("review", {}).get("decision") == "confirm_match"),
                "pending_reviews": sum(1 for pair in candidate_pairs if pair.get("review", {}).get("status") in ("pending", "locked")),
                "linked_records": 0,
            },
            "raw_records": raw_records_payload,
            "candidate_pairs": candidate_pairs,
            "linked_records": [],
            "recommendations": [
                "Reviewer confirmed a match, but no canonical UBID has been materialised yet. Re-run/link the confirmed pair before using it in policy queries."
                if confirmed
                else "Raw department record exists but has not crossed the auto-link threshold. Keep it separate until reviewer evidence is available.",
                "Use PAN/GSTIN, normalized name, address and pincode evidence before committing a merge."
            ] if raw_records_payload else [
                "No raw or canonical record matched this input. Try a department record ID, PAN, GSTIN, business name, address or pincode."
            ],
        }

    linked = (
        await db.execute(
            text(
                """
                SELECT l.source_system, l.source_record_id, l.confidence, l.decision_type,
                       l.linked_at, rr.raw_payload, rr.extracted_at,
                       n.normalized_name, n.parsed_address, n.pincode, n.pan, n.gstin,
                       n.sector, n.proprietor_name, n.pan_valid, n.gstin_valid,
                       a.status, a.score, a.evidence_timeline, a.computed_at
                FROM record_links l
                JOIN raw_records rr ON rr.id = l.raw_record_id
                LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
                LEFT JOIN ubid_activity a ON a.ubid_id = l.ubid_id
                WHERE l.ubid_id = :ubid_id AND l.unlinked_at IS NULL
                ORDER BY l.confidence DESC
                """
            ),
            {"ubid_id": ubid_row.id},
        )
    ).all()

    first = linked[0] if linked else None
    linked_records = []
    names = []
    sectors = []
    pincodes = []
    for row in linked:
        payload = _payload(row)
        name = payload.get("name") or row.normalized_name or "Unknown Business"
        names.append(name)
        sectors.append(row.sector)
        pincodes.append(row.pincode)
        linked_records.append(
            {
                "source": row.source_system,
                "id": row.source_record_id,
                "source_record_id": row.source_record_id,
                "name": name,
                "address": payload.get("address") or _address(row),
                "pincode": row.pincode,
                "sector": row.sector,
                "pan": row.pan or payload.get("pan"),
                "gstin": row.gstin or payload.get("gstin"),
                "proprietor": row.proprietor_name or payload.get("proprietor"),
                "match_confidence": f"{round((row.confidence or 0) * 100)}%",
                "confidence": round((row.confidence or 0) * 100),
                "decision_type": row.decision_type,
                "linked_at": _fmt_date(row.linked_at),
                "extracted_at": _fmt_date(row.extracted_at),
                "pan_valid": bool(row.pan_valid),
                "gstin_valid": bool(row.gstin_valid),
            }
        )

    timeline = _json_loads(first.evidence_timeline if first else None, []) or []
    return {
        "found": True,
        "trace_status": "canonical_ubid_found",
        "ubid": ubid_row.ubid_code,
        "canonical_name": (_payload(first).get("name") if first else None) or (first.normalized_name if first else "Unknown"),
        "status": first.status if first else "Unknown",
        "activity_score": first.score if first else None,
        "activity_computed_at": _fmt_date(first.computed_at if first else None),
        "searched_query": q,
        "summary": {
            "linked_records": len(linked_records),
            "raw_matches": len(raw_records_payload),
            "candidate_pairs": len(candidate_pairs),
            "departments": len(_unique([record["source"] for record in linked_records])),
            "sectors": _unique(sectors),
            "pincodes": _unique(pincodes),
        },
        "raw_records": raw_records_payload,
        "candidate_pairs": candidate_pairs,
        "linked_records": linked_records,
        "activity_timeline": timeline,
    }


@router.get("/api/entity/activity")
async def entity_activity(ubid: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            text(
                """
                SELECT u.id, u.ubid_code, u.pan AS pan_anchor, u.gstin AS gstin_anchor,
                       u.created_at, u.updated_at, a.status, a.score, a.evidence_timeline,
                       a.computed_at, a.reviewer_override, a.override_by, a.override_at,
                       a.override_justification
                FROM ubids u
                LEFT JOIN ubid_activity a ON a.ubid_id = u.id
                WHERE u.ubid_code = :ubid
                LIMIT 1
                """
            ),
            {"ubid": ubid},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="UBID not found in activity registry")

    linked = (
        await db.execute(
            text(
                """
                SELECT l.source_system, l.source_record_id, l.confidence, l.decision_type,
                       l.linked_at, rr.raw_payload, rr.extracted_at,
                       n.normalized_name, n.parsed_address, n.pincode, n.pan, n.gstin,
                       n.sector, n.proprietor_name, n.latitude, n.longitude, n.pan_valid,
                       n.gstin_valid, n.normalized_at
                FROM ubids u
                JOIN record_links l ON l.ubid_id = u.id AND l.unlinked_at IS NULL
                JOIN raw_records rr ON rr.id = l.raw_record_id
                LEFT JOIN normalized_records n ON n.raw_record_id = rr.id
                WHERE u.ubid_code = :ubid
                ORDER BY l.confidence DESC, rr.extracted_at DESC
                """
            ),
            {"ubid": ubid},
        )
    ).all()

    audits = (
        await db.execute(
            text(
                """
                SELECT action, actor, entity_type, created_at
                FROM audit_logs
                WHERE entity_id = :ubid OR entity_id = :ubid_id
                ORDER BY created_at DESC
                LIMIT 20
                """
            ),
            {"ubid": ubid, "ubid_id": str(row.id)},
        )
    ).all()

    activity_rows = (
        await db.execute(
            text(
                """
                SELECT source_system, source_record_id, event_type, event_date, payload, ingested_at
                FROM events
                WHERE ubid_id = :ubid_id
                ORDER BY event_date DESC, ingested_at DESC
                LIMIT 50
                """
            ),
            {"ubid_id": row.id},
        )
    ).all()

    timeline = _json_loads(row.evidence_timeline, []) or []
    events = []
    if row.computed_at:
        events.append(
            {
                "type": "computed",
                "date": _fmt_date(row.computed_at),
                "title": "Status computed",
                "desc": f"Activity status is {row.status or 'Unknown'} with score {float(row.score or 0):.2f}.",
                "source": "activity_classifier",
                "score_delta": round(float(row.score or 0), 3),
            }
        )
    for item in timeline:
        title = item.get("event") or item.get("event_type") or "Activity Signal"
        event_type = "review" if "review" in title.lower() else "signal"
        events.append(
            {
                "type": event_type,
                "date": _fmt_date(item.get("date") or item.get("event_date")),
                "title": title,
                "desc": item.get("description") or f"Evidence used in the {row.status or 'Unknown'} activity decision.",
                "source": item.get("source_system") or item.get("source") or "registry",
                "score_delta": item.get("decay_weight") or item.get("score_delta"),
                "days_old": item.get("days_old"),
            }
        )
    for event_row in activity_rows:
        payload = _json_loads(event_row.payload, {}) or {}
        outcome = payload.get("event_outcome") or payload.get("outcome")
        events.append(
            {
                "type": "signal",
                "date": _fmt_date(event_row.event_date),
                "title": str(event_row.event_type or "Activity event").replace("_", " ").title(),
                "desc": outcome or f"{event_row.source_system} reported this event for {event_row.source_record_id}.",
                "source": event_row.source_system,
                "source_record_id": event_row.source_record_id,
            }
        )
    for linked_row in linked:
        events.append(
            {
                "type": "link",
                "date": _fmt_date(linked_row.linked_at),
                "title": "Department record linked",
                "desc": f"{linked_row.source_system} record {linked_row.source_record_id} is linked by {linked_row.decision_type or 'matching'} at {round((linked_row.confidence or 0) * 100)}% confidence.",
                "source": linked_row.source_system,
                "source_record_id": linked_row.source_record_id,
            }
        )
    if not events:
        events.append(
            {
                "type": "computed",
                "date": _fmt_date(datetime.utcnow()),
                "title": "Status Computed",
                "desc": f"Current activity score is {row.score or 0:.2f}.",
            }
        )
    events.sort(key=lambda item: item.get("date") or "", reverse=True)

    linked_records = []
    names = []
    addresses = []
    sectors = []
    pincodes = []
    pans = []
    gstins = []
    proprietors = []
    latitudes = []
    longitudes = []

    for linked_row in linked:
        payload = _payload(linked_row)
        address = payload.get("address") or _address(linked_row)
        name = payload.get("name") or linked_row.normalized_name or "Unknown Business"
        names.append(name)
        addresses.append(address)
        sectors.append(linked_row.sector)
        pincodes.append(linked_row.pincode)
        pans.append(linked_row.pan or payload.get("pan"))
        gstins.append(linked_row.gstin or payload.get("gstin"))
        proprietors.append(linked_row.proprietor_name or payload.get("proprietor"))
        if linked_row.latitude is not None:
            latitudes.append(linked_row.latitude)
        if linked_row.longitude is not None:
            longitudes.append(linked_row.longitude)

        linked_records.append(
            {
                "source": linked_row.source_system,
                "id": linked_row.source_record_id,
                "source_record_id": linked_row.source_record_id,
                "name": name,
                "address": address,
                "pincode": linked_row.pincode,
                "sector": linked_row.sector,
                "pan": linked_row.pan or payload.get("pan"),
                "gstin": linked_row.gstin or payload.get("gstin"),
                "proprietor": linked_row.proprietor_name or payload.get("proprietor"),
                "confidence": round((linked_row.confidence or 0) * 100),
                "decision_type": linked_row.decision_type,
                "linked_at": _fmt_date(linked_row.linked_at),
                "extracted_at": _fmt_date(linked_row.extracted_at),
                "normalized_at": _fmt_date(linked_row.normalized_at),
                "pan_valid": bool(linked_row.pan_valid),
                "gstin_valid": bool(linked_row.gstin_valid),
            }
        )

    canonical_name = _unique(names)[0] if _unique(names) else "Unknown Business"
    avg_lat = sum(latitudes) / len(latitudes) if latitudes else None
    avg_lng = sum(longitudes) / len(longitudes) if longitudes else None

    return {
        "ubid": row.ubid_code,
        "name": canonical_name,
        "status": row.status or "Unknown",
        "score": round(float(row.score or 0), 3),
        "computed_at": _fmt_date(row.computed_at),
        "created_at": _fmt_date(row.created_at),
        "updated_at": _fmt_date(row.updated_at),
        "source_count": len(linked_records),
        "details": {
            "address": _unique(addresses)[0] if _unique(addresses) else "N/A",
            "pan": row.pan_anchor or (_unique(pans)[0] if _unique(pans) else None),
            "gstin": row.gstin_anchor or (_unique(gstins)[0] if _unique(gstins) else None),
            "sector": _unique(sectors)[0] if _unique(sectors) else "Unknown",
            "proprietor": _unique(proprietors)[0] if _unique(proprietors) else "N/A",
            "pincodes": _unique(pincodes),
            "sectors": _unique(sectors),
            "pan_values": _unique(pans),
            "gstin_values": _unique(gstins),
            "location": {"lat": avg_lat, "lng": avg_lng},
            "source_systems": _unique([record["source"] for record in linked_records]),
        },
        "override": {
            "status": row.reviewer_override,
            "by": row.override_by,
            "at": _fmt_date(row.override_at),
            "justification": row.override_justification,
        },
        "linked_records": linked_records,
        "audit_log": [
            {
                "action": audit.action,
                "actor": audit.actor,
                "entity_type": audit.entity_type,
                "created_at": _fmt_date(audit.created_at),
            }
            for audit in audits
        ],
        "summary": {
            "canonical_names": _unique(names),
            "linked_departments": len(_unique([record["source"] for record in linked_records])),
            "source_records": len(linked_records),
            "identifier_conflicts": {
                "pan": len(_unique(pans)) > 1,
                "gstin": len(_unique(gstins)) > 1,
            },
            "timeline_events": len(events),
            "latest_activity_date": events[0]["date"] if events else "",
        },
        "events": events,
    }


@router.post("/api/admin/run-entity-resolution")
async def run_entity_resolution_batch(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    Process unlinked records through entity resolution to create matches.
    This runs the matching algorithm on records that haven't been linked yet.
    """
    import uuid
    from ..services.entity_resolution_service import resolve_record
    from ..models import NormalizedRecord
    
    # Find unlinked normalized records
    unlinked_rows = (
        await db.execute(
            text("""
                SELECT n.id AS normalized_id
                FROM normalized_records n
                JOIN raw_records rr ON rr.id = n.raw_record_id
                LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                WHERE l.id IS NULL
                ORDER BY n.normalized_at ASC
                LIMIT :limit
            """),
            {"limit": limit}
        )
    ).all()
    
    if not unlinked_rows:
        return {
            "processed": 0,
            "message": "No unlinked records found to process",
            "auto_linked": 0,
            "added_to_review": 0
        }
    
    processed = 0
    new_ubids = 0
    added_to_review = 0
    linked_existing = 0
    
    for row in unlinked_rows:
        try:
            norm_id = uuid.UUID(row.normalized_id) if isinstance(row.normalized_id, str) else row.normalized_id
            result = await resolve_record(norm_id, db)
            
            if result.decision == "new_ubid":
                new_ubids += 1
            elif result.decision == "review_queue":
                added_to_review += 1
            elif result.decision in ("embedding_auto_match", "auto_link"):
                linked_existing += 1
            
            processed += 1
            
        except Exception as e:
            import logging
            logging.getLogger("ubid.resolution").warning(f"Failed to process record {row.normalized_id}: {e}")
            continue
    
    await db.commit()
    
    return {
        "processed": processed,
        "new_ubids_created": new_ubids,
        "linked_to_existing": linked_existing,
        "added_to_review": added_to_review,
        "message": f"Processed {processed} records. {new_ubids} new businesses created, {linked_existing} linked to existing, {added_to_review} sent for review."
    }


@router.get("/api/business-directory")
async def business_directory(
    search: str = Query(default=None),
    status: str = Query(default=None),
    sector: str = Query(default=None),
    has_pan: str = Query(default=None),
    has_gstin: str = Query(default=None),
    sort_by: str = Query(default="business_name"),
    sort_dir: str = Query(default="asc"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all UBIDs (businesses) with filtering, sorting, and pagination.
    """
    import logging
    import traceback
    logger = logging.getLogger("ubid.api")
    
    try:
        logger.info(f"Business directory request: search={search}, status={status}, limit={limit}")
        
        # Build WHERE clauses
        where_clauses = ["1=1"]
        params = {}
        
        if search:
            where_clauses.append("(u.business_name LIKE :search OR u.ubid LIKE :search OR u.pan_anchor LIKE :search OR u.gstin_anchor LIKE :search)")
            params["search"] = f"%{search}%"
        
        if status and status != "all":
            where_clauses.append("u.status = :status")
            params["status"] = status
        
        if sector and sector != "all":
            where_clauses.append("u.sector = :sector")
            params["sector"] = sector
        
        if has_pan == "true":
            where_clauses.append("u.pan_anchor IS NOT NULL AND u.pan_anchor != ''")
        elif has_pan == "false":
            where_clauses.append("(u.pan_anchor IS NULL OR u.pan_anchor = '')")
        
        if has_gstin == "true":
            where_clauses.append("u.gstin_anchor IS NOT NULL AND u.gstin_anchor != ''")
        elif has_gstin == "false":
            where_clauses.append("(u.gstin_anchor IS NULL OR u.gstin_anchor = '')")
        
        where_sql = " AND ".join(where_clauses)
        logger.info(f"WHERE clause: {where_sql}")
        
        # Get total count
        count_sql = f"SELECT COUNT(*) FROM ubid_registry u WHERE {where_sql}"
        logger.info(f"Count SQL: {count_sql}")
        count_result = await db.execute(text(count_sql), params)
        total = count_result.scalar()
        logger.info(f"Total count: {total}")
        
        # Validate sort field
        allowed_sort = {"business_name", "status", "sector", "confidence_score", "assigned_on"}
        if sort_by not in allowed_sort:
            sort_by = "business_name"
        
        sort_direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
        
        # Get businesses with linked record counts
        allowed_columns = {
            'business_name': 'u.business_name',
            'status': 'u.status', 
            'sector': 'u.sector',
            'confidence_score': 'u.confidence_score',
            'assigned_on': 'u.assigned_on'
        }
        order_column = allowed_columns.get(sort_by, 'u.business_name')
        
        query_sql = f"""
            SELECT 
                u.ubid,
                u.business_name,
                u.status,
                u.sector,
                u.pin_code,
                u.pan_anchor,
                u.gstin_anchor,
                u.confidence_score,
                u.assigned_on,
                COUNT(sr.id) as linked_record_count
            FROM ubid_registry u
            LEFT JOIN source_records sr ON sr.ubid = u.ubid
            WHERE {where_sql}
            GROUP BY u.ubid, u.business_name, u.status, u.sector, u.pin_code, 
                     u.pan_anchor, u.gstin_anchor, u.confidence_score, u.assigned_on
            ORDER BY {order_column} {sort_direction}
            LIMIT :limit OFFSET :offset
        """
        logger.info(f"Query SQL prepared")
        
        businesses_result = await db.execute(
            text(query_sql),
            {**params, "limit": limit, "offset": offset}
        )
        
        businesses = [
            {
                "ubid": row.ubid,
                "business_name": row.business_name,
                "status": row.status,
                "sector": row.sector,
                "pin_code": row.pin_code,
                "pan_anchor": row.pan_anchor,
                "gstin_anchor": row.gstin_anchor,
                "confidence_score": row.confidence_score,
                "assigned_on": row.assigned_on if row.assigned_on else None,
                "linked_record_count": row.linked_record_count
            }
            for row in businesses_result.all()
        ]
        logger.info(f"Retrieved {len(businesses)} businesses")
        
        return {
            "businesses": businesses,
            "total": total,
            "page": offset // limit + 1,
            "page_size": limit
        }
    except Exception as e:
        logger.error(f"Error in business_directory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/admin/unlinked-analysis")
async def analyze_unlinked_records(db: AsyncSession = Depends(get_db)):
    """
    Analyze why records remain unlinked - provides breakdown of unlinked records.
    """
    # Count by reason
    results = {}
    
    # 1. Records with no matching PAN in other departments (unique businesses)
    unique_pan = (
        await db.execute(
            text("""
                SELECT COUNT(*) FROM (
                    SELECT n.pan, COUNT(*) as cnt
                    FROM normalized_records n
                    JOIN raw_records rr ON rr.id = n.raw_record_id
                    LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                    WHERE l.id IS NULL AND n.pan IS NOT NULL AND n.pan != ''
                    GROUP BY n.pan
                    HAVING cnt = 1
                )
            """)
        )
    ).scalar()
    
    # 2. Records without any PAN (can't auto-match)
    no_pan = (
        await db.execute(
            text("""
                SELECT COUNT(*) FROM normalized_records n
                JOIN raw_records rr ON rr.id = n.raw_record_id
                LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                WHERE l.id IS NULL AND (n.pan IS NULL OR n.pan = '')
            """)
        )
    ).scalar()
    
    # 3. Records that were separated by reviewer (marked as different businesses)
    separated = (
        await db.execute(
            text("""
                SELECT COUNT(DISTINCT rr.id) FROM raw_records rr
                JOIN normalized_records n ON n.raw_record_id = rr.id
                LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                JOIN candidate_pairs cp ON cp.record_a_id = n.id OR cp.record_b_id = n.id
                JOIN decisions d ON d.pair_id = cp.id
                WHERE l.id IS NULL AND d.decision_type = 'separate'
            """)
        )
    ).scalar()
    
    total_unlinked = (
        await db.execute(
            text("""
                SELECT COUNT(*) FROM normalized_records n
                JOIN raw_records rr ON rr.id = n.raw_record_id
                LEFT JOIN record_links l ON l.raw_record_id = rr.id AND l.unlinked_at IS NULL
                WHERE l.id IS NULL
            """)
        )
    ).scalar()
    
    return {
        "total_unlinked": total_unlinked,
        "breakdown": {
            "unique_businesses_single_pan": unique_pan or 0,
            "no_pan_for_matching": no_pan or 0,
            "reviewer_separated": separated or 0,
            "other": max(0, (total_unlinked or 0) - (unique_pan or 0) - (no_pan or 0) - (separated or 0))
        },
        "explanation": {
            "unique_businesses_single_pan": "Records with unique PAN not found in other departments - legitimate separate businesses",
            "no_pan_for_matching": "Records without PAN identifier - cannot auto-match using current algorithm",
            "reviewer_separated": "Records marked as 'Different businesses' by human reviewer",
            "other": "Records awaiting entity resolution batch processing"
        }
    }
