"""The JSON boundary: what a request must look like.

A plain frozen dataclass, not a pydantic model. The framework will still refuse a body of the
wrong shape, and the bounds that matter — how many domains, how long each may be — are guard
clauses in the route, where they can say which rule was broken instead of naming a field path.
Keeping the record ordinary also keeps it the same kind of thing as every other record here.

The response has no schema of its own on purpose: it is whatever `present_details` produces, so
that the body this driver returns and the file the CLI writes cannot drift apart.
"""

from dataclasses import dataclass

# Enough for a page of results, small enough that a stranger cannot ask for an hour of scanning.
MAXIMUM_SUBMITTED_DOMAINS = 50
# The longest a domain name can be, so a submitted string longer than this is not one.
MAXIMUM_DOMAIN_LENGTH = 253


@dataclass(frozen=True, slots=True)
class ScanRequest:
    """A scan someone asked for. The domains are raw text and are normalised before use."""

    domains: list[str]
