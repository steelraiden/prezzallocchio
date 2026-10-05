from prezzallocchio import cli, store


def test_import_history_and_report(tmp_path, capsys):
    (tmp_path / "products.toml").write_text('[[products]]\nasin = "B0C1234567"\nname = "Cuffie"\n')
    csv_file = tmp_path / "old.csv"
    csv_file.write_text("date;price\n01/01/2025;59,90\n2025-02-01;49,90\n2025-03-01;54,00\n")
    args = ["--config", str(tmp_path / "products.toml"), "--data", str(tmp_path / "data")]

    assert cli.main(args + ["import-history", "B0C1234567", str(csv_file)]) == 0
    assert cli.main(args + ["import-history", "B0C1234567", str(csv_file)]) == 0  # idempotente
    history = store.read_history(tmp_path / "data" / "history.csv")
    assert [p.price for p in history["B0C1234567"]] == [59.9, 49.9, 54.0]

    assert cli.main(args + ["report"]) == 0
    out = capsys.readouterr().out
    assert "Cuffie" in out and "49.90" in out


def test_check_flow_dedup_and_retry(tmp_path, monkeypatch):
    from prezzallocchio import alerts, scraper

    (tmp_path / "products.toml").write_text('[[products]]\nasin = "B0C1234567"\nname = "Cuffie"\ntarget_price = 50\n')
    args = ["--config", str(tmp_path / "products.toml"), "--data", str(tmp_path / "data")]
    price = {"v": 60.0}
    sent, ok = [], {"v": True}

    monkeypatch.setattr(scraper, "fetch", lambda product, session: scraper.Offer(price["v"], "EUR", "T"))
    monkeypatch.setattr(alerts, "send_telegram", lambda text: (sent.append(text), ok["v"])[1])
    run = lambda: cli.main(args + ["check", "--delay", "0"])

    run()                                 # 60: nessun alert
    assert sent == []
    price["v"] = 45.0; ok["v"] = False
    run()                                 # 45: alert, ma l'invio fallisce
    assert len(sent) == 1
    ok["v"] = True
    run()                                 # riprova e va a buon fine
    assert len(sent) == 2
    run()                                 # stesso prezzo: nessun nuovo alert
    assert len(sent) == 2
    price["v"] = 40.0
    run()                                 # sceso ancora: nuovo alert
    assert len(sent) == 3
    price["v"] = 70.0
    run()                                 # risale: riarmo
    price["v"] = 45.0
    run()
    assert len(sent) == 4

    assert len(store.read_history(tmp_path / "data" / "history.csv")["B0C1234567"]) == 7
    assert "Cuffie" in (tmp_path / "data" / "REPORT.md").read_text()
