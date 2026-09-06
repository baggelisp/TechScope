"""Guards that hold for every unit test.

`respx` keeps HTTP off the network, but it knows nothing about dnspython: a test that drives the
whole CLI would otherwise query real nameservers, which is how a DNS lookup for stripe.com once
turned up inside a test asserting an empty result. Patching the resolver class rather than one
module's reference to it means no unit test can reach a nameserver by any route; a test that
wants DNS answers substitutes its own resolver instance, which still shadows this.
"""

from collections.abc import Sequence

import dns.asyncresolver
import dns.rdata
import dns.resolver
import pytest


@pytest.fixture(autouse=True)
def block_real_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(*_args: object, **_keywords: object) -> Sequence[dns.rdata.Rdata]:
        raise dns.resolver.NoAnswer

    monkeypatch.setattr(dns.asyncresolver.Resolver, "resolve", refuse)
