import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["timestamp", "asin", "price", "currency", "source"]


@dataclass(frozen=True)
class Point:
    timestamp: str
    asin: str
    price: float
    currency: str = ""
    source: str = "scrape"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_history(path: Path) -> dict[str, list[Point]]:
    """Storico per ASIN, in ordine cronologico."""
    history: dict[str, list[Point]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                point = Point(row["timestamp"], row["asin"], float(row["price"]), row["currency"], row["source"])
                history.setdefault(point.asin, []).append(point)
    for points in history.values():
        points.sort(key=lambda p: p.timestamp)
    return history


def write_history(path: Path, history: dict[str, list[Point]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    points = sorted((p for pts in history.values() for p in pts), key=lambda p: (p.timestamp, p.asin))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, FIELDS)
        writer.writeheader()
        for p in points:
            writer.writerow({"timestamp": p.timestamp, "asin": p.asin, "price": p.price, "currency": p.currency, "source": p.source})


def append_point(path: Path, point: Point) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({"timestamp": point.timestamp, "asin": point.asin, "price": point.price, "currency": point.currency, "source": point.source})


def load_state(path: Path) -> dict:
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key in ("alerts", "failures", "titles"):
        state.setdefault(key, {})
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
