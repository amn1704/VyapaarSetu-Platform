import time
import re
from collections import Counter
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from ..database import get_db
from ..config import settings
from ..services.llm_service import llm_service
from ..services.sql_validator import sql_validator

router = APIRouter()

class QueryRequest(BaseModel):
    question: str


INDUSTRIAL_SECTORS = ("Engineering", "Electronics/IT", "Chemicals & Pharma")
STATUS_WORDS = {
    "active": ("Active",),
    "inactive": ("Dormant", "Closed"),
    "not active": ("Dormant", "Closed"),
    "dormant": ("Dormant",),
    "closed": ("Closed",),
}

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9][Z][A-Z0-9]\b", re.IGNORECASE)
PIN_PATTERN = re.compile(r"\b\d{6}\b")


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _has_word(question_lc: str, word: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", question_lc))


def _status_values(question_lc: str) -> tuple[str, ...] | None:
    if re.search(r"\bnot\s+active\b", question_lc):
        return STATUS_WORDS["not active"]
    for word in ("inactive", "dormant", "closed", "active"):
        if _has_word(question_lc, word):
            return STATUS_WORDS[word]
    return None


def _status_filter(alias: str, statuses: tuple[str, ...]) -> str:
    if len(statuses) == 1:
        return f"{alias}.status = '{statuses[0]}'"
    return f"{alias}.status IN ({_sql_list(statuses)})"


async def _scalar_int(db: AsyncSession, sql: str) -> int:
    result = await db.execute(text(sql))
    value = result.scalar()
    return int(value or 0)


def _business_select(where_clause: str = "", order_by: str = "u.business_name", limit: int = 25) -> str:
    where_sql = f"WHERE {where_clause}" if where_clause else ""
    return f"""
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    u.pan_anchor,
    u.gstin_anchor,
    ROUND(u.confidence_score, 3) AS confidence_score
FROM ubid_registry u
{where_sql}
ORDER BY {order_by}
LIMIT {limit}
"""


def _extract_pin(question_lc: str) -> str | None:
    pin_match = re.search(r"(?:pin\s*code|pincode|pin|postal\s*code|area\s*code)\D*(\d{6})", question_lc)
    if pin_match:
        return pin_match.group(1)
    bare_pin = PIN_PATTERN.search(question_lc)
    return bare_pin.group(0) if bare_pin else None


def _is_aggregate_question(question_lc: str) -> bool:
    return any(term in question_lc for term in (
        "how many", "count", "counts", "number of", "distribution", "summary",
        "most", "least", "top", "highest", "lowest", "by sector", "by area",
        "by pin", "by pincode", "by status", "each department", "each sector"
    ))


async def _distinct_values(db: AsyncSession, table: str, column: str, limit: int = 20) -> list[str]:
    result = await db.execute(text(
        f"SELECT DISTINCT {column} AS value FROM {table} "
        f"WHERE {column} IS NOT NULL AND {column} != '' "
        f"ORDER BY {column} LIMIT {limit}"
    ))
    return [str(row._mapping["value"]) for row in result.all()]


async def _runtime_schema_context(db: AsyncSession) -> str:
    """Give the local LLM live, non-PII schema/value hints."""
    try:
        statuses, sectors, sources, event_types, review_statuses = await _collect_runtime_values(db)
    except Exception:
        return ""

    return (
        "Live database hints. Use these exact values when they match the question:\n"
        f"- ubid_registry.status values: {', '.join(statuses) or 'Active, Dormant, Closed'}\n"
        f"- ubid_registry.sector values: {', '.join(sectors) or 'unknown'}\n"
        f"- source_records.source_system values: {', '.join(sources) or 'unknown'}\n"
        f"- activity_events.event_type values: {', '.join(event_types) or 'unknown'}\n"
        f"- review_queue.status values: {', '.join(review_statuses) or 'pending, locked, resolved'}\n"
    )


async def _collect_runtime_values(db: AsyncSession) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    statuses = await _distinct_values(db, "ubid_registry", "status")
    sectors = await _distinct_values(db, "ubid_registry", "sector")
    sources = await _distinct_values(db, "source_records", "source_system")
    event_types = await _distinct_values(db, "activity_events", "event_type")
    review_statuses = await _distinct_values(db, "review_queue", "status")
    return statuses, sectors, sources, event_types, review_statuses


def _identifier_lookup_sql(question: str) -> tuple[str | None, str]:
    pan_match = PAN_PATTERN.search(question)
    if pan_match:
        pan = pan_match.group(0).upper()
        return f"""
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    u.pan_anchor,
    u.gstin_anchor,
    ROUND(u.confidence_score, 3) AS confidence_score
FROM ubid_registry u
WHERE u.pan_anchor = '{pan}'
ORDER BY u.business_name
LIMIT 50
""", "deterministic-pan-lookup"

    gstin_match = GSTIN_PATTERN.search(question)
    if gstin_match:
        gstin = gstin_match.group(0).upper()
        return f"""
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    u.pan_anchor,
    u.gstin_anchor,
    ROUND(u.confidence_score, 3) AS confidence_score
FROM ubid_registry u
WHERE u.gstin_anchor = '{gstin}'
ORDER BY u.business_name
LIMIT 50
""", "deterministic-gstin-lookup"

    return None, ""


def _active_factory_no_inspection_sql(question: str) -> str | None:
    question_lc = question.lower()
    statuses = _status_values(question_lc)
    if not statuses or "inspection" not in question_lc:
        return None
    if not any(term in question_lc for term in ("factory", "factories", "industrial")):
        return None

    months_match = re.search(r"(?:last|past)\D*(\d{1,2})\D*months?", question_lc)
    pin_code = _extract_pin(question_lc) or "560058"
    months = int(months_match.group(1)) if months_match else 18
    sector_filter = _sql_list(INDUSTRIAL_SECTORS)

    return f"""
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    MAX(ae.event_date) AS last_inspection_date
FROM ubid_registry u
LEFT JOIN activity_events ae
    ON ae.ubid = u.ubid
   AND ae.event_type = 'inspection'
WHERE u.pin_code = '{pin_code}'
  AND {_status_filter("u", statuses)}
  AND u.sector IN ({sector_filter})
GROUP BY u.ubid, u.business_name, u.status, u.sector, u.pin_code
HAVING MAX(ae.event_date) < date('now', '-{months} months')
    OR MAX(ae.event_date) IS NULL
ORDER BY u.business_name
LIMIT 50
"""


def _status_by_pin_sql(question: str) -> str | None:
    question_lc = question.lower()
    if _is_aggregate_question(question_lc):
        return None
    statuses = _status_values(question_lc)
    if not statuses:
        return None

    pin_code = _extract_pin(question_lc)
    pin_filter = f"AND u.pin_code = '{pin_code}'" if pin_code else ""
    sector_filter = ""
    if any(term in question_lc for term in ("factory", "factories", "industrial")):
        sector_filter = f"AND u.sector IN ({_sql_list(INDUSTRIAL_SECTORS)})"

    return f"""
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    u.pan_anchor,
    u.gstin_anchor,
    ROUND(u.confidence_score, 3) AS confidence_score
FROM ubid_registry u
WHERE {_status_filter("u", statuses)}
  {pin_filter}
  {sector_filter}
ORDER BY u.confidence_score DESC, u.business_name
LIMIT 50
"""


def _status_area_summary_sql(question: str) -> str | None:
    question_lc = question.lower()
    statuses = _status_values(question_lc)
    if not statuses:
        return None
    if not any(term in question_lc for term in ("area", "areas", "pin", "pincode", "postal", "where", "location")):
        return None
    if not _is_aggregate_question(question_lc):
        return None

    sector_filter = ""
    if any(term in question_lc for term in ("factory", "factories", "industrial", "industry", "industrial unit")):
        sector_filter = f"AND u.sector IN ({_sql_list(INDUSTRIAL_SECTORS)})"

    return f"""
SELECT
    u.pin_code,
    COUNT(*) AS business_count,
    ROUND(AVG(u.confidence_score), 3) AS average_match_confidence
FROM ubid_registry u
WHERE {_status_filter("u", statuses)}
  AND u.pin_code IS NOT NULL
  {sector_filter}
GROUP BY u.pin_code
ORDER BY business_count DESC
LIMIT 50
"""


def _status_sector_summary_sql(question: str) -> str | None:
    question_lc = question.lower()
    statuses = _status_values(question_lc)
    if not statuses:
        return None
    if not any(term in question_lc for term in ("business type", "business types", "sector", "sectors", "industry", "industries", "type")):
        return None
    if not _is_aggregate_question(question_lc):
        return None

    return f"""
SELECT
    u.sector,
    COUNT(*) AS business_count,
    ROUND(AVG(u.confidence_score), 3) AS average_match_confidence
FROM ubid_registry u
WHERE {_status_filter("u", statuses)}
GROUP BY u.sector
ORDER BY business_count DESC
LIMIT 50
"""


def _anchor_gap_sql(question: str) -> str | None:
    question_lc = question.lower()
    if not ("pan" in question_lc and "gstin" in question_lc):
        return None
    if not any(term in question_lc for term in ("missing", "without", "no ", "not captured", "gap")):
        return None

    return """
SELECT
    u.ubid,
    u.business_name,
    u.status,
    u.sector,
    u.pin_code,
    u.pan_anchor,
    u.gstin_anchor,
    ROUND(u.confidence_score, 3) AS confidence_score
FROM ubid_registry u
WHERE u.pan_anchor IS NOT NULL
  AND u.pan_anchor != ''
  AND (u.gstin_anchor IS NULL OR u.gstin_anchor = '')
ORDER BY u.status, u.business_name
LIMIT 50
"""


def _review_queue_sql(question: str) -> str | None:
    question_lc = question.lower()
    if not any(term in question_lc for term in ("review", "ambiguous", "human", "queue")):
        return None

    return """
SELECT
    rq.id,
    rq.confidence_score,
    rq.priority,
    rq.status,
    rq.queued_at
FROM review_queue rq
WHERE rq.status IN ('pending', 'locked')
ORDER BY rq.priority DESC, rq.queued_at ASC
LIMIT 50
"""


def _sector_summary_sql(question: str) -> str | None:
    question_lc = question.lower()
    if not _is_aggregate_question(question_lc):
        return None
    if not any(term in question_lc for term in ("sector", "sectors", "distribution", "summary")):
        return None
    if not any(term in question_lc for term in ("active", "dormant", "closed", "business", "ubid")):
        return None

    return """
SELECT
    u.sector,
    u.status,
    COUNT(*) AS ubid_count,
    ROUND(AVG(u.confidence_score), 3) AS avg_link_confidence
FROM ubid_registry u
GROUP BY u.sector, u.status
ORDER BY ubid_count DESC
LIMIT 50
"""


def _source_system_summary_sql(question: str) -> str | None:
    question_lc = question.lower()
    if not any(term in question_lc for term in ("department", "source system", "source systems", "source records")):
        return None
    if not any(term in question_lc for term in ("most", "count", "counts", "summary", "how many", "distribution")):
        return None

    return """
SELECT
    sr.source_system,
    COUNT(*) AS record_count,
    COUNT(DISTINCT sr.ubid) AS linked_business_count,
    ROUND(AVG(sr.link_confidence), 3) AS average_match_confidence
FROM source_records sr
GROUP BY sr.source_system
ORDER BY record_count DESC
LIMIT 50
"""


def _template_sql(question: str) -> tuple[str | None, str]:
    identifier_sql, identifier_tag = _identifier_lookup_sql(question)
    if identifier_sql:
        return identifier_sql, identifier_tag

    template_checks = (
        (_active_factory_no_inspection_sql, "deterministic-factory-inspection"),
        (_anchor_gap_sql, "deterministic-identifier-anchor-gap"),
        (_review_queue_sql, "deterministic-review-queue"),
        (_status_area_summary_sql, "deterministic-status-area-summary"),
        (_status_sector_summary_sql, "deterministic-status-sector-summary"),
        (_sector_summary_sql, "deterministic-sector-status-summary"),
        (_source_system_summary_sql, "deterministic-department-record-summary"),
        (_status_by_pin_sql, "deterministic-status-pincode"),
    )
    for factory, tag in template_checks:
        sql = factory(question)
        if sql:
            return sql, tag
    return None, ""


def _empty_report(request: QueryRequest, sanitised_sql: str) -> str:
    if "activity_events" in sanitised_sql and "inspection" in sanitised_sql.lower():
        return (
            "No matching businesses were returned for this query. The filter was applied successfully, "
            "but the current local dataset has no qualifying rows for the selected pincode, status, "
            "sector, and inspection window. Try broadening the pincode or removing the sector/status "
            "constraint to explore the available data."
        )
    return (
        "No matching businesses were returned for this query. The SQL passed validation and executed "
        "successfully, but the current local dataset does not contain rows for the requested filters."
    )


def _result_report(rows: list[dict], row_count: int) -> str:
    if not rows:
        return ""

    if "confidence_score" in rows[0] and "priority" in rows[0]:
        avg_confidence = sum(float(row.get("confidence_score") or 0) for row in rows) / max(row_count, 1)
        return (
            f"The reviewer queue returned {row_count} ambiguous linkage decisions. "
            f"Average confidence is {avg_confidence:.2f}, so these records should stay reversible until a reviewer confirms or rejects the match. "
            "Recommended action: resolve the highest-priority pairs first so the feedback loop can improve future UBID matching."
        )

    if "ubid_count" in rows[0]:
        top = rows[0]
        return (
            f"The grouped query returned {row_count} sector-status bands from the Unified Business Identifier registry. "
            f"The largest band is {top.get('sector')} / {top.get('status')} with {top.get('ubid_count')} UBIDs. "
            "Recommended action: compare these bands with department coverage before drawing policy conclusions."
        )

    if "source_system" in rows[0] and ("record_count" in rows[0] or "count" in rows[0]):
        top = rows[0]
        count_key = "record_count" if "record_count" in rows[0] else "count"
        top_source = top.get("source_system") or "the leading department"
        top_count = top.get(count_key)
        return (
            f"The query compared {row_count} department systems. "
            f"The largest contributor is {top_source} with {top_count} records. "
            "Recommended action: use this distribution to spot high-volume departments and check whether lower-volume departments need data feed follow-up."
        )

    if "business_count" in rows[0] and ("pin_code" in rows[0] or "sector" in rows[0]):
        dimension = "PIN code" if "pin_code" in rows[0] else "business type"
        top_label = rows[0].get("pin_code") if "pin_code" in rows[0] else rows[0].get("sector")
        return (
            f"The query returned {row_count} {dimension} groups. "
            f"The largest group is {top_label} with {rows[0].get('business_count')} businesses. "
            "Recommended action: review the ranking table and focus follow-up on the highest-volume groups first."
        )

    if len(rows[0]) <= 4 and any(key in rows[0] for key in ("count", "record_count", "ubid_count", "total")):
        first_key = next(iter(rows[0]))
        count_key = next((key for key in rows[0] if key in ("count", "record_count", "ubid_count", "total")), None)
        if count_key:
            return (
                f"The query returned {row_count} grouped result rows. "
                f"The top result is {rows[0].get(first_key)} with {rows[0].get(count_key)} records. "
                "Recommended action: review the returned table for the full ranking and use the filters shown above when sharing the result."
            )

    pin_counts = Counter(row.get("pin_code") for row in rows if row.get("pin_code"))
    sector_counts = Counter(row.get("sector") for row in rows if row.get("sector"))
    status_counts = Counter(row.get("status") for row in rows if row.get("status"))
    missing_inspections = sum(
        1 for row in rows
        if "last_inspection_date" in row and not row.get("last_inspection_date")
    )

    pin_text = ", ".join(f"{pin} ({count})" for pin, count in pin_counts.most_common(3)) or "the selected area"
    sector_text = ", ".join(f"{sector} ({count})" for sector, count in sector_counts.most_common(3)) or "the selected sectors"
    status_text = ", ".join(f"{status} ({count})" for status, count in status_counts.most_common(3)) or "the requested statuses"

    inspection_sentence = ""
    if missing_inspections:
        inspection_sentence = (
            f" {missing_inspections} returned records have no inspection date in the local activity-events table, "
            "so they satisfy the no-recent-inspection condition."
        )

    sentences = [f"The query returned {row_count} matching records."]
    if pin_counts:
        sentences.append(f"The strongest geographic concentration is {pin_text}.")
    if sector_counts:
        sentences.append(f"The leading business type mix is {sector_text}.")
    if status_counts:
        sentences.append(f"The returned status distribution is {status_text}.")
    if "business_name" in rows[0]:
        first_name = rows[0].get("business_name") or "the first returned business"
        sentences.append(f"The first returned business is {first_name}.")
    if inspection_sentence:
        sentences.append(inspection_sentence.strip())
    sentences.append("Recommended action: review the returned table and open any business ID that needs case-level follow-up.")
    return " ".join(sentences)


def _generic_result_report(question: str, rows: list[dict], row_count: int) -> str:
    if not rows:
        return (
            "No matching records were returned. The query ran successfully, but the local dataset "
            "does not contain records for the requested filters."
        )
    return _result_report(rows, row_count)


async def _zero_result_assist(request: QueryRequest, db: AsyncSession) -> dict:
    """When exact SQL returns nothing, diagnose filters and fetch useful alternatives."""
    question_lc = request.question.lower()
    pin_code = _extract_pin(question_lc)
    statuses = _status_values(question_lc)
    industrial = any(term in question_lc for term in ("factory", "factories", "industrial", "industry", "industrial unit"))

    facts: list[str] = []
    related_sql = ""
    related_rows: list[dict] = []
    related_title = "Related records"

    status_clause = _status_filter("u", statuses) if statuses else ""
    sector_clause = f"u.sector IN ({_sql_list(INDUSTRIAL_SECTORS)})" if industrial else ""
    requested_filters = " AND ".join(part for part in (status_clause, sector_clause) if part)

    if pin_code:
        pin_count = await _scalar_int(db, f"SELECT COUNT(*) FROM ubid_registry u WHERE u.pin_code = '{pin_code}'")
        if pin_count == 0:
            facts.append(f"PIN code {pin_code} is not present in the local dataset.")
        else:
            facts.append(f"PIN code {pin_code} has {pin_count} businesses before applying all filters.")

    if requested_filters:
        matching_filter_count = await _scalar_int(db, f"SELECT COUNT(*) FROM ubid_registry u WHERE {requested_filters}")
        filter_label = "requested status/business-type filters"
        facts.append(f"The {filter_label} match {matching_filter_count} businesses across all PIN codes.")

    if pin_code and requested_filters:
        same_pin_sql = _business_select(f"u.pin_code = '{pin_code}'", "u.status, u.sector, u.business_name", 25)
        _, _, same_pin_rows = await _run_sql(db, same_pin_sql)
        if same_pin_rows:
            related_sql = same_pin_sql
            related_rows = same_pin_rows
            related_title = f"Businesses available in PIN {pin_code}"

    if not related_rows and requested_filters:
        group_sql = f"""
SELECT
    u.pin_code,
    COUNT(*) AS business_count,
    SUM(CASE WHEN u.status = 'Active' THEN 1 ELSE 0 END) AS active_count,
    SUM(CASE WHEN u.status = 'Dormant' THEN 1 ELSE 0 END) AS dormant_count,
    SUM(CASE WHEN u.status = 'Closed' THEN 1 ELSE 0 END) AS closed_count
FROM ubid_registry u
WHERE {requested_filters}
  AND u.pin_code IS NOT NULL
GROUP BY u.pin_code
ORDER BY business_count DESC
LIMIT 25
"""
        _, _, group_rows = await _run_sql(db, group_sql)
        if group_rows:
            related_sql = group_sql
            related_rows = group_rows
            related_title = "PIN codes with matching businesses"

    if not related_rows and pin_code:
        related_sql = _business_select("", "u.pin_code, u.business_name", 25)
        _, _, related_rows = await _run_sql(db, related_sql)
        related_title = "Sample businesses from the local dataset"

    report = "No exact matches were found."
    if facts:
        report += " " + " ".join(facts)
    if related_rows:
        report += f" I found {len(related_rows)} related rows under: {related_title}. Use these to adjust the PIN code, status, or business type and run the exact search again."
    else:
        report += " I could not find a useful relaxed result set in the available local data."

    return {
        "answer_mode": "no_exact_match_with_related" if related_rows else "no_exact_match",
        "related_title": related_title,
        "related_sql": sql_validator.sanitise(related_sql) if related_sql else "",
        "related_results": related_rows,
        "related_row_count": len(related_rows),
        "diagnostics": facts,
        "report": report,
    }


def _sqlite_compat_sql(sql: str) -> str:
    """Adapt common PostgreSQL drift to the local SQLite read model."""
    normalised = re.sub(r"\bILIKE\b", "LIKE", sql, flags=re.IGNORECASE)
    normalised = re.sub(r"\bu\.pincode\b", "u.pin_code", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\bsr\.pincode\b", "sr.pin_code", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\bu\.name\b", "u.business_name", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\bsr\.department\b", "sr.source_system", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\bsr\.source\b", "sr.source_system", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\bae\.date\b", "ae.event_date", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"\brq\.created_at\b", "rq.queued_at", normalised, flags=re.IGNORECASE)
    normalised = re.sub(
        r"(\w+)\.sector\s+LIKE\s+'%factor(?:y|ies)%'",
        lambda match: f"{match.group(1)}.sector IN ({_sql_list(INDUSTRIAL_SECTORS)})",
        normalised,
        flags=re.IGNORECASE,
    )
    normalised = re.sub(
        r"NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s+months?'",
        r"date('now', '-\1 months')",
        normalised,
        flags=re.IGNORECASE,
    )
    normalised = re.sub(
        r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s+months?'",
        r"date('now', '-\1 months')",
        normalised,
        flags=re.IGNORECASE,
    )

    normalised = re.sub(
        r"NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+activity_events\s+(\w+)\s+WHERE\s+(.*?)\s+AND\s+MAX\(\1\.event_date\)\s*<\s*(date\('now',\s*'-\d+\s+months'\))\s*\)",
        lambda match: (
            "NOT EXISTS (SELECT 1 FROM activity_events "
            f"{match.group(1)} WHERE {match.group(2)} "
            f"AND {match.group(1)}.event_date >= {match.group(3)})"
        ),
        normalised,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return normalised


def _execution_sql(sql: str) -> str:
    if settings.DATABASE_URL.startswith("sqlite"):
        return _sqlite_compat_sql(sql)
    return sql


async def _run_sql(db: AsyncSession, sql: str) -> tuple[str, str, list[dict]]:
    sanitised_sql = sql_validator.ensure_limit(sql)
    is_safe, reason = sql_validator.validate(sanitised_sql)
    if not is_safe:
        raise ValueError(reason)

    executable_sql = _execution_sql(sanitised_sql)
    result = await db.execute(text(executable_sql))
    rows = [dict(row._mapping) for row in result.all()]
    return sanitised_sql, executable_sql, rows


async def _generate_and_execute_with_repair(request: QueryRequest, db: AsyncSession) -> tuple[str, list[dict], str]:
    schema_context = await _runtime_schema_context(db)
    previous_sql = None
    previous_error = None

    for attempt in range(3):
        generated_sql = await llm_service.text_to_sql(
            request.question,
            schema_context=schema_context,
            previous_sql=previous_sql,
            previous_error=previous_error,
        )
        try:
            sanitised_sql, _, rows = await _run_sql(db, generated_sql)
            tag = "llama3.1-local" if attempt == 0 else f"llama3.1-local-repaired-{attempt}"
            return sanitised_sql, rows, tag
        except (ValueError, SQLAlchemyError, Exception) as exc:
            previous_sql = generated_sql
            previous_error = str(exc)
            if attempt == 2:
                raise

    raise RuntimeError("Could not generate executable SQL")


@router.post("")
@router.post("/")
@router.post("/nl")
async def natural_language_query(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    """
    Translates a natural language question into SQL, executes it, 
    and generates a summary report.
    """
    start_time = time.time()
    
    # 1. Text-to-SQL. High-confidence deterministic routes cover sensitive
    # identifier lookups and common civic questions. Everything else goes
    # through the schema-grounded local LLM with execution-time repair.
    generated_sql, template_tag = _template_sql(request.question)
    if generated_sql:
        try:
            sanitised_sql, _, rows = await _run_sql(db, generated_sql)
            version_tag = template_tag
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database execution error: {e}")
    else:
        if not settings.ENABLE_LLM:
            raise HTTPException(
                status_code=503,
                detail="AI query generation is disabled. Set ENABLE_LLM=true on a local backend with Ollama to answer this question.",
            )
        try:
            sanitised_sql, rows, version_tag = await _generate_and_execute_with_repair(request, db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"SQL validation failed: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not answer this query after repair attempts: {e}")

    row_count = len(rows)

    # 2. Report Generation. If exact results are empty, run a lightweight
    # diagnostic/relaxation pass so the officer still gets a useful answer.
    assist = {}
    if rows:
        report = _generic_result_report(request.question, rows, row_count)
        answer_mode = "exact"
    else:
        assist = await _zero_result_assist(request, db)
        report = assist.get("report") or _empty_report(request, sanitised_sql)
        answer_mode = assist.get("answer_mode", "no_exact_match")

    execution_ms = int((time.time() - start_time) * 1000)
    
    return {
        "sql": sanitised_sql,
        "generated_sql": sanitised_sql,
        "results": rows,
        "report": report,
        "summary_report": report,
        "row_count": row_count,
        "exact_row_count": row_count,
        "answer_mode": answer_mode,
        "related_title": assist.get("related_title", ""),
        "related_sql": assist.get("related_sql", ""),
        "related_results": assist.get("related_results", []),
        "related_row_count": assist.get("related_row_count", 0),
        "diagnostics": assist.get("diagnostics", []),
        "execution_ms": execution_ms,
        "version_tag": version_tag
    }
