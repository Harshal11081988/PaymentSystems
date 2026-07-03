import pandas as pd
import streamlit as st
from core.db import init_db, list_transactions, list_ledger_entries, list_accounts, ledger_invariant_check

st.set_page_config(page_title="Ledger", page_icon="📒", layout="wide")
init_db()

st.title("📒 Ledger & Transactions")

healthy = ledger_invariant_check()
st.metric("Ledger integrity (Σdebits = Σcredits)", "✅ Balanced" if healthy else "⚠️ Imbalanced")

accounts = {a["id"]: a["name"] for a in list_accounts()}

st.subheader("Transactions")
txns = list_transactions()
if txns:
    df = pd.DataFrame([dict(t) for t in txns])
    df["source_name"] = df["source_account"].map(accounts).fillna("EXTERNAL")
    df["dest_name"] = df["dest_account"].map(accounts).fillna("EXTERNAL")
    df["amount"] = df["amount_minor"] / 100
    st.dataframe(
        df[["created_at", "type", "status", "rail", "source_name", "dest_name", "amount", "currency", "description"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No transactions yet.")

st.subheader("Raw Ledger Entries (double-entry rows)")
st.caption("Every transaction produces a balanced debit/credit pair — this is the system's source of truth.")
entries = list_ledger_entries()
if entries:
    edf = pd.DataFrame([dict(e) for e in entries])
    edf["account_name"] = edf["account_id"].map(accounts)
    edf["amount"] = edf["amount_minor"] / 100
    st.dataframe(
        edf[["created_at", "transaction_id", "account_name", "direction", "amount", "currency"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No ledger entries yet.")
