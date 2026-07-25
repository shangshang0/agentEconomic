"""Pure fail-closed policy helpers for audited technical world recovery."""

from __future__ import annotations


PROVIDER_ERROR_TRIP_REASONS = {
    "consecutive_provider_errors",
    "provider_error_rate",
}


def provider_error_refund_substring(
    trip_reason: object, configured_substring: str | None
) -> str | None:
    """Apply terminal provider-error matching only to provider-error trips.

    Deadlocks and runtime stalls reconcile and refund genuinely outstanding
    calls, but must not require or refund an unrelated historical quota error.
    Provider-error trips retain strict configured matching and fail closed when
    no attributable terminal matches.
    """
    if trip_reason not in PROVIDER_ERROR_TRIP_REASONS:
        return None
    return configured_substring


def require_provider_error_refund_match(
    effective_substring: str | None, attributable_count: int
) -> None:
    """Fail closed when a provider-error trip cannot justify its refund."""
    if effective_substring and attributable_count < 1:
        raise RuntimeError("rollback source has no matching attributable provider errors")
