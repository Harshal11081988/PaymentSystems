import pandas as pd
import streamlit as st
from core.db import init_db, list_transactions, ledger_invariant_check

st.set_page_config(page_title="Observability", page_icon="📊", layout="wide")
init_db()

st.title("📊 Observability Dashboard")
st.caption("Operational view of the payment system — the kind of monitoring layer a "
           "real payments platform runs continuously (state distribution, failure rate by rail, reconciliation drift).")

txns = list_transactions(limit=2000)
if not txns:
    st.info("No transaction data yet — go make some transfers first.")
    st.stop()

df = pd.DataFrame([dict(t) for t in txns])
df["created_at"] = pd.to_datetime(df["created_at"])
df["updated_at"] = pd.to_datetime(df["updated_at"])
df["latency_ms"] = (df["updated_at"] - df["created_at"]).dt.total_seconds() * 1000

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total transactions", len(df))
c2.metric("Settled", int((df["status"] == "SETTLED").sum()))
c3.metric("Failed", int((df["status"] == "FAILED").sum()))
fail_rate = (df["status"] == "FAILED").mean() * 100
c4.metric("Failure rate", f"{fail_rate:.1f}%")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Status distribution")
    st.bar_chart(df["status"].value_counts())

with col2:
    st.subheader("Failure rate by rail")
    rail_stats = df.groupby("rail")["status"].apply(lambda s: (s == "FAILED").mean() * 100)
    st.bar_chart(rail_stats)

st.divider()
st.subheader("Settlement latency (ms)")
st.caption("Time between transaction creation and final status. Wallet-to-wallet should be ~0; external rails carry simulated delay.")
st.dataframe(
    df.groupby("rail")["latency_ms"].agg(["mean", "max", "count"]).round(2),
    use_container_width=True,
)

st.divider()
st.subheader("Transaction volume over time")
volume = df.set_index("created_at").resample("1min").size()
st.line_chart(volume)

st.divider()
st.subheader("Reconciliation")
healthy = ledger_invariant_check()
if healthy:
    st.success("✅ No drift detected — total debits equal total credits across the ledger.")
else:
    st.error("⚠️ Reconciliation mismatch — investigate ledger entries immediately.")
