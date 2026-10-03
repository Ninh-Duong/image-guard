"""
core/types.py - Structured Data Types for Guardrails, Profiling & Database Persistence.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class GuardResult:
    allowed: bool
    hash: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    flagged_pending_review: bool = False
    reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        return {k: v for k, v in res.items() if v is not None}


@dataclass
class ActivityInsight:
    category: str
    label: str
    confidence: float


@dataclass
class SocialContext:
    type: str  # "solo", "duo", "group", "crowd", "no_people"
    people_count: int
    description: str


@dataclass
class UserProfileInsight:
    primary_interest: str
    interest_label: str
    confidence: float
    lifestyle_tags: List[str]
    detected_activities: List[Dict[str, Any]]
    social_context: Dict[str, Any]
    scene_summary: str
    suggested_note_caption: str
    # Unified Merged Tags & Search Keywords for DB & Downstream AI Analysis
    merged_tags: List[str] = field(default_factory=list)
    search_keywords: List[str] = field(default_factory=list)
    tag_weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessResponse:
    guard: GuardResult
    profile: Optional[UserProfileInsight] = None
    execution_time_ms: float = 0.0
    trace_id: Optional[str] = None
    db_record: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "guard": self.guard.to_dict(),
            "profile": self.profile.to_dict() if self.profile else None,
            "merged_tags": self.profile.merged_tags if self.profile else [],
            "db_record": self.db_record,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "trace_id": self.trace_id,
        }
        # Backward-compatible top-level keys for existing mobile clients
        data["allowed"] = self.guard.allowed
        data["hash"] = self.guard.hash
        data["scores"] = self.guard.scores
        data["violations"] = self.guard.violations
        data["flagged_pending_review"] = self.guard.flagged_pending_review
        if self.guard.reason:
            data["reason"] = self.guard.reason
        if self.guard.error:
            data["error"] = self.guard.error
        if self.profile:
            data["scene"] = {
                "summary": self.profile.scene_summary,
                "people_count": self.profile.social_context.get("people_count", 0),
                "scene_tag": self.profile.interest_label,
            }
        return data
