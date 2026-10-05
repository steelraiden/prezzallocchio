# prezzallocchio

Tiene d'occhio i prezzi degli articoli Amazon, salva lo storico e ti avvisa su Telegram.
Gira gratis su GitHub Actions ogni 6 ore; lo storico è un CSV nel repo (`data/history.csv`)
e il riepilogo con andamento è in `data/REPORT.md`.

## Setup (5 minuti)

1. **Prodotti**: modifica `products.toml` (ASIN o URL, e le soglie che vuoi).
2. **Bot Telegram**: scrivi a [@BotFather](https://t.me/BotFather) → `/newbot` → copia il token.
   Poi manda un messaggio qualsiasi al tuo bot e apri
   `https://api.telegram.org/bot<TOKEN>/getUpdates` per leggere il tuo `chat.id`.
3. **Secrets** del repo (Settings → Secrets and variables → Actions):
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, e opzionalmente `PROXY_URL` (vedi sotto).
4. **Actions** → "Controlla prezzi" → *Run workflow* per il primo giro. Poi va da solo.

## Alert

Per ogni prodotto, in `products.toml`:

| Regola | Scatta quando |
|---|---|
| `target_price = 49.9` | il prezzo è ≤ 49,90 |
| `drop_pct = 10` | cala di almeno il 10% rispetto all'ultima lettura |
| `historic_low = true` | è il più basso mai registrato (serve un po' di storico: ≥ 3 letture) |

Non ti spamma: una regola già segnalata non si ripete finché non si "spegne" e riaccende,
a meno che il prezzo non scenda ancora. Se un prodotto non è leggibile per 3 controlli di fila
(layout cambiato, CAPTCHA, pagina sparita) ricevi un avviso dedicato.

## Storico pregresso

Lo scraping parte da oggi: Amazon non espone lo storico. Se ne hai uno da un'altra fonte
(es. un export, o dati copiati a mano) importalo con un CSV di colonne `date,price`:

```
python -m prezzallocchio import-history B0C1234567 vecchi_prezzi.csv
```

(date `YYYY-MM-DD` o `GG/MM/AAAA`, prezzi anche in formato `59,90`; l'import è idempotente.)

## Uso locale

```
pip install -r requirements.txt
python -m prezzallocchio check --dry-run   # legge i prezzi senza scrivere né inviare nulla
python -m prezzallocchio check             # aggiorna storico e invia alert
python -m prezzallocchio report            # riepilogo (min/max/media/andamento)
pip install pytest && pytest
```
Per i test in locale con Telegram: esporta `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`;
senza, gli alert vengono solo stampati.

## Limiti da conoscere

- **Amazon non vuole bot.** Lo scraping va contro i loro termini d'uso e gli IP dei runner di GitHub
  (datacenter) vengono spesso bloccati con CAPTCHA/503. Se succede: metti un proxy residenziale
  in `PROXY_URL`, oppure esegui il check da casa (cron su PC/Raspberry). Se *tutti* i prodotti falliscono,
  il workflow diventa rosso e GitHub ti manda una mail.
- I selettori HTML dei prezzi (`scraper.py`) sono stati verificati solo su una pagina d'esempio,
  non su Amazon reale: al primo giro controlla l'output del workflow. Se Amazon cambia layout basta
  aggiornare `PRICE_SELECTORS`.
- Un prodotto non disponibile (senza prezzo) conta come lettura fallita, non viene registrato.
- Per storico vero e affidabile e nessun blocco, l'alternativa è la [API di Keepa](https://keepa.com/#!api)
  (a pagamento): il resto del codice non cambia, basta sostituire `scraper.fetch`.
- GitHub può disattivare i cron dopo 60 giorni di inattività del repo; i commit automatici
  dello storico di norma tengono il repo "attivo", ma se smette di girare riattivalo da Actions.
