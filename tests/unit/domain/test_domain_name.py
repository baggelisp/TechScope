"""The per-line normaliser that turns a raw input line into a scannable domain."""

import pytest

from techscope.domain.domain_name import decide_apex_domain, decide_domain_or_none

NORMALISED_CASES = [
    ("example.com", "example.com", "a bare domain is unchanged"),
    ("  example.com  ", "example.com", "surrounding whitespace is stripped"),
    ("example.com\r", "example.com", "a carriage return is stripped"),
    ("EXAMPLE.COM", "example.com", "an uppercase domain is lowercased"),
    ("https://example.com", "example.com", "an https scheme is removed"),
    ("http://example.com", "example.com", "an http scheme is removed"),
    ("HTTPS://Example.COM", "example.com", "an uppercase scheme is removed"),
    ("www.example.com", "example.com", "a www prefix is removed"),
    ("wwwx.example.com", "wwwx.example.com", "a label merely starting with www is kept"),
    ("https://www.example.com/path/page.html", "example.com", "scheme, www and path are removed"),
    ("example.com/", "example.com", "a trailing slash is removed"),
    ("example.com?query=1", "example.com", "a query string is removed"),
    ("example.com#fragment", "example.com", "a fragment is removed"),
    ("example.com # inline note", "example.com", "a trailing inline comment is removed"),
    ("example.com /redirects", "example.com", "a space before a path is removed"),
    ("example.com:8443", "example.com", "an explicit port is removed"),
    ("example.com.", "example.com", "a fully qualified trailing dot is removed"),
    ("sub.example.com", "sub.example.com", "a subdomain other than www is preserved"),
    ("bbc.co.uk", "bbc.co.uk", "a multi-part public suffix is preserved"),
    ("sentry.io", "sentry.io", "a two-label domain is preserved"),
]

UNUSABLE_CASES = [
    ("", "an empty line"),
    ("    ", "a whitespace-only line"),
    ("\r\n", "a bare line ending"),
    ("# a comment", "a comment line"),
    ("   # an indented comment", "an indented comment line"),
    ("https://", "a scheme with no host"),
    ("/just/a/path", "a path with no host"),
    ("localhost", "a hostname with no dot"),
    ("two words.com", "a line containing whitespace inside the host"),
    (".", "a lone dot"),
]


@pytest.mark.parametrize(
    ("raw_line", "expected_domain"),
    [(raw_line, expected) for raw_line, expected, _ in NORMALISED_CASES],
    ids=[description for _, _, description in NORMALISED_CASES],
)
def test_decide_domain_or_none_normalises_usable_line(raw_line: str, expected_domain: str) -> None:
    assert decide_domain_or_none(raw_line) == expected_domain


@pytest.mark.parametrize(
    "raw_line",
    [raw_line for raw_line, _ in UNUSABLE_CASES],
    ids=[description for _, description in UNUSABLE_CASES],
)
def test_decide_domain_or_none_rejects_unusable_line(raw_line: str) -> None:
    assert decide_domain_or_none(raw_line) is None


APEX_CASES = [
    ("example.com", "example.com", "an apex domain is unchanged"),
    ("www.example.com", "example.com", "a www prefix is stripped"),
    ("bbc.co.uk", "bbc.co.uk", "a multi-part public suffix is left alone"),
    ("www.bbc.co.uk", "bbc.co.uk", "www is stripped above a multi-part suffix"),
    ("blog.example.com", "blog.example.com", "a subdomain is not reduced"),
    ("myblog.wordpress.com", "myblog.wordpress.com", "a hosted subdomain keeps its own name"),
    ("project.github.io", "project.github.io", "a pages subdomain keeps its own name"),
    ("example.com.", "example.com", "a trailing dot is removed"),
    ("wwwx.example.com", "wwwx.example.com", "a label merely starting with www is kept"),
]


@pytest.mark.parametrize(
    ("domain", "expected_apex"),
    [(domain, expected) for domain, expected, _ in APEX_CASES],
    ids=[description for _, _, description in APEX_CASES],
)
def test_decide_apex_domain_resolves_the_dns_name(domain: str, expected_apex: str) -> None:
    assert decide_apex_domain(domain) == expected_apex
