"""The HTTP source of signals: one homepage fetch, then the response extractors.

The extractors arrive with backlog item 5. Until then this collector proves the fetch path and
reports what the fetch found, which is already enough to record every block and failure.
"""

import logging

from techscope.application.ports.signal_collector import CollectionResult
from techscope.domain.models import CollectionFailure
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

        return CollectionResult(signals=(), failure=_decide_block_failure_or_none(domain, outcome))


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
