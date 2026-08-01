"""docs/language.md Section 8, items 5-6: no-silent-switch and explicit-switch."""
from rendering.language_switch import (
    RESULT_AMBIGUOUS,
    RESULT_NO_SIGNAL,
    RESULT_SWITCH_TO_EN,
    RESULT_SWITCH_TO_PT,
    detect_language_switch,
)


def test_ordinary_portuguese_message_no_signal():
    assert detect_language_switch("Oi, pode fazer uma fatura de 500 USDC?") == RESULT_NO_SIGNAL


def test_stray_english_word_in_portuguese_message_does_not_switch():
    """The exact failure mode Section 1.2 warns about: a pasted English
    client name or stray English word must never flip the preference.
    """
    msg = "Cria uma fatura para o cliente 'Global Trading Solutions LLC' em USDC"
    assert detect_language_switch(msg) == RESULT_NO_SIGNAL


def test_english_invoice_text_pasted_into_portuguese_message_no_signal():
    msg = "O cliente mandou isso: 'Please send invoice to accounting@example.com'"
    assert detect_language_switch(msg) == RESULT_NO_SIGNAL


def test_explicit_portuguese_trigger_switches_to_english():
    for msg in ("fala inglês, por favor", "pode responder em inglês?", "quero em inglês"):
        assert detect_language_switch(msg) == RESULT_SWITCH_TO_EN


def test_explicit_english_trigger_switches_to_english():
    for msg in ("switch to English please", "can you speak English?", "reply in English from now on"):
        assert detect_language_switch(msg) == RESULT_SWITCH_TO_EN


def test_explicit_trigger_switches_back_to_portuguese():
    for msg in ("volta pro português", "switch back to Portuguese", "speak Portuguese again please"):
        assert detect_language_switch(msg) == RESULT_SWITCH_TO_PT


def test_accents_are_normalized_for_matching():
    # Same trigger, unaccented ASCII typing (common on some keyboards/devices)
    assert detect_language_switch("fala ingles") == RESULT_SWITCH_TO_EN
    assert detect_language_switch("volta para o portugues") == RESULT_SWITCH_TO_PT


def test_vague_language_mention_is_ambiguous_not_silent():
    assert detect_language_switch("can we change the language?") == RESULT_AMBIGUOUS
    assert detect_language_switch("posso mudar o idioma?") == RESULT_AMBIGUOUS


def test_case_insensitive_matching():
    assert detect_language_switch("SWITCH TO ENGLISH") == RESULT_SWITCH_TO_EN
