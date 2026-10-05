import pytest

from prezzallocchio.alerts import evaluate, new_alerts
from prezzallocchio.config import Product, parse_ref


def test_target_and_drop():
    p = Product("A" * 10, target_price=50, drop_pct=10)
    fired = evaluate(p, 45.0, [60.0, 55.0])
    assert set(fired) == {"target", "drop"}


def test_nothing_fires():
    assert evaluate(Product("A" * 10, target_price=40, drop_pct=10), 52.0, [55.0]) == {}


def test_historic_low_needs_enough_history():
    p = Product("A" * 10)
    assert evaluate(p, 10.0, [20.0, 30.0]) == {}
    assert "low" in evaluate(p, 10.0, [20.0, 30.0, 25.0])
    assert evaluate(p, 22.0, [20.0, 30.0, 25.0]) == {}


def test_dedup_only_realerts_on_further_drop():
    fired = {"target": "x"}
    assert new_alerts(fired, {}, 40.0) == ["target"]
    assert new_alerts(fired, {"target": 40.0}, 40.0) == []
    assert new_alerts(fired, {"target": 40.0}, 41.0) == []
    assert new_alerts(fired, {"target": 40.0}, 38.0) == ["target"]


def test_parse_ref():
    assert parse_ref("B0C1234567") == ("B0C1234567", None)
    assert parse_ref("https://www.amazon.de/Foo-Bar/dp/B0C1234567/ref=sr_1_1?x=1") == ("B0C1234567", "amazon.de")
    with pytest.raises(ValueError):
        parse_ref("ciao")
