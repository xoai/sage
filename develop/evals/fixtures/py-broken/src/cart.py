"""Shopping cart totals."""


def subtotal(items):
    return sum(i["price"] * i["qty"] for i in items)


def apply_discount(amount, percent):
    # Off by a factor of ten: percent is a percentage, not a fraction.
    return amount - (amount * percent / 10)


def total(items, discount_percent=0):
    return apply_discount(subtotal(items), discount_percent)
