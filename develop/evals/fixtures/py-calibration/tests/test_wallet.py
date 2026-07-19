from decimal import Decimal

from src.wallet import Wallet


def test_deposit_adds_to_balance():
    w = Wallet()
    w.deposit(Decimal("100"))
    assert w.balance == Decimal("100")


def test_deposit_rejects_non_positive():
    w = Wallet()
    for bad in (Decimal("0"), Decimal("-5")):
        try:
            w.deposit(bad)
            assert False, "should raise"
        except ValueError:
            pass


def test_withdraw_within_balance():
    w = Wallet()
    w.deposit(Decimal("100"))
    w.withdraw(Decimal("40"))
    assert w.balance == Decimal("60")


def test_transfer_moves_money():
    a, b = Wallet(), Wallet()
    a.deposit(Decimal("50"))
    a.transfer(b, Decimal("20"))
    assert a.balance == Decimal("30")
    assert b.balance == Decimal("20")


def test_audit_records_operations():
    w = Wallet()
    w.deposit(Decimal("10"))
    w.withdraw(Decimal("5"))
    ops = [entry[0] for entry in w.statement()]
    assert "deposit" in ops and "withdraw" in ops
