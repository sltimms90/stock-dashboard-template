import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="My Portfolio", layout="wide")

# Custom CSS to make the "Hero" number huge and centered
st.markdown("""
    <style>
    .hero-metric {
        font-size: 3rem !important;
        font-weight: 700;
        text-align: center;
        color: #1f77b4;
    }
    .hero-label {
        font-size: 1.2rem;
        text-align: center;
        color: #555;
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

# --- DATA MAPPING ---
# Manual map for pretty names since yfinance can be slow/ugly with foreign names
NAME_MAP = {
    "2330.TW": "TSMC (Taiwan Semi)",
    "2382.TW": "Quanta Computer",
    "00725B.TWO": "Yuanta Inv. Grade Bond",
    "00725B.TW": "Yuanta Inv. Grade Bond"
}

# --- LOAD DATA ---
holdings_data = st.secrets.get("holdings", [])
sales_data = st.secrets.get("sales", [])
dividends_data = st.secrets.get("dividends", [])
expenses_data = st.secrets.get("expenses", [])
cash_data = st.secrets.get("cash", [])

# --- CALCULATIONS ---
# 1. Banked & Expenses
realized_profit = sum([item["Profit"] for item in sales_data]) if sales_data else 0
total_dividends = sum([item["Amount"] for item in dividends_data]) if dividends_data else 0
total_expenses = sum([item["Amount"] for item in expenses_data]) if expenses_data else 0
total_cash = sum([item["Amount"] for item in cash_data]) if cash_data else 0

# 2. Live Holdings
def load_holdings():
    if not holdings_data: return pd.DataFrame()
    df = pd.DataFrame(holdings_data)
    tickers = " ".join(df["Ticker"].tolist())
    
    # Fetch Data
    if len(df) > 0:
        data = yf.download(tickers, period="1d")['Close']
    
    current_prices = []
    for ticker in df["Ticker"]:
        try:
            if len(df) == 1: price = float(data.iloc[-1])
            else: price = float(data[ticker].iloc[-1])
        except: price = 0.0
        current_prices.append(price)
    
    df["Current_Price"] = current_prices
    df["Market_Value"] = df["Shares"] * df["Current_Price"]
    df["Unrealized_Gain"] = df["Market_Value"] - (df["Shares"] * df["Cost_Basis"])
    df["Gain_Pct"] = (df["Unrealized_Gain"] / (df["Shares"] * df["Cost_Basis"])) * 100
    
    # Add Name Mapping
    df["Name"] = df["Ticker"].map(NAME_MAP).fillna(df["Ticker"])
    
    return df

try:
    df = load_holdings()
    
    # Portfolio Aggregates
    stock_value = df["Market_Value"].sum() if not df.empty else 0
    unrealized_profit = df["Unrealized_Gain"].sum() if not df.empty else 0
    total_assets = stock_value + total_cash
    
    # P&L Logic
    gross_investment_pnl = unrealized_profit + realized_profit + total_dividends
    net_lifetime_pnl = gross_investment_pnl - total_expenses
    
    # Allocation Logic (Simple Heuristic)
    bond_val = df[df["Ticker"].str.contains("00725")]["Market_Value"].sum() if not df.empty else 0
    equity_val = stock_value - bond_val
    cash_val = total_cash
    
    bond_pct = (bond_val / total_assets) * 100 if total_assets else 0
    equity_pct = (equity_val / total_assets) * 100 if total_assets else 0
    cash_pct = (cash_val / total_assets) * 100 if total_assets else 0

    # --- LAYOUT START ---

    # SECTION 1: HERO HEADER (Total Assets)
    st.markdown(f'<div class="hero-label">TOTAL ASSETS (Stocks + Cash)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-metric">NT$ {total_assets:,.0f}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # SECTION 2: HIGH LEVEL SUMMARY (The "Truth" P&L)
    c1, c2, c3 = st.columns(3)
    
    # A. Investment Performance (Gross)
    c1.metric(
        "Investment P&L (Pre-Fees)", 
        f"${gross_investment_pnl:,.0f}",
        delta=f"Raw Returns",
        help="Realized + Unrealized + Dividends (Before Loan Interest)"
    )
    
    # B. The Cost of Business
    c2.metric(
        "Total Fees & Interest", 
        f"-${total_expenses:,.0f}",
        delta="Expenses",
        delta_color="inverse"
    )
    
    # C. The Bottom Line
    c3.metric(
        "Cumulative Net P&L", 
        f"${net_lifetime_pnl:,.0f}",
        delta=f"Net After Fees",
        help="This is your final profit after paying the bank."
    )

    # SECTION 3: CURRENT POSITION (Live Market)
    st.markdown("### 🟢 Current Position (Unrealized)")
    
    col_a, col_b, col_c = st.columns(3)
    
    # Portfolio Return % (Unrealized only)
    curr_return_pct = (unrealized_profit / stock_value * 100) if stock_value else 0
    
    col_a.metric("Unrealized Gains", f"${unrealized_profit:,.0f}", delta=f"{curr_return_pct:.2f}% Return")
    col_b.metric("Stock Market Value", f"${stock_value:,.0f}")
    col_c.metric("Portfolio Age", "Since Jan 2026") # Hardcoded start date for now
    
    # Allocation Bar
    st.caption(f"📊 **Allocation:** Bonds: {bond_pct:.1f}% | Equities: {equity_pct:.1f}% | Cash: {cash_pct:.1f}%")
    st.progress(int(bond_pct + equity_pct)) # Visual bar showing invested % vs cash

    # Holdings Table
    if not df.empty:
        # Calculate Weight
        df["Weight"] = (df["Market_Value"] / stock_value) * 100
        
        # Sort by Market Value (Biggest first)
        df_sorted = df.sort_values(by="Market_Value", ascending=False).copy()
        
        # Format for Display
        display_df = pd.DataFrame()
        display_df["Company"] = df_sorted["Name"]
        display_df["Ticker"] = df_sorted["Ticker"]
        display_df["Price"] = df_sorted["Current_Price"].map("${:,.1f}".format)
        display_df["Shares"] = df_sorted["Shares"]
        display_df["Market Value"] = df_sorted["Market_Value"].map("${:,.0f}".format)
        display_df["Weight"] = df_sorted["Weight"].map("{:.1f}%".format)
        display_df["Unrealized"] = df_sorted["Unrealized_Gain"].map("${:,.0f}".format)
        display_df["Return"] = df_sorted["Gain_Pct"].map("{:,.2f}%".format)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # SECTION 4: BANKED PROFITS (Locked In)
    st.markdown("### 🔒 Realized & Banked (Locked In)")
    
    rc1, rc2, rc3 = st.columns(3)
    
    total_banked = realized_profit + total_dividends
    
    rc1.metric("Total Banked Cash", f"${total_banked:,.0f}", help="Cash actually received from Sales + Dividends")
    rc2.metric("Realized Sales", f"${realized_profit:,.0f}")
    rc3.metric("Dividends Received", f"${total_dividends:,.0f}")

    # Footer
    st.caption("Values in NTD (TWD). Data delayed by 15 mins (Yahoo Finance).")

except Exception as e:
    st.error(f"Error loading dashboard: {e}")
