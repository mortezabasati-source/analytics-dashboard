"""Run the real dashboard with deterministic data and no database access."""

import runpy
import sys
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

import pandas as pd
import streamlit as st

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))


def get_test_date_boundaries():
    today = date.today()
    return today - timedelta(days=549), today


def load_test_data(start_date_str=None):
    today = date.today()
    dates = [today - timedelta(days=day) for day in range(550)]
    df = pd.DataFrame({
        "order_date": dates,
        "category": "Typ A",
        "product_name": "Testprodukt",
        "sales": 1000.0,
        "net_sales": 950.0,
        "return_sales": 50.0,
        "return_rate": 0.05,
        "quantity": 10,
        "return_quantity": 1,
        "store_name": "ICA Testbutik",
        "location": "Stockholm",
    })
    df["year_week_key"] = pd.to_datetime(df["order_date"]).dt.strftime("%Y-W%U")
    df["year_month_key"] = pd.to_datetime(df["order_date"]).dt.strftime("%Y-M%m")
    if start_date_str:
        df = df[df["order_date"] >= date.fromisoformat(start_date_str)]
    return df


# Replace only the database module, before loading the production entry point.
# Credentials and .env files are never read by this test server.
database = ModuleType("db")
database.load_data = load_test_data
database.get_date_boundaries = get_test_date_boundaries
sys.modules["db"] = database
runpy.run_path(str(SRC / "app.py"), run_name="__main__")

st.session_state.test_runs = st.session_state.get("test_runs", 0) + 1
st.button("Rerun dashboard")
st.text(f"Dashboard run: {st.session_state.test_runs}")
