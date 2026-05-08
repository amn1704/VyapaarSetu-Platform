from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..config import settings
from ..services.llm_service import llm_service
from ..services.pseudonymiser import pseudonymiser

router = APIRouter()

class ReviewSummaryRequest(BaseModel):
    evidence: dict

@router.post("/summarise")
async def summarise_review(request: ReviewSummaryRequest):
    """
    Generates an AI-driven summary and recommendation for human reviewers.
    Treats PII with strict pseudonymisation.
    """
    if not settings.ENABLE_LLM:
        raise HTTPException(status_code=503, detail="AI review summaries are disabled. Set ENABLE_LLM=true to use Ollama locally.")

    # 1. Pseudonymise all PII in evidence dict
    try:
        pseudonymised_evidence = pseudonymiser.pseudonymise_record(request.evidence)
        # Handle nested records if present in the evidence object
        if "record_a" in pseudonymised_evidence:
             pseudonymised_evidence["record_a"] = pseudonymiser.pseudonymise_record(pseudonymised_evidence["record_a"])
        if "record_b" in pseudonymised_evidence:
             pseudonymised_evidence["record_b"] = pseudonymiser.pseudonymise_record(pseudonymised_evidence["record_b"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pseudonymisation failure: {e}")

    # 2. Call LLM for summary
    try:
        summary = await llm_service.summarise_evidence(pseudonymised_evidence)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM failure: {e}")

    # Extract confidence (optional: LLM might return it in text as per prompt)
    # The prompt says: "Final line: Confidence score: X/1.0"
    confidence_score = 0.0
    if "Confidence score:" in summary:
        try:
            score_part = summary.split("Confidence score:")[-1].strip()
            confidence_score = float(score_part.split("/")[0])
        except:
            pass

    recommendation = "MATCH" if "Lean towards MATCH" in summary else "NON-MATCH"

    return {
        "summary": summary,
        "confidence_score": confidence_score,
        "recommendation": recommendation
    }
