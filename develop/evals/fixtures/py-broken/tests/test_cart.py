import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.cart import subtotal, total


def test_subtotal():
    assert subtotal([{"price": 10, "qty": 2}]) == 20


def test_ten_percent_off_twenty_is_eighteen():
    assert total([{"price": 10, "qty": 2}], discount_percent=10) == 18
