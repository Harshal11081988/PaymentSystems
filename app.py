import streamlit as st
from core.db import init_db, list_accounts, create_account, get_balance, ledger_invariant_check
from core.rails import topup

st.set_page_config(page_title="Payment System", page_icon="💳", layout="wide")
init_db()

st.title("💳 Payment System — Demo Platform")
st.caption("A double-entry ledger wallet system modeling the four-corners payment model "
           "(payer → payer's institution → network → payee's institution → payee).")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("System Health")
    healthy = ledger_invariant_check()
    if healthy:
        st.success("✅ Ledger balanced (debits = credits)")
    else:
        st.error("⚠️ Ledger imbalance detected — reconciliation required")

    st.subheader("Create Account")
    with st.form("new_account", clear_on_submit=True):
        name = st.text_input("Account holder name")
        submitted = st.form_submit_button("Create Wallet")
        if submitted and name.strip():
            acc_id = create_account(name.strip())
            st.success(f"Created wallet for {name} ({acc_id[:8]}...)")
            st.rerun()

with col1:
    st.subheader("Accounts")
    accounts = list_accounts()
    if not accounts:
        st.info("No accounts yet — create one to get started.")
    for acc in accounts:
        bal = get_balance(acc["id"])
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.markdown(f"**{acc['name']}**  \n`{acc['id'][:8]}...`")
        c2.metric("Balance", f"₹{bal/100:,.2f}")
        with c3:
            with st.popover("Top up"):
                amt = st.number_input(
                    "Amount (₹)", min_value=1.0, step=100.0, key=f"topup_{acc['id']}"
                )
                if st.button("Confirm top-up", key=f"btn_{acc['id']}"):
                    topup(acc["id"], int(amt * 100), rail="BANK", description="Manual top-up")
                    st.rerun()
        st.divider()

st.markdown("---")
st.caption("Use the sidebar to Transfer funds, inspect the Ledger, or view the Observability dashboard.")
