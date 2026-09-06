"""Building the ordered, de-duplicated scan list from the raw domains file text."""

import logging

import pytest

from techscope.domain.domain_list import build_domain_list

DOMAIN_LIST_LOGGER = "techscope.domain.domain_list"


def test_build_domain_list_preserves_input_order() -> None:
    text = "notion.so\nstripe.com\nintercom.com\n"

    assert build_domain_list(text) == ("notion.so", "stripe.com", "intercom.com")


def test_build_domain_list_skips_blank_and_comment_lines() -> None:
    text = "# the assignment domains\n\nstripe.com\n\n   \n# trailing note\nnotion.so\n"

    assert build_domain_list(text) == ("stripe.com", "notion.so")


def test_build_domain_list_deduplicates_after_normalisation() -> None:
    text = "stripe.com\nhttps://www.Stripe.com/pricing\nSTRIPE.COM.\nnotion.so\n"

    assert build_domain_list(text) == ("stripe.com", "notion.so")


def test_build_domain_list_keeps_first_occurrence_position_of_a_duplicate() -> None:
    text = "notion.so\nstripe.com\nnotion.so\n"

    assert build_domain_list(text) == ("notion.so", "stripe.com")


def test_build_domain_list_handles_carriage_return_line_endings() -> None:
    text = "notion.so\r\nstripe.com\r\n"

    assert build_domain_list(text) == ("notion.so", "stripe.com")


def test_build_domain_list_handles_missing_trailing_newline() -> None:
    text = "notion.so\nstripe.com"

    assert build_domain_list(text) == ("notion.so", "stripe.com")


def test_build_domain_list_empty_text_returns_no_domains() -> None:
    assert build_domain_list("") == ()


def test_build_domain_list_only_unusable_lines_returns_no_domains() -> None:
    text = "# nothing here\n\n   \n"

    assert build_domain_list(text) == ()


def test_build_domain_list_warns_about_a_line_it_drops(caplog: pytest.LogCaptureFixture) -> None:
    """The brief promises a result per input line; a line that yields none must be visible."""
    with caplog.at_level(logging.WARNING, logger=DOMAIN_LIST_LOGGER):
        build_domain_list("localhost\nexample.com\n")

    assert [record.levelname for record in caplog.records] == ["WARNING"]
    assert "localhost" in caplog.records[0].getMessage()


def test_build_domain_list_does_not_warn_about_blank_or_comment_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=DOMAIN_LIST_LOGGER):
        build_domain_list("# the domains\n\nexample.com\n")

    assert caplog.records == []


def test_build_domain_list_quotes_a_dropped_line_without_invisible_characters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=DOMAIN_LIST_LOGGER):
        build_domain_list("bad\x1bhost\n")

    assert "\x1b" not in caplog.records[0].getMessage()


def test_build_domain_list_does_not_warn_about_a_comment_behind_a_byte_order_mark(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An editor that prepends a byte order mark puts it on the comment header, line one."""
    with caplog.at_level(logging.WARNING, logger=DOMAIN_LIST_LOGGER):
        domains = build_domain_list("\ufeff# the domains\nexample.com\n")

    assert domains == ("example.com",)
    assert caplog.records == []


def test_build_domain_list_does_not_warn_about_a_line_of_invisible_characters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=DOMAIN_LIST_LOGGER):
        build_domain_list("\u200b\nexample.com\n")

    assert caplog.records == []
