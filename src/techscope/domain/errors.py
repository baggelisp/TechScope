"""The exception hierarchy. Tests assert on the typed fields, never on message text."""


class TechScopeError(Exception):
    """Base of every error this package raises deliberately."""


class FingerprintLoadError(TechScopeError):
    """The fingerprint database could not be turned into usable patterns.

    ``technology`` names the offending entry, or is ``None`` when the file itself is the problem.
    A fingerprint that cannot compile is never skipped: a silently missing pattern would look
    exactly like a technology that is not in use.
    """

    def __init__(self, technology: str | None, detail: str) -> None:
        self.technology = technology
        self.detail = detail
        super().__init__(_build_message(technology, detail))


def _build_message(technology: str | None, detail: str) -> str:
    if technology is None:
        return f"fingerprint database: {detail}"

    return f"fingerprint {technology!r}: {detail}"
