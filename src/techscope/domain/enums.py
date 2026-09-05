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
