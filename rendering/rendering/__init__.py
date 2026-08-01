"""Pure, independently-testable bilingual (pt-BR / en) message rendering.

Per docs/language.md Section 2: this package is a rendering-layer-only
concern. It never touches the ledger or the tax engine's math -- it takes
plain decimal/date data plus a language code and produces final chat text.
No function here computes a tax figure; it only formats one that was
already computed elsewhere (see ../tax_engine/).
"""

SUPPORTED_LANGUAGES = ("pt-BR", "en")
DEFAULT_LANGUAGE = "pt-BR"


def validate_language(language: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported language {language!r}; expected one of {SUPPORTED_LANGUAGES}")
    return language
