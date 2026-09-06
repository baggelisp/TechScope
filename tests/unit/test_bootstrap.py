"""The composition root, from the side both drivers see it.

The CLI wires a scan per invocation and the HTTP API wires one for the life of the process, so
what is tested here is that the wiring is the same either way and that it cleans up after itself.
"""

from pathlib import Path

import httpx
import pytest

from techscope import bootstrap
from techscope.domain.errors import FingerprintLoadError
from techscope.infrastructure.http.homepage_fetcher import build_client

PACKAGED_FINGERPRINTS = bootstrap.DEFAULT_FINGERPRINTS_PATH


@pytest.fixture
def opened_clients(monkeypatch: pytest.MonkeyPatch) -> list[httpx.AsyncClient]:
    """Every client the composition root opens, so a test can ask whether it was closed."""
    opened: list[httpx.AsyncClient] = []
    build_real_client = build_client

    def remember() -> httpx.AsyncClient:
        client = build_real_client()
        opened.append(client)

        return client

    monkeypatch.setattr(bootstrap, "build_client", remember)

    return opened


def build_settings(fingerprints_path: Path = PACKAGED_FINGERPRINTS) -> bootstrap.ScanSettings:
    return bootstrap.ScanSettings(
        fingerprints_path=fingerprints_path,
        nameservers=(),
        concurrency=bootstrap.DEFAULT_CONCURRENCY,
        timeout_seconds=bootstrap.DEFAULT_TIMEOUT_SECONDS,
        deadline_seconds=bootstrap.DEFAULT_DEADLINE_SECONDS,
    )


async def test_build_scan_service_loads_the_packaged_fingerprints() -> None:
    async with bootstrap.build_scan_service(build_settings()) as service:
        assert len(service.fingerprints) > 0


async def test_build_scan_service_wires_a_usable_scan() -> None:
    """A scan of nothing still runs: the wiring is complete, not merely constructed."""
    async with bootstrap.build_scan_service(build_settings()) as service:
        report = await service.scan_domains.execute(())

    assert report.results == ()


async def test_build_scan_service_closes_its_client_on_exit(
    opened_clients: list[httpx.AsyncClient],
) -> None:
    """The API holds this open for the life of the process; the CLI for one run."""
    async with bootstrap.build_scan_service(build_settings()):
        pass

    assert [client.is_closed for client in opened_clients] == [True]


async def test_build_scan_service_closes_its_client_when_the_body_raises(
    opened_clients: list[httpx.AsyncClient],
) -> None:
    with pytest.raises(RuntimeError):
        async with bootstrap.build_scan_service(build_settings()):
            raise RuntimeError("the driver fell over")

    assert [client.is_closed for client in opened_clients] == [True]


async def test_build_scan_service_reports_an_unusable_database_by_technology(
    tmp_path: Path,
) -> None:
    broken = tmp_path / "technologies.json"
    broken.write_text('{"Hostile Tech": {"headers": {"X-Thing": "(a+)+$"}}}', encoding="utf-8")

    with pytest.raises(FingerprintLoadError) as raised:
        async with bootstrap.build_scan_service(build_settings(broken)):
            pass

    assert raised.value.technology == "Hostile Tech"
