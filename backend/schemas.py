from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional

class _SchemaBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class ReviewerIdentityMixin(_SchemaBase):
    reviewer_id: Optional[str] = Field(default="system", alias="reviewerId")

class ReviewRecord(_SchemaBase):
    id: str
    source: str
    name: str
    address: str
    pan: Optional[str] = "N/A"
    gstin: Optional[str] = "N/A"
    pincode: Optional[str] = "N/A"
    sector: Optional[str] = "Unknown"


class ReviewEvidence(_SchemaBase):
    band: str
    signals: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    feature_scores: List[Dict[str, Any]] = Field(default_factory=list)
    matches: Dict[str, bool] = Field(default_factory=dict)
    token_overlap: Dict[str, Any] = Field(default_factory=dict)
    raw: Dict[str, Any] = Field(default_factory=dict)


class ReviewQueueItem(_SchemaBase):
    id: str
    confidence_score: int
    priority: int = 0
    queued_at: Optional[str] = None
    blocking_strategy: Optional[str] = None
    record_a: ReviewRecord = Field(..., alias="recordA")
    record_b: ReviewRecord = Field(..., alias="recordB")
    evidence: ReviewEvidence
    model: Dict[str, Any] = Field(default_factory=dict)

class RawRecordItem(_SchemaBase):
    id: str
    source: str
    name: str
    address: str
    pan: Optional[str] = None
    date: str

class DashboardStats(_SchemaBase):
    metrics: Dict[str, int]
    charts: Dict[str, List[Dict[str, Any]]]

class EntityLookupResponse(_SchemaBase):
    ubid: str
    name: str
    status: str
    lastInspection: Optional[str] = None
    evidence: List[str]

class IngestRequest(_SchemaBase):
    source_system: str
    source_record_id: str
    payload: Dict[str, Any]

class ReviewActionRequest(ReviewerIdentityMixin):
    queue_item_id: str = Field(..., alias="queueItemId")
    decision: str  # confirm_match | confirm_non_match | defer | needs_data
    justification: Optional[str] = None

class OverrideActivityRequest(ReviewerIdentityMixin):
    ubid_id: str
    status: str  # Active | Dormant | Closed
    justification: str

class ThresholdUpdateRequest(_SchemaBase):
    auto_link_min: float = Field(..., ge=0.0, le=1.0)
    review_min: float = Field(..., ge=0.0, le=1.0)
    deployed_by: str

class ApproveWeightsRequest(_SchemaBase):
    model_version: str
    approved_by: str

class EventIngestRequest(_SchemaBase):
    source_system: str
    source_record_id: str
    event_type: str
    event_date: str  # ISO date YYYY-MM-DD
    payload: Optional[Dict[str, Any]] = None

class QueryRequest(_SchemaBase):
    question: str

class ActivityClassifyRequest(_SchemaBase):
    ubid: str
    include_llm_explanation: bool = True

class ReverseLinkRequest(ReviewerIdentityMixin):
    record_link_id: str
    reason: str = Field(..., min_length=10)

class MatchRunRequest(_SchemaBase):
    norm_record_id: Optional[str] = None
    source_record_id: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
