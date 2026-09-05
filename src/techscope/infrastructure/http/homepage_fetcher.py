"""Fetching one homepage, politely and within a hard time bound.

One request per host, ever: the homepage, following redirects. The scanner identifies itself
honestly and detects a block rather than trying to evade it.
"""

import asyncio
import logging
from importlib.metadata import version

import httpx

from techscope.domain.enums import FailureReasonEnum
from techscope.infrastructure.http.models import FetchFailure, FetchResult
from techscope.infrastructure.http.soft_block import decide_block_reason_or_none

logger = logging.getLogger(__name__)

PROJECT_URL = "https://github.com/baggelisp/TechScope"
USER_AGENT = f"TechScope/{version('techscope')} (+{PROJECT_URL})"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 10.0
TOTAL_TIMEOUT_SECONDS = 15.0
RETRY_BACKOFF_SECONDS = 0.5
MAXIMUM_REDIRECTS = 5
MAXIMUM_BODY_BYTES = 2 * 1024 * 1024
FALLBACK_ENCODING = "utf-8"
DECODE_ERROR_POLICY = "replace"

# Only these justify trying again, or trying the other scheme: the host never answered.
TRANSIENT_REASONS = frozenset({FailureReasonEnum.CONNECTION_FAILED, FailureReasonEnum.TIMEOUT})


def build_client() -> httpx.AsyncClient:
    """The client this fetcher expects.

    Redirect following, the redirect cap, the timeouts and the honest identification belong
    together: splitting them between here and the composition root is how one quietly goes
    missing. The composition root still owns the client's lifetime.
    """
    timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT_SECONDS,
        read=READ_TIMEOUT_SECONDS,
        write=READ_TIMEOUT_SECONDS,
        pool=CONNECT_TIMEOUT_SECONDS,
    )

    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=MAXIMUM_REDIRECTS,
        headers=REQUEST_HEADERS,
    )


class HomepageFetcher:
    """Fetches ``https://<domain>/``, falling back to http only if the connection itself failed."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        retry_backoff_seconds: float,
        total_timeout_seconds: float,
    ) -> None:
        self._client = client
        self._retry_backoff_seconds = retry_backoff_seconds
        self._total_timeout_seconds = total_timeout_seconds

    async def fetch(self, domain: str) -> FetchResult | FetchFailure:
        """Never raises. The whole attempt, retries and scheme fallback included, is bounded here.

        The per-request httpx timeouts are the inner bound; this is the outer guarantee, and it
        is the only thing that holds against a host that drips bytes forever.
        """
        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                return await self._fetch_with_scheme_fallback(domain)
        except TimeoutError:
            logger.warning(
                "%s exceeded the %.1fs fetch budget", domain, self._total_timeout_seconds
            )

            return FetchFailure(
                reason=FailureReasonEnum.TIMEOUT,
                detail=f"no response within {self._total_timeout_seconds:.1f}s",
            )

    async def _fetch_with_scheme_fallback(self, domain: str) -> FetchResult | FetchFailure:
        secure_outcome = await self._attempt_with_retry(f"https://{domain}/")

        if isinstance(secure_outcome, FetchResult):
            return secure_outcome

        if secure_outcome.reason is not FailureReasonEnum.CONNECTION_FAILED:
            return secure_outcome

        logger.info("%s did not accept an https connection, trying http once", domain)

        return await self._attempt_with_retry(f"http://{domain}/")

    async def _attempt_with_retry(self, url: str) -> FetchResult | FetchFailure:
        first_outcome = await self._attempt(url)

        if isinstance(first_outcome, FetchResult):
            return first_outcome

        if first_outcome.reason not in TRANSIENT_REASONS:
            return first_outcome

        logger.debug("retrying %s after %s", url, first_outcome.reason)
        await asyncio.sleep(self._retry_backoff_seconds)

        return await self._attempt(url)

    async def _attempt(self, url: str) -> FetchResult | FetchFailure:
        try:
            async with self._client.stream("GET", url) as response:
                raw_body = await _read_capped_body(response)
                body = _decide_body_text(response, raw_body)

                return _build_fetch_result(response, body)
        except httpx.InvalidURL as error:
            # Not an HTTPError, so it would otherwise escape and break the no-raise contract.
            return FetchFailure(reason=FailureReasonEnum.INVALID_HOST, detail=str(error))
        except httpx.TooManyRedirects as error:
            return FetchFailure(reason=FailureReasonEnum.TOO_MANY_REDIRECTS, detail=str(error))
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            return FetchFailure(reason=FailureReasonEnum.CONNECTION_FAILED, detail=str(error))
        except httpx.TimeoutException as error:
            return FetchFailure(reason=FailureReasonEnum.TIMEOUT, detail=str(error))
        except httpx.HTTPError as error:
            return FetchFailure(reason=FailureReasonEnum.INVALID_RESPONSE, detail=str(error))


async def _read_capped_body(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    collected = 0

    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
        collected += len(chunk)

        if collected >= MAXIMUM_BODY_BYTES:
            break

    return b"".join(chunks)[:MAXIMUM_BODY_BYTES]


def _build_fetch_result(response: httpx.Response, body: str) -> FetchResult:
    headers = tuple((name.lower(), value) for name, value in response.headers.multi_items())

    return FetchResult(
        final_url=str(response.url),
        status_code=response.status_code,
        headers=headers,
        body=body,
        block_reason=decide_block_reason_or_none(response.status_code, body),
    )


def _decide_body_text(response: httpx.Response, raw_body: bytes) -> str:
    encoding = _decide_encoding(response)

    try:
        return raw_body.decode(encoding, errors=DECODE_ERROR_POLICY)
    except LookupError:
        return raw_body.decode(FALLBACK_ENCODING, errors=DECODE_ERROR_POLICY)


def _decide_encoding(response: httpx.Response) -> str:
    declared = response.charset_encoding

    if declared is None:
        return FALLBACK_ENCODING

    return declared
