import os

import requests

from .config import Product

# Servono almeno questi punti storici prima di dichiarare un "minimo storico",
# altrimenti i primi controlli segnalerebbero minimi a ogni lettura.
MIN_POINTS_FOR_LOW = 3
FAILURES_BEFORE_ALERT = 3


def evaluate(product: Product, price: float, prior: list[float]) -> dict[str, str]:
    """Regole scattate per il prezzo attuale. `prior` = prezzi precedenti, cronologici."""
    fired: dict[str, str] = {}
    if product.target_price is not None and price <= product.target_price:
        fired["target"] = f"sotto il prezzo obiettivo ({product.target_price:.2f})"
    if product.drop_pct and prior and price <= prior[-1] * (1 - product.drop_pct / 100):
        fired["drop"] = f"calo del {(1 - price / prior[-1]) * 100:.0f}% (era {prior[-1]:.2f})"
    if product.historic_low and len(prior) >= MIN_POINTS_FOR_LOW and price < min(prior):
        fired["low"] = f"nuovo minimo storico (prima {min(prior):.2f})"
    return fired


def new_alerts(fired: dict[str, str], last: dict[str, float], price: float) -> list[str]:
    """Filtra le regole già segnalate: si ri-avvisa solo se la regola era spenta
    o se il prezzo è sceso ancora rispetto all'ultimo avviso."""
    return [rule for rule in fired if rule not in last or price < last[rule]]


def format_alert(product: Product, title: str, price: float, currency: str, reasons: list[str]) -> str:
    lines = [f"💸 {title}", f"Ora: {price:.2f} {currency}".rstrip()]
    lines += [f"• {reason}" for reason in reasons]
    lines.append(product.url)
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[telegram non configurato] " + text.replace("\n", " | "))
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=20,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        # Non stampiamo l'URL: contiene il token.
        print(f"Invio Telegram fallito: {type(exc).__name__}")
        return False
