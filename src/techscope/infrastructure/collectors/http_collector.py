"""The HTTP source of signals: one homepage fetch, one document parse, then every extractor.

A soft-blocked response still goes through the extractors: its headers are real evidence, and a
Cloudflare challenge proves Cloudflare.
"""

import asyncio
import logging
from itertools import chain

from techscope.application.ports.signal_collector import CollectionResult
from techscope.domain.models import CollectionFailure, Signal
from techscope.infrastructure.extractors.observed_response import build_observed_response
from techscope.infrastructure.extractors.registry import EXTRACTORS
from techscope.infrastructure.http.homepage_fetcher import HomepageFetcher
from techscope.infrastructure.http.models import FetchFailure, FetchResult

logger = logging.getLogger(__name__)

COLLECTOR_NAME = "http"


class HttpSignalCollector:
    """Fetches the homepage once and turns the response into signals."""

    name = COLLECTOR_NAME

    def __init__(self, fetcher: HomepageFetcher) -> None:
        self._fetcher = fetcher

    async def collect(self, domain: str) -> CollectionResult:
        outcome = await self._fetcher.fetch(domain)

        if isinstance(outcome, FetchFailure):
            logger.warning(
                "%s could not be fetched: %s (%s)", domain, outcome.reason, outcome.detail
            )

            return CollectionResult(signals=(), failure=_build_failure(outcome))

        # Parsing and scanning a large page is CPU-bound. On the event loop it blocks every
        # other domain, and a blocked loop pushes concurrent DNS attempts past their timeout:
        # measured, one full scan in four lost real records that way while DNS alone never did.
        signals = await asyncio.to_thread(_extract_signals, outcome)
        logger.debug("%s produced %d signals", domain, len(signals))

        return CollectionResult(
            signals=signals, failure=_decide_block_failure_or_none(domain, outcome)
        )


def _extract_signals(result: FetchResult) -> tuple[Signal, ...]:
    observed = build_observed_response(result)

    return tuple(chain.from_iterable(extractor(observed) for extractor in EXTRACTORS))


def _build_failure(failure: FetchFailure) -> CollectionFailure:
    return CollectionFailure(collector=COLLECTOR_NAME, reason=failure.reason, detail=failure.detail)


def _decide_block_failure_or_none(domain: str, result: FetchResult) -> CollectionFailure | None:
    """A block is recorded, but the headers that came with it were still collected."""
    if result.block_reason is None:
        return None

    logger.warning("%s soft-blocked the scan: %s", domain, result.block_reason)

    return CollectionFailure(
        collector=COLLECTOR_NAME,
        reason=result.block_reason,
        detail=f"status {result.status_code} from {result.final_url}",
    )
