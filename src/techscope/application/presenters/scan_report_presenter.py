"""Turning a scan report into JSON-ready records.

One place decides these shapes, so the file the CLI writes and the body the HTTP API returns
cannot drift apart.
"""

from techscope.domain.models import (
    CollectionFailure,
    Detection,
    DomainScanResult,
    Evidence,
    Fingerprint,
    ScanReport,
)
from techscope.domain.text_safety import strip_invisible_characters

ROUNDED_PLACES = 3


def present_summary(report: ScanReport) -> dict[str, list[str]]:
    """The shape the assignment asks for: a domain, and the technologies found on it."""
    return {result.domain: list(result.list_technology_names()) for result in report.results}


def present_fingerprints(fingerprints: tuple[Fingerprint, ...]) -> dict[str, object]:
    """What a service will match against, so a caller can show what was looked for.

    Sorted by name, like every other list this scanner emits: a caller should not have to know
    what order a database happened to be written in.
    """
    ordered = sorted(fingerprints, key=_read_fingerprint_name)
    technologies = [_present_fingerprint(fingerprint) for fingerprint in ordered]

    return {"count": len(technologies), "technologies": technologies}


def _read_fingerprint_name(fingerprint: Fingerprint) -> str:
    return fingerprint.name


def _present_fingerprint(fingerprint: Fingerprint) -> dict[str, object]:
    channels = {pattern.channel.value for pattern in fingerprint.patterns}

    return {
        "name": fingerprint.name,
        "channels": sorted(channels),
        "implies": list(fingerprint.implies),
    }


def present_details(report: ScanReport) -> dict[str, object]:
    """Everything behind the summary: why each technology was reported, and what went wrong.

    The summary alone cannot tell a domain that runs nothing detectable from one that refused to
    answer — both are an empty list. This is where that difference lives.
    """
    return {
        "summary": _present_run_summary(report),
        "domains": [_present_domain(result) for result in report.results],
    }


def _present_run_summary(report: ScanReport) -> dict[str, object]:
    troubled = report.list_troubled_results()

    return {
        "domains": len(report.results),
        "detections": report.count_detections(),
        "domains_with_problems": len(troubled),
        "duration_seconds": round(report.duration_seconds, 3),
    }


def _present_domain(result: DomainScanResult) -> dict[str, object]:
    return {
        "domain": result.domain,
        "observed_url": result.observed_url,
        "duration_seconds": _decide_rounded_seconds_or_none(result.duration_seconds),
        "technologies": list(result.list_technology_names()),
        "detections": [_present_detection(detection) for detection in result.detections],
        "problems": [_present_failure(failure) for failure in result.failures],
    }


def _present_detection(detection: Detection) -> dict[str, object]:
    return {
        "name": detection.name,
        "confidence": detection.confidence,
        "evidence": [_present_evidence(evidence) for evidence in detection.evidence],
    }


def _present_evidence(evidence: Evidence) -> dict[str, object]:
    return {
        "channel": evidence.channel.value,
        "key": evidence.key,
        "pattern": evidence.pattern_source,
        "matched": evidence.matched_text,
    }


def _present_failure(failure: CollectionFailure) -> dict[str, object]:
    """The detail quotes the target that failed, and a caller chose that text."""
    return {
        "collector": failure.collector,
        "reason": failure.reason.value,
        "detail": strip_invisible_characters(failure.detail),
    }


def _decide_rounded_seconds_or_none(duration_seconds: float | None) -> float | None:
    """A domain cut short by the deadline has no duration, and null says so."""
    if duration_seconds is None:
        return None

    return round(duration_seconds, ROUNDED_PLACES)
