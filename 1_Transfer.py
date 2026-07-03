import streamlit as st
from core.db import init_db, list_accounts, get_balance, transfer, InsufficientFunds, DuplicateTransaction
from core.rails import withdraw

st.set_page_config(page_title="Transfer", page_icon="💸", layout="wide")
init_db()

st.title("💸 Transfer Funds")

accounts = list_accounts()
if len(accounts) < 1:
    st.warning("Create at least one account on the Home page first.")
    st.stop()

acc_map = {f"{a['name']} ({a['id'][:8]}...)": a["id"] for a in accounts}

tab1, tab2 = st.tabs(["Wallet → Wallet", "Withdraw to Bank"])

with tab1:
    st.subheader("Wallet-to-wallet transfer")
    st.caption("Instant clearing and settlement — no external rail involved.")
    c1, c2 = st.columns(2)
    with c1:
        src_label = st.selectbox("From", list(acc_map.keys()), key="src")
    with c2:
        dest_label = st.selectbox("To", list(acc_map.keys()), key="dest")

    src_id = acc_map[src_label]
    dest_id = acc_map[dest_label]
    st.metric("Available balance", f"₹{get_balance(src_id)/100:,.2f}")

    amount = st.number_input("Amount (₹)", min_value=1.0, step=50.0)
    desc = st.text_input("Description", value="Wallet transfer")

    if st.button("Send transfer", type="primary"):
        if src_id == dest_id:
            st.error("Source and destination must differ.")
        else:
            try:
                txn_id = transfer(
                    source_account=src_id,
                    dest_account=dest_id,
                    amount_minor=int(amount * 100),
                    description=desc,
                )
                st.success(f"Transfer settled. Transaction ID: `{txn_id[:8]}...`")
            except InsufficientFunds:
                st.error("Insufficient funds in source wallet.")
            except DuplicateTransaction:
                st.warning("Duplicate transaction detected (idempotency key already used).")

with tab2:
    st.subheader("Withdraw to external bank (simulated rail)")
    st.caption("Goes through INITIATED → SETTLED/FAILED to mimic a real async bank rail.")
    acc_label = st.selectbox("From wallet", list(acc_map.keys()), key="wd_src")
    acc_id = acc_map[acc_label]
    st.metric("Available balance", f"₹{get_balance(acc_id)/100:,.2f}")
    wd_amount = st.number_input("Withdrawal amount (₹)", min_value=1.0, step=50.0, key="wd_amt")

    if st.button("Withdraw", type="primary"):
        try:
            txn_id = withdraw(acc_id, int(wd_amount * 100))
            st.success(f"Withdrawal submitted and settled. Transaction ID: `{txn_id[:8]}...`")
            st.info("Check the Ledger or Observability pages to see the final status.")
        except InsufficientFunds:
            st.error("Insufficient funds.")
