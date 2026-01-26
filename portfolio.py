import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import twstock  # Requires: pip install twstock

# --- CONFIGURATION ---
st.set_page_config(page_title="My Portfolio", layout="wide")

# Custom CSS for the Hero Section
st.markdown("""
    <style>
    .hero-metric {
        font-size: 3.5rem !important;
        font-weight: 700;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 0px;
    }
    .hero-label {
        font-size: 1.2rem;
        text-align: center;
        color: #555;
        margin-top: 20px;
    }
    div[data-testid="stMetric"] {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #eee;
    }
    </style>
""", unsafe_allow_html=True)

# --- PASSWORD PROTECTION ---
if "app_password" in st.secrets:
    password = st.secrets["app_password"]
    if "authenticated" not in st.session_state:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔒 Portfolio Login")
            entered_password = st.text_input("Enter Password", type="password")
            if st.button("Login"):
                if entered_password == password:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
        st.stop()

# --- HELPER: HYBRID PRICE FETCHER ---
def get_realtime_price(ticker_yf):
    """
    Tries to get real-time price from twstock (Taiwan SE).
    Falls back to yfinance (15m delay) if that fails.
    """
    ticker_clean = ticker_yf.split('.')[0]
    
    # 1. Try TWSTOCK (Real-time)
    try:
        if ticker_clean.isdigit():
            stock = twstock.realtime.get(ticker_clean)
            if stock['success']:
                price = stock['realtime'].get('latest_trade_price')
                if price and price != '-' and float(price) > 0:
                    return float(price)
    except Exception:
        pass 

    # 2. Fallback to YAHOO
    try:
        data = yf.Ticker(ticker_yf).history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        return 0.0
    return 0.0

# --- DATA MAPPING ---
NAME_MAP = {
    "2330.TW": "TSMC (Taiwan Semi)",
    "2382.TW": "Quanta Computer",
    "00725B.TWO": "Cathay Inv. Grade Bond",
    "00725B.TW": "Cathay Inv. Grade Bond" # Fallback if ticker format changes
}

# --- LOAD DATA ---
holdings_data = st.secrets.get("holdings", [])
sales_data = st.secrets.get("sales", [])
dividends_data = st.secrets.get("dividends", [])
expenses_data = st.secrets.get("expenses", [])
cash_data = st.secrets.get("cash", [])

# --- CALCULATIONS ---
realized_profit = sum([item["Profit"] for item in sales_data]) if sales_data else 0
total_dividends = sum([item["Amount"] for item in dividends_data]) if dividends_data else 0
total_expenses = sum([item["Amount"] for item in expenses_data]) if expenses_data else 0
total_cash = sum([item["Amount"] for item in cash_data]) if cash_data else 0

# Load Holdings
def load_holdings():
    if not holdings_data: return pd.DataFrame()
    df = pd.DataFrame(holdings_data)
    
    current_prices = []
    for ticker in df["Ticker"]:
        price = get_realtime_price(ticker)
        current_prices.append(price)
    
    df["Current_Price"] = current_prices
    df["Market_Value"] = df["Shares"] * df["Current_Price"]
    df["Cost_Value"] = df["Shares"] * df["Cost_Basis"]
    df["Unrealized_Gain"] = df["Market_Value"] - df["Cost_Value"]
    df["Gain_Pct"] = (df["Unrealized_Gain"] / df["Cost_Value"])
    df["Name"] = df["Ticker"].map(NAME_MAP).fillna(df["Ticker"])
    
    return df

try:
    df = load_holdings()
    
    # Aggregates
    stock_value = df["Market_Value"].sum() if not df.empty else 0
    total_cost_basis = df["Cost_Value"].sum() if not df.empty else 0
    unrealized_profit = df["Unrealized_Gain"].sum() if not df.empty else 0
    total_assets = stock_value + total_cash
    
    # P&L
    gross_investment_pnl = unrealized_profit + realized_profit + total_dividends
    net_lifetime_pnl = gross_investment_pnl - total_expenses
    
    # Inception Return (Gross Profit / Total Capital Employed)
    # Using Cost Basis + Cash as proxy for "Total Capital"
    inception_return_pct = (gross_investment_pnl / (total_cost_basis + total_cash) * 100) if (total_cost_basis + total_cash) else 0

    # Allocation
    bond_val = df[df["Ticker"].str.contains("00725")]["Market_Value"].sum() if not df.empty else 0
    equity_val = stock_value - bond_val
    cash_val = total_cash
    
    bond_pct = (bond_val / total_assets) if total_assets else 0
    equity_pct = (equity_val / total_assets) if total_assets else 0
    cash_pct = (cash_val / total_assets) if total_assets else 0

    # --- LAYOUT ---

    # 1. HERO HEADER
    st.markdown(f'<div class="hero-label">TOTAL ASSETS (Stocks + Cash)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-metric">NT$ {total_assets:,.0f}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # 2. SUMMARY METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Investment P&L (Gross)", f"NT$
