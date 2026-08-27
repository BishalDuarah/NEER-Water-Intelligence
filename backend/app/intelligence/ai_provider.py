"""AI provider abstraction (Phase 3-B1).

``AIProvider`` is the ONLY contract the rest of NEER depends on for AI, and it
is deliberately network-free. A concrete provider will be implemented in Phase
3-B2 and substituted here without touching the deterministic engine or the
context/analysis models.

Error contract (raised by concrete providers in later phases, consumed by NEER
fallback logic — defined here so callers can distinguish failure modes):

- ``ProviderUnavailableError`` -      service down / not reachable;
- ``ProviderTimeoutError`` -          provider did not respond in time;
- ``MalformedAIResponseError`` -      response present but not structured;
- ``AIValidationError`` -             structured validation of the output failed.

There is no network, HTTP, SDK import, credential, or prompt execution in this
module. ``AIProvider.generate_analysis`` performs no I/O by contract.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.intelligence.ai_analysis import AIIncidentAnalysis
from app.intelligence.ai_context import IncidentAIContext


class AIProviderError(Exception):
    """Base class for AI provider failures."""


class ProviderUnavailableError(AIProviderError):
    """Provider service is down or unreachable."""


class ProviderTimeoutError(AIProviderError):
    """Provider did not respond within the allowed window."""


class MalformedAIResponseError(AIProviderError):
    """Provider returned content that is not structured as expected."""


class AIValidationError(AIProviderError):
    """Provider output failed structured validation."""


@runtime_checkable
class AIProvider(Protocol):
    """Generate a validated AIIncidentAnalysis for an IncidentAIContext.

    Implementations perform their I/O inside this single method; NEER depends
    on this interface only. ``generate_analysis`` must return a fully valid
    ``AIIncidentAnalysis`` or raise an ``AIProviderError`` subclass.
    """

    def generate_analysis(self, context: IncidentAIContext) -> AIIncidentAnalysis:
        """Return a validated AIIncidentAnalysis for ``context``."""