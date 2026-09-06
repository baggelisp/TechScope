"""What the driver refuses, and how early.

Domains arrive here from a stranger. Every bound below is the difference between this endpoint
and the CLI's file, so each one is tested for the refusal *and*, where it matters, for the point
at which the refusal happens.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from techscope.presentation.api.app import create_app
from techscope.presentation.api.body_limit import MAXIMUM_REQUEST_BYTES
from techscope.presentation.api.schemas import MAXIMUM_DOMAIN_LENGTH, MAXIMUM_SUBMITTED_DOMAINS
from tests.unit.presentation.api.test_routes import build_fake_service

INVALID_REQUEST = "invalid_request"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(build_fake_service())) as entered:
        yield entered


def build_oversized_body() -> str:
    """A body far past the bound, so nothing about it depends on the exact overhead."""
    entry = "a" * MAXIMUM_DOMAIN_LENGTH

    return '{"domains": [' + ", ".join(f'"{entry}"' for _ in range(400)) + "]}"


def test_a_body_past_the_bound_is_refused_before_it_is_read(client: TestClient) -> None:
    """The declared length is enough to refuse on; nothing is decoded or built into a list."""
    body = build_oversized_body()

    response = client.post("/scans", content=body, headers={"content-type": "application/json"})

    assert len(body) > MAXIMUM_REQUEST_BYTES
    assert response.status_code == 422
    assert response.json()["error"]["code"] == INVALID_REQUEST
    assert "bytes" in response.json()["error"]["message"]


def test_a_body_past_the_bound_is_refused_when_its_length_is_not_declared(
    client: TestClient,
) -> None:
    """A chunked body announces no length, so the bytes have to be counted as they arrive."""
    body = build_oversized_body().encode("utf-8")

    def stream_body() -> Iterator[bytes]:
        for start in range(0, len(body), 1024):
            yield body[start : start + 1024]

    response = client.post(
        "/scans", content=stream_body(), headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == INVALID_REQUEST
    # The same answer as the declared-length case, not the domain cap noticing later.
    assert "bytes" in response.json()["error"]["message"]


def test_a_body_within_the_bound_is_served_normally(client: TestClient) -> None:
    """The bound must not be so tight that a full-sized legitimate request cannot be made."""
    at_the_cap = [f"host{number}.example" for number in range(MAXIMUM_SUBMITTED_DOMAINS)]

    response = client.post("/scans", json={"domains": at_the_cap})

    assert response.status_code == 200


def test_a_domain_longer_than_a_domain_can_be_is_refused(client: TestClient) -> None:
    too_long = "a" * (MAXIMUM_DOMAIN_LENGTH + 1) + ".example"

    response = client.post("/scans", json={"domains": [too_long]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == INVALID_REQUEST
    assert str(MAXIMUM_DOMAIN_LENGTH) in response.json()["error"]["message"]


def test_a_domain_at_the_length_limit_is_accepted(client: TestClient) -> None:
    label = "a" * 60
    at_the_limit = ".".join([label] * 4)[:MAXIMUM_DOMAIN_LENGTH]

    response = client.post("/scans", json={"domains": [at_the_limit]})

    assert response.status_code == 200


def test_a_scan_that_arrives_before_the_service_is_wired_says_so() -> None:
    """Not entered as a context manager, so the lifespan never ran: exactly that race."""
    unstarted = TestClient(create_app(build_fake_service()))

    response = unstarted.post("/scans", json={"domains": ["example.com"]})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_reading_the_fingerprints_before_the_service_is_wired_says_so() -> None:
    unstarted = TestClient(create_app(build_fake_service()))

    response = unstarted.get("/fingerprints")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_the_wrong_method_is_answered_in_the_same_shape(client: TestClient) -> None:
    response = client.put("/scans", json={"domains": ["example.com"]})

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_a_malformed_request_is_not_echoed_into_the_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The framework's message quotes the input; logging that is an unbounded write for a caller."""
    smuggled = "SMUGGLED-INTO-THE-LOG"

    with caplog.at_level("INFO"):
        response = client.post("/scans", json={"domains": smuggled})

    assert response.status_code == 422
    assert smuggled not in caplog.text
    assert len(caplog.text) < 500
