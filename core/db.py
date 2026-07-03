"""
Core persistence layer for the payment system.
Uses SQLite for zero-config local + Streamlit Cloud deployment.
All money is stored as integer minor units (e.g. paise) — never floats.
"""
import sqlite3
import uuid
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "payments.db")


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'WALLET',   -- WALLET | EXTERNAL_RAIL
                currency TEXT NOT NULL DEFAULT 'INR',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE,
                type TEXT NOT NULL,                     -- TRANSFER | TOPUP | WITHDRAWAL
                status TEXT NOT NULL,                    -- INITIATED|CLEARED|SETTLED|FAILED|REVERSED
                source_account TEXT,
                dest_account TEXT,
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                rail TEXT NOT NULL DEFAULT 'WALLET',
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ledger_entries (
                id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                direction TEXT NOT NULL CHECK (direction IN ('DEBIT','CREDIT')),
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (transaction_id, account_id, direction),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            );
            """
        )
    ensure_system_accounts()


def create_account(name: str, acc_type: str = "WALLET", currency: str = "INR", fixed_id=None) -> str:
    acc_id = fixed_id or str(uuid.uuid4())
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM accounts WHERE id=?", (acc_id,)).fetchone()
        if existing:
            return acc_id
        conn.execute(
            "INSERT INTO accounts (id, name, type, currency, created_at) VALUES (?,?,?,?,?)",
            (acc_id, name, acc_type, currency, _now()),
        )
    return acc_id


def ensure_system_accounts():
    create_account("External Bank Rail", acc_type="EXTERNAL_RAIL", fixed_id="sys_external_bank")
    create_account("External Card Rail", acc_type="EXTERNAL_RAIL", fixed_id="sys_external_card")


def system_account_for_rail(rail: str) -> str:
    return {"BANK": "sys_external_bank", "CARD": "sys_external_card"}.get(rail, "sys_external_bank")


def list_accounts(include_system=False):
    with get_conn() as conn:
        if include_system:
            return conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        return conn.execute(
            "SELECT * FROM accounts WHERE type != 'EXTERNAL_RAIL' ORDER BY created_at"
        ).fetchall()


def get_balance(account_id: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN direction='CREDIT' THEN amount_minor ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN direction='DEBIT' THEN amount_minor ELSE 0 END), 0) AS balance
            FROM ledger_entries WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
        return row["balance"] if row else 0


def _post_double_entry(conn, txn_id, source_account, dest_account, amount_minor, currency):
    """Writes the debit/credit pair. Must sum to zero — this is the core invariant."""
    ts = _now()
    if source_account:
        conn.execute(
            "INSERT INTO ledger_entries (id, transaction_id, account_id, direction, amount_minor, currency, created_at) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), txn_id, source_account, "DEBIT", amount_minor, currency, ts),
        )
    if dest_account:
        conn.execute(
            "INSERT INTO ledger_entries (id, transaction_id, account_id, direction, amount_minor, currency, created_at) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), txn_id, dest_account, "CREDIT", amount_minor, currency, ts),
        )


class InsufficientFunds(Exception):
    pass


class DuplicateTransaction(Exception):
    pass


def transfer(
    source_account: str,
    dest_account: str,
    amount_minor: int,
    currency: str = "INR",
    idempotency_key: str | None = None,
    txn_type: str = "TRANSFER",
    rail: str = "WALLET",
    description: str = "",
    allow_overdraft: bool = False,
) -> str:
    """
    Executes a clearing + (for WALLET rail) immediate settlement transfer.
    For external rails (TOPUP/WITHDRAWAL), status is left at CLEARED — a
    separate settle_transaction() call simulates the async rail confirming.
    """
    idempotency_key = idempotency_key or str(uuid.uuid4())

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if existing:
            raise DuplicateTransaction(existing["id"])

        if source_account and not allow_overdraft:
            bal = get_balance(source_account)
            if bal < amount_minor:
                raise InsufficientFunds(f"balance {bal} < amount {amount_minor}")

        txn_id = str(uuid.uuid4())
        ts = _now()
        status = "CLEARED" if rail == "WALLET" else "INITIATED"

        conn.execute(
            """INSERT INTO transactions
               (id, idempotency_key, type, status, source_account, dest_account,
                amount_minor, currency, rail, description, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (txn_id, idempotency_key, txn_type, status, source_account, dest_account,
             amount_minor, currency, rail, description, ts, ts),
        )

        # Wallet-internal transfers settle immediately (clearing == settlement).
        # External rail transactions post ledger entries only on settle_transaction().
        if rail == "WALLET":
            _post_double_entry(conn, txn_id, source_account, dest_account, amount_minor, currency)
            conn.execute(
                "UPDATE transactions SET status='SETTLED', updated_at=? WHERE id=?",
                (_now(), txn_id),
            )

        return txn_id


def settle_transaction(txn_id: str, success: bool = True):
    """Simulates an external rail adapter confirming settlement asynchronously."""
    with get_conn() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
        if not txn or txn["status"] not in ("INITIATED", "CLEARED"):
            return
        if success:
            _post_double_entry(
                conn, txn_id, txn["source_account"], txn["dest_account"],
                txn["amount_minor"], txn["currency"],
            )
            conn.execute("UPDATE transactions SET status='SETTLED', updated_at=? WHERE id=?", (_now(), txn_id))
        else:
            conn.execute("UPDATE transactions SET status='FAILED', updated_at=? WHERE id=?", (_now(), txn_id))


def list_transactions(limit: int = 200):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


def list_ledger_entries(account_id: str | None = None, limit: int = 500):
    with get_conn() as conn:
        if account_id:
            return conn.execute(
                "SELECT * FROM ledger_entries WHERE account_id=? ORDER BY created_at DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM ledger_entries ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


def ledger_invariant_check() -> bool:
    """Global double-entry check: total debits must equal total credits."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN direction='DEBIT' THEN amount_minor ELSE 0 END) AS debits,
                SUM(CASE WHEN direction='CREDIT' THEN amount_minor ELSE 0 END) AS credits
            FROM ledger_entries
            """
        ).fetchone()
        debits = row["debits"] or 0
        credits = row["credits"] or 0
        return debits == credits
