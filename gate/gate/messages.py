"""Bilingual billing/onboarding strings -- pt-BR default per docs/language.md
Section 1 (same default as Livro's own conversational replies), English on
request. These are platform-level (gate) messages, distinct from the 7
tax-domain templates in rendering/rendering/templates.py -- that package
stays scoped to a tenant's own Livro conversation; this one is scoped to
"can this message be billed at all," which happens before any tenant-level
language preference has even been read (it lives in a workspace that may
not exist yet for a brand-new sender).
"""
from __future__ import annotations

from decimal import Decimal


def welcome_provisioning(language: str = "pt-BR") -> str:
    if language == "en":
        return "Welcome to Livro! Setting up your account now, one moment..."
    return "Bem-vindo à Livro! Estou configurando sua conta, um momento..."


def welcome_ready(trial_credit_usd: Decimal, language: str = "pt-BR") -> str:
    amount = f"{trial_credit_usd:.2f}"
    if language == "en":
        return (
            f"You're all set! You have ${amount} in free trial credit to try Livro out. "
            "Tell me about a client you'd like to invoice in USDC, or ask me anything."
        )
    return (
        f"Tudo pronto! Você tem ${amount} em crédito de teste gratuito para experimentar a Livro. "
        "Me conte sobre um cliente que você gostaria de faturar em USDC, ou pergunte qualquer coisa."
    )


def insufficient_balance(topup_link: str, language: str = "pt-BR") -> str:
    if language == "en":
        return (
            "Your credit balance is running low. Top up with USDC to keep going: "
            f"{topup_link}"
        )
    return (
        "Seu saldo de créditos está acabando. Recarregue com USDC para continuar: "
        f"{topup_link}"
    )


def topup_confirmed(credited_usd: Decimal, language: str = "pt-BR") -> str:
    amount = f"{credited_usd:.2f}"
    if language == "en":
        return f"Payment received! ${amount} added to your balance. You're good to go."
    return f"Pagamento recebido! ${amount} adicionados ao seu saldo. Pode continuar."


def account_disabled(language: str = "pt-BR") -> str:
    if language == "en":
        return "This account has been closed. Contact support to reactivate it."
    return "Esta conta foi encerrada. Entre em contato com o suporte para reativá-la."
