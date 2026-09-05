"""Parsing a page once, tolerantly, into the parts fingerprints care about."""

import pytest

from techscope.infrastructure.extractors.observed_response import MetaTag, parse_html_document


def test_parse_collects_a_quoted_script_source() -> None:
    document = parse_html_document('<script src="https://js.stripe.com/v3/"></script>')

    assert document.script_sources == ("https://js.stripe.com/v3/",)


def test_parse_collects_an_unquoted_script_source() -> None:
    document = parse_html_document("<script src=https://js.stripe.com/v3/></script>")

    assert document.script_sources == ("https://js.stripe.com/v3/",)


def test_parse_collects_a_single_quoted_script_source() -> None:
    document = parse_html_document("<script src='https://js.stripe.com/v3/'></script>")

    assert document.script_sources == ("https://js.stripe.com/v3/",)


def test_parse_keeps_a_protocol_relative_source_as_written() -> None:
    document = parse_html_document('<script src="//js.hs-scripts.com/8912.js"></script>')

    assert document.script_sources == ("//js.hs-scripts.com/8912.js",)


def test_parse_keeps_a_relative_source_as_written() -> None:
    document = parse_html_document('<script src="/wp-includes/js/jquery.js"></script>')

    assert document.script_sources == ("/wp-includes/js/jquery.js",)


def test_parse_trims_whitespace_around_a_source() -> None:
    document = parse_html_document('<script src="  https://a.example/b.js  "></script>')

    assert document.script_sources == ("https://a.example/b.js",)


def test_parse_ignores_a_script_whose_source_is_empty() -> None:
    document = parse_html_document('<script src="   "></script>')

    assert document.script_sources == ()


def test_parse_treats_a_valueless_source_attribute_as_no_source() -> None:
    document = parse_html_document("<script src>window.x = 1;</script>")

    assert document.script_sources == ()
    assert document.inline_scripts == ("window.x = 1;",)


def test_parse_collects_an_inline_script_body() -> None:
    body = "<script>function gtag(){dataLayer.push(arguments);}</script>"

    document = parse_html_document(body)

    assert document.inline_scripts == ("function gtag(){dataLayer.push(arguments);}",)


def test_parse_does_not_treat_a_sourced_script_as_inline() -> None:
    document = parse_html_document('<script src="https://a.example/b.js"></script>')

    assert document.inline_scripts == ()


def test_parse_collects_several_inline_scripts_separately() -> None:
    body = "<script>first();</script><p>text</p><script>second();</script>"

    document = parse_html_document(body)

    assert document.inline_scripts == ("first();", "second();")


def test_parse_ignores_an_empty_inline_script() -> None:
    document = parse_html_document("<script>   </script>")

    assert document.inline_scripts == ()


def test_parse_does_not_treat_ordinary_text_as_a_script() -> None:
    document = parse_html_document("<p>window.Intercom is mentioned in this paragraph</p>")

    assert document.inline_scripts == ()


def test_parse_keeps_comparison_operators_inside_a_script() -> None:
    body = "<script>if (a < b && c > d) { run(); }</script>"

    document = parse_html_document(body)

    assert "a < b" in document.inline_scripts[0]


def test_parse_collects_a_named_meta_tag() -> None:
    body = '<meta name="generator" content="WordPress 6.4">'

    document = parse_html_document(body)

    assert document.meta_tags == (MetaTag(name="generator", content="WordPress 6.4"),)


def test_parse_collects_a_meta_tag_declared_with_property() -> None:
    body = '<meta property="og:site_name" content="Shopify">'

    document = parse_html_document(body)

    assert document.meta_tags == (MetaTag(name="og:site_name", content="Shopify"),)


def test_parse_prefers_the_name_attribute_over_property() -> None:
    body = '<meta name="generator" property="og:x" content="WordPress">'

    document = parse_html_document(body)

    assert document.meta_tags[0].name == "generator"


def test_parse_ignores_a_meta_tag_without_content() -> None:
    document = parse_html_document('<meta name="viewport">')

    assert document.meta_tags == ()


def test_parse_ignores_a_meta_tag_without_a_name() -> None:
    document = parse_html_document('<meta charset="utf-8">')

    assert document.meta_tags == ()


def test_parse_handles_a_self_closing_meta_tag() -> None:
    document = parse_html_document('<meta name="generator" content="WordPress" />')

    assert document.meta_tags == (MetaTag(name="generator", content="WordPress"),)


def test_parse_reads_attribute_names_case_insensitively() -> None:
    body = '<SCRIPT SRC="https://a.example/b.js"></SCRIPT>'

    document = parse_html_document(body)

    assert document.script_sources == ("https://a.example/b.js",)


def test_parse_of_an_empty_body_finds_nothing() -> None:
    document = parse_html_document("")

    assert document.script_sources == ()
    assert document.inline_scripts == ()
    assert document.meta_tags == ()


def test_parse_survives_unclosed_tags() -> None:
    body = '<html><body><div><script src="https://a.example/b.js">'

    document = parse_html_document(body)

    assert document.script_sources == ("https://a.example/b.js",)


def test_parse_survives_a_stray_closing_tag() -> None:
    body = '</div></script><script src="https://a.example/b.js"></script>'

    document = parse_html_document(body)

    assert document.script_sources == ("https://a.example/b.js",)


def test_parse_survives_content_that_is_not_html_at_all() -> None:
    document = parse_html_document('{"json": true, "value": "<not a tag"}')

    assert document.script_sources == ()


def test_parse_ignores_a_script_tag_inside_a_comment() -> None:
    body = '<!-- <script src="https://tracker.example/x.js"></script> -->'

    document = parse_html_document(body)

    assert document.script_sources == ()


def test_parse_ignores_a_json_data_island() -> None:
    """Server-rendered frameworks serialise a page's own copy into a script element."""
    body = (
        '<script type="application/json">'
        '{"post":"we removed cdn.segment.com/analytics.js"}'
        "</script>"
    )

    document = parse_html_document(body)

    assert document.inline_scripts == ()


def test_parse_ignores_a_linked_data_island() -> None:
    body = '<script type="application/ld+json">{"articleBody":"static.zdassets.com"}</script>'

    assert parse_html_document(body).inline_scripts == ()


def test_parse_ignores_a_client_side_template() -> None:
    body = '<script type="text/template"><div>browser.sentry-cdn.com</div></script>'

    assert parse_html_document(body).inline_scripts == ()


@pytest.mark.parametrize(
    "declared_type",
    ["text/javascript", "application/javascript", "module", "TEXT/JAVASCRIPT", " module "],
    ids=["classic", "application form", "an es module", "uppercase", "padded"],
)
def test_parse_keeps_a_script_that_declares_a_javascript_type(declared_type: str) -> None:
    body = f'<script type="{declared_type}">window.analytics = [];</script>'

    assert parse_html_document(body).inline_scripts == ("window.analytics = [];",)


def test_parse_keeps_a_script_that_declares_no_type() -> None:
    assert parse_html_document("<script>run();</script>").inline_scripts == ("run();",)


def test_parse_of_an_unclosed_inline_script_swallows_the_rest_of_the_document() -> None:
    """A known limit of tolerant parsing: html.parser stays in script mode to the end of input.

    Browsers behave the same way, so a page like this is broken for everyone, but it means later
    tags are lost rather than merely unparsed.
    """
    body = '<script>var x=1;<meta name="generator" content="WordPress">'

    document = parse_html_document(body)

    assert document.meta_tags == ()
