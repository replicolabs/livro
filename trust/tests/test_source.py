from trust.source import UNTRUSTED_SOURCES, is_trusted_source


def test_authenticated_chat_is_trusted():
    assert is_trusted_source("freelancer_authenticated_chat") is True


def test_every_known_untrusted_source_is_untrusted():
    for source in UNTRUSTED_SOURCES:
        assert is_trusted_source(source) is False


def test_unknown_source_fails_closed_to_untrusted():
    assert is_trusted_source("some_new_channel_nobody_declared") is False
    assert is_trusted_source("") is False
