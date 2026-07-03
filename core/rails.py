"""
Simulated external rail adapters — stand-ins for a real bank RTGS/ACH or
card network connection. Each adapter exposes the same interface so a real
integration (e.g. Razorpay, Stripe, UPI) can be swapped in later without
touching the payment orchestration logic.
"""
import random
import time
from core.db import transfer, settle_transaction, system_account_for_rail

RAIL_FAILURE_RATE = {
    "BANK": 0.03,
    "CARD": 0.05,
}


def topup(account_id: str, amount_minor: int, rail: str = "BANK", description: str = "Top-up") -> str:
    """Money enters the system from an external rail into a wallet."""
    sys_acc = system_account_for_rail(rail)
    txn_id = transfer(
        source_account=sys_acc,
        dest_account=account_id,
        amount_minor=amount_minor,
        rail=rail,
        txn_type="TOPUP",
        description=description,
        allow_overdraft=True,  # the external clearing account has no "real" balance limit
    )
    _simulate_async_settlement(txn_id, rail)
    return txn_id


def withdraw(account_id: str, amount_minor: int, rail: str = "BANK", description: str = "Withdrawal") -> str:
    """Money leaves the wallet out to an external rail."""
    sys_acc = system_account_for_rail(rail)
    txn_id = transfer(
        source_account=account_id,
        dest_account=sys_acc,
        amount_minor=amount_minor,
        rail=rail,
        txn_type="WITHDRAWAL",
        description=description,
    )
    _simulate_async_settlement(txn_id, rail)
    return txn_id


def _simulate_async_settlement(txn_id: str, rail: str):
    """
    In a real system this would be a webhook/callback arriving later.
    Here we simulate it synchronously so the demo is self-contained,
    but the transaction still passes through INITIATED -> SETTLED/FAILED
    so the state machine and observability dashboard are meaningful.
    """
    failure_rate = RAIL_FAILURE_RATE.get(rail, 0.02)
    success = random.random() > failure_rate
    time.sleep(0.05)  # nominal processing delay
    settle_transaction(txn_id, success=success)
