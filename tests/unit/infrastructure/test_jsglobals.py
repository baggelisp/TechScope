"""Reading JavaScript globals out of script text without running it."""

import pytest

from techscope.domain.enums import ChannelEnum
from techscope.infrastructure.extractors.jsglobals import (
    build_code_map,
    build_javascript_globals,
    extract_js_global_signals,
)
from techscope.infrastructure.extractors.observed_response import build_observed_response
from techscope.infrastructure.http.models import FetchResult

# Real loader snippets, trimmed. These are the shapes the extractor exists to read.
SEGMENT_SNIPPET = """
!function(){var analytics=window.analytics=window.analytics||[];
if(!analytics.initialize)if(analytics.invoked)
window.console&&console.error("included twice.");
else{analytics.invoked=!0;analytics.load("WRITE_KEY");}}();
"""
INTERCOM_SNIPPET = """
window.intercomSettings = {app_id: "abc123"};
(function(){var w=window;var ic=w.Intercom;
if(typeof ic==="function"){ic('reattach');}})();
"""
ANALYTICS_SNIPPET = """
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
"""


def build_globals_from_page(body: str) -> tuple[str, ...]:
    result = FetchResult(
        final_url="https://example.com/",
        status_code=200,
        headers=(),
        body=body,
        block_reason=None,
    )
    signals = extract_js_global_signals(build_observed_response(result))

    return tuple(signal.key for signal in signals if signal.key is not None)


def test_reads_a_window_property_assignment() -> None:
    assert build_javascript_globals("window.Intercom = function(){};") == ("Intercom",)


def test_reads_a_window_subscript_assignment() -> None:
    assert build_javascript_globals("window['analytics'] = [];") == ("analytics",)


def test_reads_a_double_quoted_window_subscript() -> None:
    assert build_javascript_globals('window["dataLayer"] = [];') == ("dataLayer",)


def test_reads_a_dotted_path_and_its_root() -> None:
    assert build_javascript_globals('window.Shopify.shop = "x";') == ("Shopify.shop", "Shopify")


def test_reads_a_top_level_declaration() -> None:
    assert build_javascript_globals("var analytics = [];") == ("analytics",)


@pytest.mark.parametrize("keyword", ["var", "let", "const"], ids=["var", "let", "const"])
def test_reads_every_declaration_keyword(keyword: str) -> None:
    assert build_javascript_globals(f"{keyword} zE = 1;") == ("zE",)


def test_reads_a_top_level_function_declaration() -> None:
    assert build_javascript_globals("function gtag(){dataLayer.push(arguments);}") == ("gtag",)


def test_reports_each_name_once() -> None:
    source = "window.dataLayer = window.dataLayer || []; window.dataLayer = [];"

    assert build_javascript_globals(source) == ("dataLayer",)


def test_keeps_the_order_names_first_appear_in() -> None:
    source = "window.first = 1; window.second = 2;"

    assert build_javascript_globals(source) == ("first", "second")


def test_ignores_a_name_written_inside_a_double_quoted_string() -> None:
    """The accuracy guard: documentation that talks about a global is not that global."""
    source = 'var docs = "window.Intercom = function(){}";'

    assert build_javascript_globals(source) == ("docs",)


def test_ignores_a_name_written_inside_a_single_quoted_string() -> None:
    source = "var docs = 'window.Intercom = 1';"

    assert build_javascript_globals(source) == ("docs",)


def test_ignores_a_name_written_inside_a_template_literal() -> None:
    source = "var docs = `window.Intercom = 1`;"

    assert build_javascript_globals(source) == ("docs",)


def test_ignores_a_name_inside_a_string_that_escapes_its_quote() -> None:
    source = 'var docs = "he said \\"window.Intercom = 1\\" loudly";'

    assert build_javascript_globals(source) == ("docs",)


def test_ignores_a_name_inside_a_line_comment() -> None:
    assert build_javascript_globals("// window.Intercom = function(){};") == ()


def test_ignores_a_name_inside_a_block_comment() -> None:
    assert build_javascript_globals("/* window.Intercom = 1; */") == ()


def test_ignores_a_name_inside_an_unterminated_block_comment() -> None:
    assert build_javascript_globals("/* window.Intercom = 1;") == ()


def test_ignores_a_declaration_inside_a_function() -> None:
    """A `var` inside a function is a local, not a global."""
    source = "function setup(){ var privateThing = 1; }"

    assert build_javascript_globals(source) == ("setup",)


def test_reads_a_window_property_even_inside_a_function() -> None:
    """A window property is global wherever it is written; the enclosing function is one too."""
    source = "function setup(){ window.Intercom = 1; }"

    assert build_javascript_globals(source) == ("setup", "Intercom")


def test_ignores_a_comparison_rather_than_an_assignment() -> None:
    assert build_javascript_globals("if (window.Intercom == other) { run(); }") == ()


def test_ignores_a_property_read_without_assignment() -> None:
    assert build_javascript_globals("if (window.Intercom) { run(); }") == ()


def test_ignores_a_window_property_of_something_else() -> None:
    assert build_javascript_globals("other.window.Intercom = 1;") == ()


def test_ignores_a_member_assignment_that_is_not_on_window() -> None:
    assert build_javascript_globals("settings.Intercom = 1;") == ()


def test_of_an_empty_script_finds_nothing() -> None:
    assert build_javascript_globals("") == ()


def test_of_a_script_with_no_globals_finds_nothing() -> None:
    assert build_javascript_globals("(function(){ doThing(); })();") == ()


def test_reads_the_segment_loader_snippet() -> None:
    assert "analytics" in build_javascript_globals(SEGMENT_SNIPPET)


def test_reads_the_intercom_snippet() -> None:
    assert "intercomSettings" in build_javascript_globals(INTERCOM_SNIPPET)


def test_reads_the_analytics_snippet() -> None:
    names = build_javascript_globals(ANALYTICS_SNIPPET)

    assert "dataLayer" in names
    assert "gtag" in names


def test_code_map_marks_a_string_as_ignored() -> None:
    source = 'var a = "text";'

    assert build_code_map(source).is_ignored(source.index('"')) is True


def test_code_map_treats_the_whole_of_a_brace_free_script_as_top_level() -> None:
    source = "var a = 1;"

    assert build_code_map(source).is_top_level(0) is True


def test_code_map_does_not_treat_the_inside_of_a_block_as_top_level() -> None:
    source = "function f(){ var a = 1; }"
    inside = source.index("var a")

    assert build_code_map(source).is_top_level(inside) is False


def test_extractor_emits_a_signal_per_global_keyed_by_its_name() -> None:
    body = "<html><body><script>window.Intercom = 1;</script></body></html>"

    assert build_globals_from_page(body) == ("Intercom",)


def test_extractor_uses_the_javascript_global_channel() -> None:
    result = FetchResult(
        final_url="https://example.com/",
        status_code=200,
        headers=(),
        body="<script>window.Intercom = 1;</script>",
        block_reason=None,
    )

    signals = extract_js_global_signals(build_observed_response(result))

    assert signals[0].channel is ChannelEnum.JS_GLOBAL


def test_extractor_reads_every_inline_script_on_the_page() -> None:
    body = "<script>window.first = 1;</script><p>x</p><script>window.second = 2;</script>"

    assert build_globals_from_page(body) == ("first", "second")


def test_extractor_ignores_a_json_data_island() -> None:
    """Page data is not script: the parser already skips it, and this keeps it that way."""
    body = '<script type="application/json">{"code":"window.Intercom = 1;"}</script>'

    assert build_globals_from_page(body) == ()


def test_extractor_ignores_a_script_loaded_from_elsewhere() -> None:
    body = '<script src="https://widget.intercom.io/widget/abc"></script>'

    assert build_globals_from_page(body) == ()


def test_extractor_of_a_page_without_scripts_emits_nothing() -> None:
    assert build_globals_from_page("<html><body>nothing</body></html>") == ()


def test_ignores_a_subscript_read_without_assignment() -> None:
    """Checking whether a global exists is not evidence that it does."""
    assert build_javascript_globals("if (window['Intercom']) { boot(); }") == ()


def test_reads_a_subscript_assignment_but_not_a_neighbouring_read() -> None:
    source = "if (window['Optimizely']) { window['Marker'] = 1; }"

    assert build_javascript_globals(source) == ("Marker",)


def test_a_quote_inside_a_regex_literal_does_not_open_a_string() -> None:
    """The desync this guards against reads later names straight out of documentation text."""
    source = (
        'function esc(s){return s.replace(/"/g,"&quot;")}\nvar help = "set window.Optimizely = 1";'
    )

    assert build_javascript_globals(source) == ("esc", "help")


def test_a_quote_inside_a_regex_literal_does_not_swallow_the_rest_of_the_script() -> None:
    source = "var text = html.replace(/'/g, '');\nwindow.Segment = 1;"

    assert build_javascript_globals(source) == ("text", "Segment")


def test_a_division_is_not_mistaken_for_a_regex() -> None:
    source = "var ratio = width / height; window.Intercom = 1;"

    assert build_javascript_globals(source) == ("ratio", "Intercom")


def test_survives_an_unterminated_string() -> None:
    """The declaration before it still counts; the unterminated text swallows only what follows."""
    assert build_javascript_globals('var a = "never closed;') == ("a",)


def test_survives_unbalanced_closing_braces() -> None:
    assert build_javascript_globals("}}} var a = 1;") == ("a",)


def test_survives_unbalanced_opening_braces() -> None:
    assert build_javascript_globals("var a = 1; {{{") == ("a",)


def test_ignores_a_function_declared_inside_another_function() -> None:
    source = "function outer(){ function inner(){} }"

    assert build_javascript_globals(source) == ("outer",)


def test_ignores_a_function_assigned_to_a_local() -> None:
    source = "function outer(){ var handler = function(){}; }"

    assert build_javascript_globals(source) == ("outer",)


def test_scans_a_large_script_quickly() -> None:
    """The span lookup is a binary search; scanning cost 397 s on this input before."""
    source = "".join(f'window.n{index}=1;var s{index}="t{index}";' for index in range(20000))

    assert len(build_javascript_globals(source)) == 40000
