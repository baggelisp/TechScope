"""The HTTP driver, over the same core the CLI drives.

Every test injects a wired service built from fake collectors, so nothing here touches the
network and what is exercised is the driver: what it accepts, what it refuses, and what it says
when something goes wrong.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from techscope import bootstrap
from techscope.application.ports.signal_collector import CollectionResult
from techscope.application.use_cases.scan_domain import ScanDomainUseCase
from techscope.application.use_cases.scan_domains import ScanDomainsUseCase
from techscope.domain.enums import BlockReasonEnum, ChannelEnum
from techscope.domain.matcher import build_fingerprint_index
from techscope.domain.models import CollectionFailure, ScanReport, Signal
from techscope.presentation.api.app import create_app
from techscope.presentation.api.schemas import MAXIMUM_SUBMITTED_DOMAINS
from tests.support.builders import build_test_fingerprint, build_test_pattern

STRIPE = build_test_fingerprint(
    "Stripe", (build_test_pattern(ChannelEnum.HEADER, key_source="x-stripe-.*"),)
)
CLOUDFLARE = build_test_fingerprint(
    "Cloudflare", (build_test_pattern(ChannelEnum.HEADER, key_source="cf-ray"),)
)


class FakeCollector:
    """Answers with the signals a test asked for, and nothing else."""

    name = "fake"

    def __init__(self, failing_domains: tuple[str, ...] = ()) -> None:
        self._failing_domains = failing_domains

    async def collect(self, domain: str) -> CollectionResult:
        if domain in self._failing_domains:
            failure = CollectionFailure(
                collector=self.name, reason=BlockReasonEnum.FORBIDDEN, detail="403 from the host"
            )

            return CollectionResult(signals=(), failure=failure)

        signal = Signal(channel=ChannelEnum.HEADER, value="abc-DFW", key="cf-ray")

        return CollectionResult(signals=(signal,), failure=None)


def build_fake_service(failing_domains: tuple[str, ...] = ()) -> bootstrap.ScanService:
    index = build_fingerprint_index((STRIPE, CLOUDFLARE))
    scan_domain = ScanDomainUseCase(
        collectors=(FakeCollector(failing_domains),), fingerprint_index=index
    )

    return bootstrap.ScanService(
        scan_domains=ScanDomainsUseCase(
            scan_domain=scan_domain, concurrency=5, deadline_seconds=5.0
        ),
        fingerprints=(STRIPE, CLOUDFLARE),
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Entered as a context manager, which is what runs the application's lifespan."""
    with TestClient(create_app(build_fake_service())) as entered:
        yield entered


def test_health_reports_the_service_is_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fingerprints_lists_what_the_service_will_match_against(client: TestClient) -> None:
    response = client.get("/fingerprints")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [technology["name"] for technology in body["technologies"]] == ["Cloudflare", "Stripe"]


def test_a_scan_returns_the_same_shape_the_cli_writes_to_its_details_file(
    client: TestClient,
) -> None:
    response = client.post("/scans", json={"domains": ["example.com"]})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["domains"] == 1
    assert [entry["domain"] for entry in body["domains"]] == ["example.com"]
    assert body["domains"][0]["technologies"] == ["Cloudflare"]


def test_a_scan_keeps_the_submitted_order_and_drops_duplicates(client: TestClient) -> None:
    submitted = ["stripe.com", "https://www.example.com/pricing", "stripe.com"]

    response = client.post("/scans", json={"domains": submitted})

    assert [entry["domain"] for entry in response.json()["domains"]] == [
        "stripe.com",
        "example.com",
    ]


def test_a_domain_that_fails_still_answers_two_hundred_with_the_failure_recorded() -> None:
    """One bad domain is a result, not an error: the assignment's rule, over HTTP."""
    service = build_fake_service(failing_domains=("blocked.example",))

    with TestClient(create_app(service)) as failing:
        response = failing.post("/scans", json={"domains": ["blocked.example"]})

    assert response.status_code == 200
    entry = response.json()["domains"][0]
    assert entry["technologies"] == []
    assert entry["problems"][0]["reason"] == BlockReasonEnum.FORBIDDEN.value


def test_an_empty_domain_list_is_refused(client: TestClient) -> None:
    response = client.post("/scans", json={"domains": []})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_a_list_of_nothing_usable_is_refused(client: TestClient) -> None:
    """Distinct from an empty list: these were sent, and none of them is a domain."""
    response = client.post("/scans", json={"domains": ["#comment", "   ", "..."]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_more_domains_than_the_cap_are_refused(client: TestClient) -> None:
    too_many = [f"host{number}.example" for number in range(MAXIMUM_SUBMITTED_DOMAINS + 1)]

    response = client.post("/scans", json={"domains": too_many})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_exactly_the_cap_is_accepted(client: TestClient) -> None:
    at_the_cap = [f"host{number}.example" for number in range(MAXIMUM_SUBMITTED_DOMAINS)]

    response = client.post("/scans", json={"domains": at_the_cap})

    assert response.status_code == 200
    assert response.json()["summary"]["domains"] == MAXIMUM_SUBMITTED_DOMAINS


def test_a_body_that_is_not_the_expected_shape_is_refused_as_typed_json(
    client: TestClient,
) -> None:
    """A validation error must come back in our shape, never as FastAPI's own."""
    response = client.post("/scans", json={"domain": "example.com"})

    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == "invalid_request"


def test_an_unknown_route_answers_typed_json(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_scan_that_falls_over_answers_typed_json_rather_than_a_traceback() -> None:
    """A raising collector is already a recorded failure; this is for the defects that are not."""

    class BrokenScanDomains(ScanDomainsUseCase):
        async def execute(self, domains: tuple[str, ...]) -> ScanReport:  # noqa: ARG002
            raise MemoryError("out of memory")

    index = build_fingerprint_index((STRIPE,))
    service = bootstrap.ScanService(
        scan_domains=BrokenScanDomains(
            scan_domain=ScanDomainUseCase(collectors=(), fingerprint_index=index),
            concurrency=1,
            deadline_seconds=5.0,
        ),
        fingerprints=(STRIPE,),
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as broken:
        response = broken.post("/scans", json={"domains": ["example.com"]})

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "the request could not be completed"}
    }
