"""The extractors the HTTP collector runs, in order.

Adding a response channel is an entry here plus its module. Nothing else changes: the collector
does not name them and the matcher never learns which one produced a signal.
"""

from collections.abc import Callable

from techscope.domain.models import Signal
from techscope.infrastructure.extractors.cookies import extract_cookie_signals
from techscope.infrastructure.extractors.headers import extract_header_signals
from techscope.infrastructure.extractors.html import extract_html_signal
from techscope.infrastructure.extractors.jsglobals import extract_js_global_signals
from techscope.infrastructure.extractors.meta import extract_meta_signals
from techscope.infrastructure.extractors.observed_response import ObservedResponse
from techscope.infrastructure.extractors.scripts import extract_script_signals

Extractor = Callable[[ObservedResponse], tuple[Signal, ...]]

EXTRACTORS: tuple[Extractor, ...] = (
    extract_header_signals,
    extract_cookie_signals,
    extract_script_signals,
    extract_meta_signals,
    extract_js_global_signals,
    extract_html_signal,
)
