"""Building the ordered, de-duplicated scan list from the raw domains file text."""

from techscope.domain.domain_list import build_domain_list


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
