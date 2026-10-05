import pytest

from prezzallocchio.scraper import Blocked, FetchError, parse_price, parse_product_page

PAGE = """
<html><body>
<span id="productTitle"> Cuffie Bluetooth XYZ </span>
<div id="corePrice_feature_div">
  <span class="a-price a-text-price"><span class="a-offscreen">99,99&nbsp;€</span></span>
  <span class="a-price"><span class="a-offscreen">1.234,56&nbsp;€</span></span>
</div>
</body></html>
"""


@pytest.mark.parametrize(
    "text,expected",
    [("1.234,56 €", 1234.56), ("€ 1,234.56", 1234.56), ("29,99€", 29.99), ("EUR 29.99", 29.99), ("1.234 €", 1234.0), ("19 €", 19.0)],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parse_price_none():
    assert parse_price("non disponibile") is None


def test_parse_page_ignores_struck_list_price():
    offer = parse_product_page(PAGE)
    assert offer.price == 1234.56
    assert offer.currency == "EUR"
    assert offer.title == "Cuffie Bluetooth XYZ"


def test_captcha_is_blocked():
    with pytest.raises(Blocked):
        parse_product_page('<form action="/errors/validateCaptcha">')


def test_missing_price():
    with pytest.raises(FetchError):
        parse_product_page("<html><span id='productTitle'>x</span></html>")
