# Wallet service — specification

## §1 Deposit

`deposit(amount)` adds to the balance. Amounts must be positive;
zero or negative amounts raise `ValueError` and change nothing.

## §2 No overdraft

`withdraw(amount)` debits the balance. The balance must never go below
zero: a withdrawal exceeding the current balance raises
`InsufficientFunds` and changes nothing.

## §3 Atomic transfer

`transfer(dst, amount)` debits this wallet and credits `dst` as one
operation: if either side fails, NEITHER balance changes.

## §4 Daily withdrawal limit

The SUM of one day's withdrawals must not exceed `daily_limit`
(default 1000). A withdrawal that would push the day's total over the
limit raises `LimitExceeded` and changes nothing.

## §5 Audit trail

Every successful mutating operation (deposit, withdraw, transfer)
appends an audit record `(operation, amount, balance_after)`.

## §6 Statement

`statement(n=10)` returns the last `n` audit records, NEWEST FIRST.

## §7 Decimal only

Monetary amounts are `Decimal`. Passing a `float` to any operation
raises `TypeError` — floats silently corrupt cents.

## §8 Account closure

`close()` marks the wallet closed. Every subsequent mutating operation
on a closed wallet raises `ClosedWallet`. Reading the balance and the
statement stays allowed.

## §9 Monthly interest

`accrue_interest(rate)` applies one month's interest to the balance,
rounded half-even to cents, and appends an audit record.
