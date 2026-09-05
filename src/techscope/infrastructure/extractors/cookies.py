"""Cookie names and values, read from every ``Set-Cookie`` header."""

from techscope.domain.enums import ChannelEnum
from techscope.domain.models import Signal
from techscope.infrastructure.extractors.observed_response import ObservedResponse

SET_COOKIE_HEADER = "set-cookie"
ATTRIBUTE_SEPARATOR = ";"
NAME_VALUE_SEPARATOR = "="


def extract_cookie_signals(response: ObservedResponse) -> tuple[Signal, ...]:
    """The name is the signal's key; the attributes after the first ``;`` are not the value."""
    signals: list[Signal] = []

    for name, value in response.result.headers:
        if name != SET_COOKIE_HEADER:
            continue

        signal = _decide_cookie_signal_or_none(value)

        if signal is None:
            continue

        signals.append(signal)

    return tuple(signals)


def _decide_cookie_signal_or_none(header_value: str) -> Signal | None:
    pair = header_value.split(ATTRIBUTE_SEPARATOR)[0]
    separator_index = pair.find(NAME_VALUE_SEPARATOR)

    if separator_index < 0:
        return None

    cookie_name = pair[:separator_index].strip()

    if len(cookie_name) == 0:
        return None

    cookie_value = pair[separator_index + 1 :].strip()

    return Signal(channel=ChannelEnum.COOKIE, value=cookie_value, key=cookie_name)
