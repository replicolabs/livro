"""Bilingual message templates. docs/language.md Section 6.

Every function takes plain structured data (Decimal/date/str) plus a
language code and returns final chat text. None of these functions look up
a preference themselves -- the caller (a skill's step) reads
user_preferences.json and passes `language` in explicitly, so a switch
request can never be silently ignored by a stale default (docs/language.md
Section 1.3/8.7's persistence requirement).

Templates below are a faithful, formatting-corrected rendering of
docs/language.md Section 6's illustrative pairs -- see
formatting.py::format_vencimento for the one deliberate deviation from the
illustrative English example (a bare-numerals vencimento date), resolved in
favor of Section 5.3's explicit unambiguous-date rule.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from rendering import validate_language
from rendering.formatting import (
    format_brl,
    format_brl_signed,
    format_competencia,
    format_month_name,
    format_percentage,
    format_usdc,
    format_vencimento,
)

DISCLAIMER = {
    "pt-BR": "Isso é uma ferramenta de apoio ao cálculo, não substitui a orientação de um contador.",
    "en": "This is a computation aid, not a substitute for guidance from a contador.",
}


def render_invoice_draft(usdc_amount: Decimal, client_label: str, month: int, link: str, language: str) -> str:
    validate_language(language)
    amount = format_usdc(usdc_amount, language)
    month_name = format_month_name(month, language)
    if language == "pt-BR":
        return (
            f"Fatura criada: {amount} para o cliente de {client_label}, referente a {month_name}. "
            f"Aqui está o link de pagamento: {link}. Envie para o cliente quando quiser."
        )
    return (
        f"Invoice created: {amount} for the {client_label} client, for {month_name}. "
        f"Here's the payment link: {link}. Send it to the client whenever you're ready."
    )


def render_payment_received(
    usdc_amount: Decimal,
    client_label: str,
    receipt_date: date,
    ptax_rate: Decimal,
    brl_value: Decimal,
    language: str,
) -> str:
    validate_language(language)
    amount = format_usdc(usdc_amount, language)
    rate = format_brl(ptax_rate, language)
    value = format_brl(brl_value, language)
    when = format_vencimento(receipt_date, language)  # same unambiguous date renderer
    if language == "pt-BR":
        return (
            f"Pagamento recebido: {amount} do cliente de {client_label}, em {when}. "
            f"Cotação PTAX do dia: {rate}. Valor em reais: {value}. "
            "O que você quer fazer com esse valor: converter para reais, manter em USDC, ou alocar em um título?"
        )
    return (
        f"Payment received: {amount} from the {client_label} client, on {when}. "
        f"That day's PTAX rate: {rate}. Value in reais: {value}. "
        "What would you like to do with it: convert to reais, hold as USDC, or allocate into a bond?"
    )


def render_monthly_carne_leao_summary(
    base: Decimal,
    bracket_rate: Decimal,
    tax_due: Decimal,
    darf_code: str,
    competencia_month: int,
    competencia_year: int,
    vencimento: date,
    language: str,
) -> str:
    validate_language(language)
    month_name = format_month_name(competencia_month, language)
    base_str = format_brl(base, language)
    rate_str = format_percentage(bracket_rate, language)
    tax_str = format_brl_signed(tax_due, language)
    competencia_str = format_competencia(competencia_month, competencia_year)
    vencimento_str = format_vencimento(vencimento, language)
    disclaimer = DISCLAIMER[language]

    if language == "pt-BR":
        return (
            f"Seu Carnê-Leão de {month_name}: base de cálculo {base_str}, alíquota aplicada {rate_str}, "
            f"valor devido {tax_str} (DARF código {darf_code}, competência {competencia_str}, "
            f"vencimento {vencimento_str}). {disclaimer} "
            "Teve alguma outra renda esse mês que eu deveria incluir?"
        )
    return (
        f"Your Carnê-Leão for {month_name}: taxable base {base_str}, {rate_str} bracket applied, "
        f"amount due {tax_str} (DARF código {darf_code}, competência {competencia_str}, "
        f"vencimento {vencimento_str}). {disclaimer} "
        "Was there any other income this month I should include?"
    )


def render_threshold_warning(threshold_brl: Decimal, language: str) -> str:
    validate_language(language)
    threshold_str = format_brl(threshold_brl, language)
    if language == "pt-BR":
        return (
            f"Aviso: suas movimentações este mês estão próximas do limite de {threshold_str} "
            "que exige declaração adicional à Receita (IN 1888). "
            "Vale confirmar com seu contador se essa declaração é necessária."
        )
    return (
        f"Heads up: your transactions this month are approaching the {threshold_str} threshold "
        "that triggers an additional self-report to Receita (IN 1888). "
        "Worth confirming with your contador whether that report is needed."
    )


def render_injection_refusal(language: str) -> str:
    validate_language(language)
    if language == "pt-BR":
        return (
            "Recebi uma mensagem pedindo para redirecionar um pagamento para um endereço "
            "diferente, mas isso não veio de você diretamente, então não vou seguir essa "
            "instrução. Se você realmente quiser fazer isso, me diga diretamente e eu "
            "preparo o rascunho para sua aprovação."
        )
    return (
        "I received a message asking to redirect a payment to a different address, but it "
        "didn't come from you directly, so I'm not acting on it. If you actually want to do "
        "this, tell me directly and I'll draft it for your approval."
    )


def render_external_holding_prompt(language: str) -> str:
    validate_language(language)
    if language == "pt-BR":
        return (
            "Só para garantir que seus números fiquem completos: você recebeu alguma outra "
            "renda este mês, em cripto ou não, que eu não veria automaticamente nesta carteira?"
        )
    return (
        "Just to make sure your numbers are complete: did you receive any other income this "
        "month, crypto or otherwise, that I wouldn't automatically see through this wallet?"
    )


def render_disposition_choices(language: str) -> list[str]:
    """Button/choice labels for the ask_user disposition prompt (convert /
    hold / allocate) that watch_payment's Step 3 sends -- CLAUDE.md Section
    1.2/3.1. Kept as its own function (not folded into
    render_payment_received) since ask_user's `choices` list is passed
    separately from the message text itself.
    """
    validate_language(language)
    if language == "pt-BR":
        return ["Converter para reais", "Manter em USDC", "Alocar em título (Tesouro/Etherfuse)"]
    return ["Convert to reais", "Hold as USDC", "Allocate to a bond (Tesouro/Etherfuse)"]


def render_language_switch_confirmation(new_language: str) -> str:
    """Rendered IN the new language -- doubles as proof the switch took
    effect (docs/language.md Section 3).
    """
    validate_language(new_language)
    if new_language == "pt-BR":
        return "Combinado, vou responder em português a partir de agora."
    return "Got it, I'll reply in English from now on."


def render_language_switch_clarification(current_language: str) -> str:
    """Asked when detect_language_switch returns 'ambiguous' -- always in
    the CURRENT (not requested) language, per docs/language.md Section 3.
    """
    validate_language(current_language)
    if current_language == "pt-BR":
        return "Você quer que eu passe a responder em inglês?"
    return "Would you like me to reply in Portuguese instead?"
