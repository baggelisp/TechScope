"""Scanning one domain: run every collector, match what they saw, report what went wrong.

The use case knows nothing about HTTP or DNS. It sees collectors behind a port, and every
collector is isolated so that one failing source can never cost the domain the others' evidence.
"""

import asyncio
import logging

from techscope.application.ports.signal_collector import CollectionResult, SignalCollector
from techscope.domain.enums import FailureReasonEnum
from techscope.domain.matcher import match_signals
from techscope.domain.models import (
    CollectionFailure,
    DomainScanResult,
    FingerprintIndex,
    Signal,
)

logger = logging.getLogger(__name__)


class ScanDomainUseCase:
    """Turns one domain into one result. Never raises for a domain-level problem."""

    def __init__(
        self, collectors: tuple[SignalCollector, ...], fingerprint_index: FingerprintIndex
    ) -> None:
        self._collectors = collectors
        self._fingerprint_index = fingerprint_index

    async def execute(self, domain: str) -> DomainScanResult:
        """Collect, match, report.

        ``duration_seconds`` stays absent here: whoever ran this owns the clock and fills it in.
        """
        outcomes = await asyncio.gather(
            *(collector.collect(domain) for collector in self._collectors),
            return_exceptions=True,
        )
        signals: list[Signal] = []
        failures: list[CollectionFailure] = []
        observed_urls: list[str] = []

        for collector, outcome in zip(self._collectors, outcomes, strict=True):
            recoverable = _check_outcome_is_recoverable_or_raise(outcome)
            result = _decide_collection_result(collector.name, domain, recoverable)
            signals.extend(result.signals)

            if result.failure is not None:
                failures.append(result.failure)

            if result.observed_url is not None:
                observed_urls.append(result.observed_url)

        detections = match_signals(tuple(signals), self._fingerprint_index)

        return DomainScanResult(
            domain=domain,
            detections=detections,
            failures=tuple(failures),
            observed_url=_decide_observed_url_or_none(observed_urls),
            duration_seconds=None,
        )


def _check_outcome_is_recoverable_or_raise(
    outcome: CollectionResult | BaseException,
) -> CollectionResult | Exception:
    """Cancellation and other BaseExceptions belong to the caller, not to this domain."""
    if isinstance(outcome, CollectionResult | Exception):
        return outcome

    raise outcome


def _decide_collection_result(
    collector_name: str, domain: str, outcome: CollectionResult | Exception
) -> CollectionResult:
    """A collector is contracted not to raise.

    If one does anyway, that is the collector's failure rather than the domain's.
    """
    if isinstance(outcome, CollectionResult):
        return outcome

    logger.warning("collector %s raised for %s: %r", collector_name, domain, outcome)
    failure = CollectionFailure(
        collector=collector_name,
        reason=FailureReasonEnum.COLLECTOR_ERROR,
        detail=repr(outcome),
    )

    return CollectionResult(signals=(), failure=failure)


def _decide_observed_url_or_none(observed_urls: list[str]) -> str | None:
    """Only the HTTP collector reads a page, so there is at most one to report."""
    if len(observed_urls) == 0:
        return None

    return observed_urls[0]
