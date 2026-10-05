import argparse
import csv
import random
import time
from datetime import datetime
from pathlib import Path

from . import alerts, scraper, store
from .config import load_products, parse_ref
from .report import build_report, write_report


def parse_date(text: str) -> str:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt).isoformat()
        except ValueError:
            continue
    raise ValueError(f"Data non riconosciuta: {text!r} (usa YYYY-MM-DD o GG/MM/AAAA)")


def cmd_check(args) -> int:
    products = load_products(args.config)
    history_path, state_path = args.data / "history.csv", args.data / "state.json"
    history = store.read_history(history_path)
    state = store.load_state(state_path)
    session = scraper.make_session()
    queue: list[tuple[str, str, dict[str, float]]] = []  # (testo, asin, {regola: prezzo})
    failures: list[str] = []
    errors = 0

    for i, product in enumerate(products):
        if i and args.delay:
            time.sleep(random.uniform(args.delay, args.delay * 2))
        label = product.name or state["titles"].get(product.asin) or product.asin
        try:
            offer = scraper.fetch(product, session)
        except scraper.FetchError as exc:
            errors += 1
            count = state["failures"].get(product.asin, 0) + 1
            state["failures"][product.asin] = count
            print(f"✗ {label}: {exc} ({count} di fila)")
            if count == alerts.FAILURES_BEFORE_ALERT:
                failures.append(f"• {label}: {exc}\n  {product.url}")
            continue

        state["failures"].pop(product.asin, None)
        if offer.title:
            state["titles"][product.asin] = offer.title
        title = product.name or offer.title or product.asin
        currency = offer.currency or ""
        print(f"✓ {title[:60]}: {offer.price:.2f} {currency}")

        prior = [p.price for p in history.get(product.asin, [])]
        point = store.Point(store.now_iso(), product.asin, offer.price, currency)
        history.setdefault(product.asin, []).append(point)
        if not args.dry_run:
            store.append_point(history_path, point)

        fired = alerts.evaluate(product, offer.price, prior)
        last = state["alerts"].get(product.asin, {})
        to_send = alerts.new_alerts(fired, last, offer.price)
        # Le regole spente si "riarmano"; quelle ancora attive mantengono l'ultimo prezzo avvisato.
        state["alerts"][product.asin] = {r: last[r] for r in fired if r in last}
        if to_send:
            text = alerts.format_alert(product, title, offer.price, currency, [fired[r] for r in to_send])
            queue.append((text, product.asin, {r: offer.price for r in to_send}))

    if failures:
        text = f"⚠️ Non riesco a leggere il prezzo da {alerts.FAILURES_BEFORE_ALERT} controlli di fila:\n" + "\n".join(failures)
        queue.append((text, "", {}))

    if args.dry_run:
        for text, _, _ in queue:
            print("[dry-run]\n" + text)
        return 0

    for text, asin, rules in queue:
        # Lo stato dell'avviso si aggiorna solo se l'invio riesce: altrimenti si riprova al giro dopo.
        if alerts.send_telegram(text) and asin:
            state["alerts"].setdefault(asin, {}).update(rules)
    store.save_state(state_path, state)
    write_report(args.data / "REPORT.md", products, history, state["titles"])
    # Se TUTTI i prodotti falliscono il workflow risulta rosso e GitHub avvisa via mail.
    return 1 if products and errors == len(products) else 0


def cmd_report(args) -> int:
    products = load_products(args.config)
    history = store.read_history(args.data / "history.csv")
    state = store.load_state(args.data / "state.json")
    print(build_report(products, history, state["titles"]))
    return 0


def cmd_import(args) -> int:
    """Importa storico pregresso da CSV con colonne `date,price` (separatore , o ;)."""
    asin, _ = parse_ref(args.product)
    history_path = args.data / "history.csv"
    history = store.read_history(history_path)
    known = {p.timestamp for p in history.get(asin, [])}

    added = 0
    with args.csv.open(newline="", encoding="utf-8-sig") as fh:
        dialect = csv.Sniffer().sniff(fh.read(2048), delimiters=",;\t")
        fh.seek(0)
        for row in csv.DictReader(fh, dialect=dialect):
            row = {k.strip().lower(): v for k, v in row.items()}
            price = scraper.parse_price(row["price"])
            if price is None:
                continue
            ts = parse_date(row["date"])
            if ts in known:
                continue
            history.setdefault(asin, []).append(store.Point(ts, asin, price, args.currency, "import"))
            known.add(ts)
            added += 1
    store.write_history(history_path, history)
    print(f"Importati {added} punti per {asin}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prezzallocchio", description="Monitor dei prezzi Amazon con storico e alert Telegram")
    parser.add_argument("--config", type=Path, default=Path("products.toml"))
    parser.add_argument("--data", type=Path, default=Path("data"))
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="legge i prezzi, aggiorna lo storico, invia gli alert")
    check.add_argument("--dry-run", action="store_true", help="non scrive nulla e non invia messaggi")
    check.add_argument("--delay", type=float, default=4.0, help="pausa base (s) tra un prodotto e l'altro")
    check.set_defaults(func=cmd_check)

    sub.add_parser("report", help="stampa il riepilogo dello storico").set_defaults(func=cmd_report)

    imp = sub.add_parser("import-history", help="importa storico pregresso da CSV (colonne date,price)")
    imp.add_argument("product", help="ASIN o URL del prodotto")
    imp.add_argument("csv", type=Path)
    imp.add_argument("--currency", default="EUR")
    imp.set_defaults(func=cmd_import)

    args = parser.parse_args(argv)
    return args.func(args)
