import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_DOMAIN = "amazon.it"
_ASIN_IN_URL = re.compile(r"/(?:dp|gp/product|product)/([A-Z0-9]{10})")
_BARE_ASIN = re.compile(r"[A-Z0-9]{10}")


@dataclass(frozen=True)
class Product:
    asin: str
    domain: str = DEFAULT_DOMAIN
    name: str | None = None
    target_price: float | None = None
    drop_pct: float | None = None
    historic_low: bool = True

    @property
    def url(self) -> str:
        return f"https://www.{self.domain}/dp/{self.asin}"


def parse_ref(value: str) -> tuple[str, str | None]:
    """Da un ASIN o un URL Amazon ricava (asin, dominio o None)."""
    value = value.strip()
    if _BARE_ASIN.fullmatch(value):
        return value, None
    match = _ASIN_IN_URL.search(value)
    if not match:
        raise ValueError(f"Non riesco a ricavare l'ASIN da {value!r}")
    host = urlparse(value).netloc.lower().removeprefix("www.")
    return match.group(1), host or None


def load_products(path: Path) -> list[Product]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    settings = data.get("settings", {})
    default_domain = settings.get("domain", DEFAULT_DOMAIN)
    default_low = settings.get("historic_low", True)

    products = []
    for entry in data.get("products", []):
        ref = entry.get("asin") or entry.get("url")
        if not ref:
            raise ValueError(f"Prodotto senza 'asin' né 'url': {entry}")
        asin, url_domain = parse_ref(ref)
        products.append(
            Product(
                asin=asin,
                domain=entry.get("domain") or url_domain or default_domain,
                name=entry.get("name"),
                target_price=entry.get("target_price"),
                drop_pct=entry.get("drop_pct"),
                historic_low=entry.get("historic_low", default_low),
            )
        )
    return products
