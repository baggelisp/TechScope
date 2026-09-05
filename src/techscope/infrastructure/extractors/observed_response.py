"""Everything one response tells us, parsed once.

A tolerant HTML parse of a large homepage costs a quarter of a second, so it happens exactly
once per response and every extractor reads the same parsed view. Regex is never run over the
whole document to find tags: real pages are too broken for that to be honest.
"""

from dataclasses import dataclass
from html.parser import HTMLParser

from techscope.infrastructure.http.models import FetchResult

SCRIPT_TAG = "script"
META_TAG = "meta"
SOURCE_ATTRIBUTE = "src"
TYPE_ATTRIBUTE = "type"
NAME_ATTRIBUTE = "name"
PROPERTY_ATTRIBUTE = "property"
CONTENT_ATTRIBUTE = "content"

# A <script> element is only JavaScript when it says so or says nothing. Server-rendered
# frameworks and JSON-LD serialise a page's own copy into <script type="application/json">
# and friends, so treating those as script text would match vendor URLs in editorial text.
JAVASCRIPT_SCRIPT_TYPES = frozenset(
    {
        "text/javascript",
        "application/javascript",
        "application/ecmascript",
        "text/ecmascript",
        "module",
    }
)


@dataclass(frozen=True, slots=True)
class MetaTag:
    """One ``<meta>`` element that carries both a name and content."""

    name: str
    content: str


@dataclass(frozen=True, slots=True)
class HtmlDocument:
    """The parts of a page that fingerprints care about."""

    script_sources: tuple[str, ...]
    inline_scripts: tuple[str, ...]
    meta_tags: tuple[MetaTag, ...]


@dataclass(frozen=True, slots=True)
class ObservedResponse:
    """A fetched response together with its parsed document. What an extractor reads."""

    result: FetchResult
    document: HtmlDocument


def build_observed_response(result: FetchResult) -> ObservedResponse:
    return ObservedResponse(result=result, document=parse_html_document(result.body))


def parse_html_document(body: str) -> HtmlDocument:
    """Parse tolerantly. Broken markup yields fewer tags, never an exception."""
    collector = _DocumentCollector()
    collector.feed(body)
    collector.close()

    return HtmlDocument(
        script_sources=tuple(collector.script_sources),
        inline_scripts=tuple(collector.inline_scripts),
        meta_tags=tuple(collector.meta_tags),
    )


class _DocumentCollector(HTMLParser):
    """Collects script sources, inline script bodies and meta tags in a single pass."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.script_sources: list[str] = []
        self.inline_scripts: list[str] = []
        self.meta_tags: list[MetaTag] = []
        self._inside_inline_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = _build_attributes(attrs)

        if tag == SCRIPT_TAG:
            self._open_script(attributes)

            return

        if tag == META_TAG:
            self._collect_meta_tag(attributes)

    def handle_endtag(self, tag: str) -> None:
        if tag == SCRIPT_TAG:
            self._inside_inline_script = False

    def handle_data(self, data: str) -> None:
        if not self._inside_inline_script:
            return

        body = data.strip()

        if len(body) == 0:
            return

        self.inline_scripts.append(body)

    def _open_script(self, attributes: dict[str, str]) -> None:
        source = attributes.get(SOURCE_ATTRIBUTE)

        if source is None:
            self._inside_inline_script = _is_javascript_script(attributes)

            return

        trimmed = source.strip()

        if len(trimmed) == 0:
            return

        self.script_sources.append(trimmed)

    def _collect_meta_tag(self, attributes: dict[str, str]) -> None:
        name = _decide_meta_name_or_none(attributes)
        content = attributes.get(CONTENT_ATTRIBUTE)

        if name is None or content is None:
            return

        self.meta_tags.append(MetaTag(name=name, content=content))


def _build_attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    """A valueless attribute is absent rather than empty: ``<script src>`` carries no source."""
    attributes: dict[str, str] = {}

    for name, value in attrs:
        if value is None:
            continue

        attributes[name.lower()] = value

    return attributes


def _decide_meta_name_or_none(attributes: dict[str, str]) -> str | None:
    name = attributes.get(NAME_ATTRIBUTE)

    if name is not None:
        return name

    return attributes.get(PROPERTY_ATTRIBUTE)


def _is_javascript_script(attributes: dict[str, str]) -> bool:
    declared_type = attributes.get(TYPE_ATTRIBUTE)

    if declared_type is None:
        return True

    return declared_type.strip().lower() in JAVASCRIPT_SCRIPT_TYPES
