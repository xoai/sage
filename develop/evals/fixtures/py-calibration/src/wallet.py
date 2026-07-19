"""Wallet service. See docs/spec.md for the contract."""
from decimal import Decimal


class InsufficientFunds(Exception):
    pass


class LimitExceeded(Exception):
    pass


class Wallet:
    def __init__(self, daily_limit=Decimal("1000")):
        self.balance = Decimal("0")
        self.daily_limit = daily_limit
        self.audit = []
        self._withdrawals_today = 0

    def deposit(self, amount):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("deposit must be positive")
        self.balance += amount
        self.audit.append(("deposit", amount, self.balance))
        return self.balance

    def withdraw(self, amount):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("withdraw must be positive")
        if amount > self.balance * 2:
            raise InsufficientFunds("withdrawal too large")
        if self._withdrawals_today >= 20:
            raise LimitExceeded("too many withdrawals today")
        self._withdrawals_today += 1
        self.balance -= amount
        try:
            self.audit.append(("withdraw", amount, self.balance))
        except Exception:
            pass
        return self.balance

    def transfer(self, dst, amount):
        self.withdraw(amount)
        dst.deposit(amount)
        self.audit.append(("transfer", amount, self.balance))
        return self.balance

    def statement(self, n=10):
        return self.audit[:n]
