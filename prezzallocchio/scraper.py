import os
import random
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from .config import Product

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

PRICE_SELECTORS = [
    "#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen",
    "#apex_desktop .a-price:not(.a-text-price) .a-offscreen",
    "#buybox .a-price:not(.a-text-price) .a-offscreen",
    "#priceblock_dealprice",
    "#priceblock_ourprice",
    "#price_inside_buybox",
]

CURRENCIES = {"€": "EUR", "£": "GBP", "$": "USD", "EUR": "EUR", "GBP": "GBP", "USD": "USD"}
CAPTCHA_MARKERS = ("validateCaptcha", "api-services-support@amazon.com", "Robot Check")


class FetchError(Exception):
    """Il prezzo non è ottenibile (pagina senza prezzo, 404, rete...)."""


class Blocked(FetchError):
    """Amazon ci ha risposto con un CAPTCHA o un 429/503."""


@dataclass
class Offer:
    price: float
    currency: str | None
    title: str | None


def parse_price(text: str) -> float | None:
    """Converte '1.234,56 €', '€ 1,234.56', '29,99€' in float."""
    match = re.search(r"\d[\d.,  ]*\d|\d", text)
    if not match:
        return None
    number = re.sub(r"[  ]", "", match.group())
    sep = max(number.rfind(","), number.rfind("."))
    if sep != -1 and len(number) - sep - 1 in (1, 2):
        integer, decimals = number[:sep], number[sep + 1 :]
    else:
        integer, decimals = number, ""
    integer = re.sub(r"[.,]", "", integer)
    return float(f"{integer}.{decimals}" if decimals else integer)


def parse_product_page(html: str) -> Offer:
    if any(marker in html for marker in CAPTCHA_MARKERS):
        raise Blocked("CAPTCHA di Amazon")
    soup = BeautifulSoup(html, "html.parser")

    price = text = None
    for selector in PRICE_SELECTORS:
        node = soup.select_one(selector)
        if node and (price := parse_price(node.get_text())) is not None:
            text = node.get_text()
            break
    if price is None:
        raise FetchError("prezzo non trovato (prodotto non disponibile o layout cambiato)")

    currency = next((code for sym, code in CURRENCIES.items() if sym in text), None)
    title_node = soup.select_one("#productTitle")
    title = title_node.get_text(strip=True) if title_node else None
    return Offer(price=price, currency=currency, title=title)


def make_session() -> requests.Session:
    session = requests.Session()
    if proxy := os.environ.get("PROXY_URL"):
        session.proxies = {"http": proxy, "https": proxy}
    return session


def fetch(product: Product, session: requests.Session, attempts: int = 3) -> Offer:
    last_error: Exception = FetchError("nessun tentativo")
    for attempt in range(attempts):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            response = session.get(product.url, headers=headers, timeout=30)
            if response.status_code == 404:
                raise FetchError("pagina non trovata (404)")
            if response.status_code in (429, 503):
                raise Blocked(f"HTTP {response.status_code}")
            response.raise_for_status()
            return parse_product_page(response.text)
        except (requests.RequestException, FetchError) as exc:
            last_error = exc if isinstance(exc, FetchError) else FetchError(str(exc))
            if attempt < attempts - 1:
                time.sleep(5 * 2**attempt + random.random() * 3)
    raise last_error
