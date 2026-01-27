import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import twstock  # Requires: pip install twstock lxml
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="My Portfolio", layout="wide")

# Custom CSS
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

# --- HELPER: ROBUST REAL-TIME PRICE FETCHER (Grok's Logic) ---
def get_realtime_price(ticker_yf):
    ticker_clean = ticker_yf.split('.')[0]  # e.g., '00725B' or '2330'
    
    # print(f"Fetching for {ticker_yf}...")  # Uncomment for debugging logs
    
    # 1. Try TWSTOCK (real-time attempt)
    try:
        stock_data = twstock.realtime.get(ticker_clean)
        
        if stock_data.get('success', False):
            realtime_info = stock_data.get('realtime', {})
            price_str = realtime_info.get('latest_trade_price', '-')
            
            # Check if price is valid (not '-' which means no trade yet)
            if price_str != '-' and price_str.strip() and float(price_str) > 0:
                return float(price_str)
            
    except Exception as e:
        print(f"twstock failed for {ticker_yf}: {e}")
    
    # 2. Fallback to Yahoo (usually last close)
    try:
        ticker_obj = yf.Ticker(ticker_yf)
        data = ticker_obj.history(period="1d", prepost=False)
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except Exception as e:
        print(f"Yahoo failed for {ticker_yf}: {e}")
    
    return 0.0

# --- DATA MAPPING ---
NAME_MAP = {
    "2330.TW": "TSMC (Taiwan Semi)",
    "2382.TW": "Quanta Computer",
    "00725B.TWO": "Cathay Inv. Grade Bond",
    "00725B.TW": "Cathay Inv. Grade Bond"
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
    
    # Calculate % Return (Multiply by 100 for display)
    df["Gain_Pct"] = (df["Unrealized_Gain"] / df["Cost_Value"]) * 100
    
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
    
    # Inception Return
    invested_capital = total_cost_basis + total_cash
    inception_return_pct = (gross_investment_pnl / invested_capital * 100) if invested_capital else 0

    # Allocation
    bond_val = df[df["Ticker"].str.contains("00725")]["Market_Value"].sum() if not df.empty else 0
    equity_val = stock_value - bond_val
    cash_val = total_cash
    
    bond_pct = (bond_val / total_assets) if total_assets else 0
    equity_pct = (equity_val / total_assets) if total_assets else 0
    cash_pct = (cash_val / total_assets) if total_assets else 0

    # --- LAYOUT ---
    
    # REFRESH BUTTON
    if st.button("🔄 Refresh Data"):
        st.rerun()

    # 1. HERO HEADER
    st.markdown(f'<div class="hero-label">TOTAL ASSETS (Stocks + Cash)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-metric">NT$ {total_assets:,.0f}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # 2. SUMMARY METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric(
        label="Investment P&L (Gross)",
        value=f"NT$ {gross_investment_pnl:,.0f}",
        delta="Pre-Fee Performance"
    )
    c2.metric(
        label="Total Fees & Interest",
        value=f"-NT$ {total_expenses:,.0f}",
        delta="Expenses",
        delta_color="inverse"
    )
    c3.metric(
        label="Cumulative Net P&L",
        value=f"NT$ {net_lifetime_pnl:,.0f}",
        delta="Net After Fees"
    )

    # 3. CURRENT POSITION
    st.markdown("### 🟢 Current Position")
    
    # Allocation Chart
    alloc_df = pd.DataFrame({
        'Category': ['Bonds', 'Equities', 'Cash'],
        'Value': [bond_val, equity_val, cash_val]
    })
    
    st.caption(f"📊 **Allocation:** Bonds: {bond_pct:.1
