"""The shape the fan-out needs from a domain scan.

Not a port over I/O — ``ScanDomainUseCase`` is the only implementation and it stays that way.
It exists so the bounded fan-out can be exercised by a fake that is slow, or that explodes, in
the tests that pin those behaviours.
"""

from typing import Protocol

from techscope.domain.models import DomainScanResult


class DomainScanner(Protocol):
    async def execute(self, domain: str) -> DomainScanResult: ...
