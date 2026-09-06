"""The endpoints. Thin on purpose: normalise, delegate, present.

The domains arrive from a third party, which is the difference between this driver and the CLI
and the reason feature 10 had to land first: every fetch this triggers is checked against the
target guard, on the initial request and on every redirect hop.
"""

import logging

from fastapi import APIRouter, Request

from techscope.application.presenters.scan_report_presenter import (
    present_details,
    present_fingerprints,
)
from techscope.bootstrap import ScanService
from techscope.domain.domain_list import build_domain_list_from_lines
from techscope.presentation.api.errors import ApiError
from techscope.presentation.api.schemas import (
    MAXIMUM_DOMAIN_LENGTH,
    MAXIMUM_SUBMITTED_DOMAINS,
    ScanRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

SERVICE_STATE_ATTRIBUTE = "scan_service"
HEALTHY_STATUS = "ok"


@router.get("/health")
async def read_health() -> dict[str, str]:
    """Whether this process is serving. Deliberately says nothing about the internet."""
    return {"status": HEALTHY_STATUS}


@router.get("/fingerprints")
async def read_fingerprints(request: Request) -> dict[str, object]:
    """What the service will match against, so the web app can show what it looked for."""
    service = _read_service(request)

    return present_fingerprints(service.fingerprints)


@router.post("/scans")
async def create_scan(request: Request, scan_request: ScanRequest) -> dict[str, object]:
    """Scan the submitted domains and answer with the shape the CLI writes to `--details`."""
    domains = _decide_domains_or_raise(scan_request.domains)
    service = _read_service(request)
    logger.info("scanning %d domains for an API caller", len(domains))
    report = await service.scan_domains.execute(domains)

    return present_details(report)


def _decide_domains_or_raise(submitted: list[str]) -> tuple[str, ...]:
    """The same normalisation the CLI applies to a file, applied to a request body.

    Sharing it is the point: a domain the CLI would refuse must not become a fetch here because
    a different parser was more generous. The body itself is bounded before it reaches here;
    these are the bounds on what it says.
    """
    if len(submitted) == 0:
        raise ApiError.invalid_request("submit at least one domain")

    if len(submitted) > MAXIMUM_SUBMITTED_DOMAINS:
        raise ApiError.invalid_request(
            f"a scan may cover at most {MAXIMUM_SUBMITTED_DOMAINS} domains, "
            f"and {len(submitted)} were submitted"
        )

    if _has_an_oversized_entry(submitted):
        raise ApiError.invalid_request(
            f"a domain may be at most {MAXIMUM_DOMAIN_LENGTH} characters"
        )

    domains = build_domain_list_from_lines(submitted)

    if len(domains) == 0:
        raise ApiError.invalid_request("none of the submitted entries is a usable domain")

    return domains


def _has_an_oversized_entry(submitted: list[str]) -> bool:
    return any(len(entry) > MAXIMUM_DOMAIN_LENGTH for entry in submitted)


def _read_service(request: Request) -> ScanService:
    """The service the lifespan wired. Absent only if a request beat the lifespan to it."""
    service = getattr(request.app.state, SERVICE_STATE_ATTRIBUTE, None)

    if not isinstance(service, ScanService):
        raise ApiError.unavailable("the scanning service is not ready")

    return service
