"""The shared vocabulary. Every signal and every pattern names one of these channels."""

from enum import StrEnum


class ChannelEnum(StrEnum):
    """Where a signal came from, and therefore which patterns may match it.

    The values are the wire format: they appear in the details JSON and in the web app, so they
    are stable identifiers rather than display text.
    """

    HEADER = "header"
    COOKIE = "cookie"
    SCRIPT_SRC = "script_src"
    SCRIPT_INLINE = "script_inline"
    HTML = "html"
    META = "meta"
    JS_GLOBAL = "js_global"
    DNS_MX = "dns_mx"
    DNS_TXT = "dns_txt"
    DNS_CNAME = "dns_cname"


# Channels whose signals carry a name as well as a value: a header name, a cookie name, a meta
# tag name, a JavaScript global. A pattern on one of these constrains the name as well.
KEYED_CHANNELS = frozenset(
    {
        ChannelEnum.HEADER,
        ChannelEnum.COOKIE,
        ChannelEnum.META,
        ChannelEnum.JS_GLOBAL,
    }
)


class BlockReasonEnum(StrEnum):
    """Why a host refused to serve its homepage normally.

    A block is data rather than an error: the response headers that came with it are still
    evidence, and a Cloudflare challenge proves Cloudflare.
    """

    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CHALLENGE_PAGE = "challenge_page"
    EMPTY_BODY = "empty_body"


class FailureReasonEnum(StrEnum):
    """Why nothing at all could be collected for a domain."""

    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    TOO_MANY_REDIRECTS = "too_many_redirects"
    INVALID_HOST = "invalid_host"
    INVALID_RESPONSE = "invalid_response"
    DNS_UNRESOLVED = "dns_unresolved"
    COLLECTOR_ERROR = "collector_error"
