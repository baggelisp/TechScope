"""The port through which a use case obtains the fingerprint database."""

from typing import Protocol

from techscope.domain.models import Fingerprint


class FingerprintRepository(Protocol):
    """Supplies the technologies to match against. Implemented in ``infrastructure``."""

    def load(self) -> tuple[Fingerprint, ...]:
        """Return every fingerprint, or raise ``FingerprintLoadError``. Nothing else."""
        ...
