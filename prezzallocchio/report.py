from datetime import datetime
from pathlib import Path

from .config import Product
from .store import Point

BARS = "▁▂▃▄▅▆▇█"


def sparkline(prices: list[float], width: int = 30) -> str:
    prices = prices[-width:]
    if not prices:
        return ""
    lo, hi = min(prices), max(prices)
    if hi == lo:
        return BARS[0] * len(prices)
    return "".join(BARS[round((p - lo) / (hi - lo) * (len(BARS) - 1))] for p in prices)


def build_report(products: list[Product], history: dict[str, list[Point]], titles: dict[str, str]) -> str:
    rows = [
        "| Prodotto | Ora | Min | Max | Media | Min il | Andamento |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for product in products:
        points = history.get(product.asin, [])
        name = (product.name or titles.get(product.asin) or product.asin)[:60]
        label = f"[{name}]({product.url})"
        if not points:
            rows.append(f"| {label} | – | – | – | – | – | |")
            continue
        prices = [p.price for p in points]
        low = min(points, key=lambda p: p.price)
        rows.append(
            f"| {label} | **{prices[-1]:.2f}** | {low.price:.2f} | {max(prices):.2f} "
            f"| {sum(prices) / len(prices):.2f} | {datetime.fromisoformat(low.timestamp):%d/%m/%Y} | `{sparkline(prices)}` |"
        )
    updated = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
    return f"# Prezzi monitorati\n\nAggiornato il {updated}\n\n" + "\n".join(rows) + "\n"


def write_report(path: Path, *args) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(*args), encoding="utf-8")
