"""Capability Registry — catálogo central de capacidades do CRIS OS."""

from core.capability.models import (
    Capability,
    CapabilityContext,
    CapabilityRegistration,
    CapabilityRegistryStats,
    CapabilityResult,
    CapabilityStatus,
    ConflictStrategy,
    FallbackStrategy,
    HealthStatus,
    ResolveContext,
    ResolvedCapability,
)
from core.capability.errors import (
    CapabilityConflictError,
    CapabilityError,
    CapabilityNotFoundError,
    CapabilityPermissionError,
    CapabilityTimeoutError,
    CapabilityUnavailableError,
    InvalidVersionError,
)
from core.capability.health import HealthTracker
from core.capability.metrics import CapabilityMetrics, MetricsCollector, MetricsSnapshot
from core.capability.registry import CapabilityRegistry
from core.capability.semver import match as semver_match, Version
from core.domain.events import Event, EventType

__all__ = [
    # Models
    "Capability",
    "CapabilityContext",
    "CapabilityRegistration",
    "CapabilityRegistryStats",
    "CapabilityResult",
    "CapabilityStatus",
    "ConflictStrategy",
    "FallbackStrategy",
    "HealthStatus",
    "ResolveContext",
    "ResolvedCapability",
    # Errors
    "CapabilityConflictError",
    "CapabilityError",
    "CapabilityNotFoundError",
    "CapabilityPermissionError",
    "CapabilityTimeoutError",
    "CapabilityUnavailableError",
    "InvalidVersionError",
    # Core
    "CapabilityRegistry",
    "CapabilityMetrics",
    "HealthTracker",
    "MetricsCollector",
    "MetricsSnapshot",
    # Semver
    "semver_match",
    "Version",
    # Events
    "Event",
    "EventType",
]