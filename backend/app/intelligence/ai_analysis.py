"""AI output model for the assistive AI layer (Phase 3-B1).

``AIIncidentAnalysis`` is the validated shape a FUTURE provider must return.
Every field here is AI-OWNED: summary, evidence interpretation, possible
causes, investigation actions, response options, uncertainty, safety notes.

Deterministic authoritative values (``risk_score``, ``severity``,
``incident_type``, ``confidence``, timestamps, population) are deliberately NOT
fields of this model: the AI cannot redefine them. ``incident_id`` is present
only as a correlation/reference identifier, validated by the same stable format
the deterministic engine produces.

The model treats its input as untrusted generated content: constraints reject
invalid payloads (missing fields, out-of-range values, bad references, a
"confirmed" cause framing, non-advisory response options) instead of silently
clamping them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.intelligence.ai_context import INCIDENT_ID_PATTERN


class PossibleCause(BaseModel):
    """A hypothesis framed as possible/plausible - never confirmed."""

    cause: str = Field(min_length=1)
    framing: Literal["possible", "plausible", "consistent"] = "consistent"
    supporting_evidence: list[str] = Field(default_factory=list)
    notes: str | None = None


class InvestigationAction(BaseModel):
    """An advisory, evidence-grounded operator investigation step."""

    action: str = Field(min_length=1)
    category: str | None = None
    priority: int = Field(ge=1, le=100)
    rationale: str = Field(min_length=1)


class ResponseOption(BaseModel):
    """A suggestion for a human operator; never an autonomous command."""

    recommendation: str = Field(min_length=1)
    priority: int | None = Field(default=None, ge=1, le=100)
    rationale: str | None = None
    advisory: Literal[True] = True


class Uncertainty(BaseModel):
    """Explicit uncertainty communication."""

    supported: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    additional_information: list[str] = Field(default_factory=list)


class AIIncidentAnalysis(BaseModel):
    """Validated, structured output of the future AI provider."""

    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    summary: str = Field(min_length=1)
    evidence_interpretation: str = Field(min_length=1)
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    investigation_actions: list[InvestigationAction] = Field(default_factory=list)
    response_options: list[ResponseOption] = Field(default_factory=list)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    safety_notes: list[str] = Field(default_factory=list)