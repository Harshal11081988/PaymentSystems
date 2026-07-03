# 💳 Payment System — Double-Entry Ledger Wallet

A demo payment platform built around a real double-entry ledger, modeling the
"four corners" payment flow (payer → payer's institution → network → payee's
institution → payee). Includes simulated external rails (bank/card top-up and
withdrawal with async settlement), a transfer UI, a raw ledger inspector, and
an operational observability dashboard.

## Features
- **Double-entry ledger** — every transaction posts a balanced debit/credit pair; balances are derived, never mutated directly.
- **Idempotency keys** — prevents duplicate processing on retry.
- **Clearing vs. settlement** — wallet-to-wallet is instant; external rails (bank/card) simulate async settlement with a configurable failure rate.
- **System clearing accounts** — external rails post through `sys_external_bank` / `sys_external_card` accounts so the global ledger invariant (Σdebits = Σcredits) always holds, even across top-ups/withdrawals.
- **Observability dashboard** — status distribution, failure rate by rail, settlement latency, transaction volume, and a live reconciliation check.

## Project structure
```
payment-system/
├── app.py                    # Home page — accounts, balances, top-up
├── pages/
│   ├── 1_Transfer.py         # Wallet-to-wallet + withdrawal
│   ├── 2_Ledger.py           # Transactions + raw ledger entries
│   └── 3_Observability.py    # Metrics dashboard
├── core/
│   ├── db.py                 # SQLite double-entry ledger logic
│   └── rails.py              # Simulated external rail adapters
├── requirements.txt
└── .streamlit/config.toml
```

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501

## Push to GitHub
```bash
cd payment-system
git init
git add .
git commit -m "Initial commit: double-entry payment system demo"
git branch -M main
git remote add origin https://github.com/Harshal11081988/payment-system.git
git push -u origin main
```
(Create the empty repo on GitHub first, or run `gh repo create payment-system --public --source=. --push` if you have the GitHub CLI installed.)

## Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **New app**, select the `payment-system` repo, branch `main`, and set the main file path to `app.py`.
3. Click **Deploy**. Streamlit Cloud will install `requirements.txt` automatically.
4. Note: the SQLite file (`payments.db`) resets whenever the app redeploys or sleeps from inactivity, since Streamlit Cloud's filesystem isn't persistent — fine for a demo, but for a durable version swap `core/db.py` to a hosted Postgres (e.g. Supabase/Neon free tier) using the same schema.

## Extending it
- Swap `core/rails.py` for a real gateway (Razorpay/Stripe test mode) behind the same `topup()`/`withdraw()` interface.
- Add a fraud/velocity rules module that runs before `transfer()` commits.
- Move from SQLite to Postgres for concurrent-write safety before any real usage.
- Add authentication (Streamlit doesn't have built-in auth — `streamlit-authenticator` package is a quick option) before exposing this beyond a personal demo.

## Why double-entry
This mirrors the core mechanic described in traditional payment systems literature: settlement is the actual movement of funds, distinct from clearing, and finality matters. Modeling it as immutable ledger rows (rather than a single mutable balance column) is what makes the reconciliation check on the Observability page meaningful — it's structurally impossible for money to be created or destroyed without it showing up as an imbalance.
