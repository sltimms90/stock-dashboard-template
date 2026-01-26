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
    c1.metric("Investment P&L (Gross)", f"NT$ {gross_investment_pnl:,.0f}", delta="Pre-Fee Performance")
    c2.metric("Total Fees & Interest", f"-NT$ {total_expenses:,.0f}", delta="Expenses", delta_color="inverse")
    c3.metric("Cumulative Net P&L", f"NT$ {net_lifetime_pnl:,.0f}", delta="Net After Fees")

    # 3. CURRENT POSITION
    st.markdown("### 🟢 Current Position")
    
    # Allocation Chart
    alloc_df = pd.DataFrame({
        'Category': ['Bonds', 'Equities', 'Cash'],
        'Value': [bond_val, equity_val, cash_val]
    })
    
    st.caption(f"📊 **Allocation:** Bonds: {bond_pct:.1%} | Equities: {equity_pct:.1%} | Cash: {cash_pct:.1%}")
    
    chart = alt.Chart(alloc_df).mark_bar(size=35).encode(
        x=alt.X('Value', axis=None, stack='normalize'),
        color=alt.Color('Category', scale=alt.Scale(domain=['Bonds', 'Equities', 'Cash'], range=['#1f77b4', '#2ca02c', '#7f7f7f']), legend=None),
        tooltip=['Category', alt.Tooltip('Value', format=',.0f')]
    ).properties(height=40)
    st.altair_chart(chart, use_container_width=True)
    
    # Metrics
    col_a, col_b, col_c = st.columns(3)
    curr_return_pct = (unrealized_profit / total_cost_basis * 100) if total_cost_basis else 0
    
    col_a.metric("Unrealized Gains", f"NT$ {unrealized_profit:,.0f}", delta=f"{curr_return_pct:.2f}% Return")
    col_b.metric("Stock Market Value", f"NT$ {stock_value:,.0f}")
    col_c.metric("Portfolio Age", "Since Jan 2026", delta=f"{inception_return_pct:.2f}% Inception Rtn")

    # 4. HOLDINGS TABLE (With Formatted Columns)
    if not df.empty:
        # Prepare Data
        df["Weight"] = (df["Market_Value"] / stock_value)
        
        # Sort
        df_sorted = df.sort_values(by="Market_Value", ascending=False).copy()
        
        # Select Columns for Display (Keep numbers numeric for sorting!)
        display_df = df_sorted[["Name", "Ticker", "Current_Price", "Shares", "Market_Value", "Weight", "Unrealized_Gain", "Gain_Pct"]]

        # Add Total Row
        total_row = pd.DataFrame([{
            "Name": "TOTALS", 
            "Ticker": "", 
            "Current_Price": None, 
            "Shares": None, 
            "Market_Value": stock_value, 
            "Weight": 1.0, 
            "Unrealized_Gain": unrealized_profit, 
            "Gain_Pct": (unrealized_profit/total_cost_basis) if total_cost_basis else 0
        }])
        
        final_table = pd.concat([display_df, total_row], ignore_index=True)

        # Configure Column Formats
        st.dataframe(
            final_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Name": "Company",
                "Current_Price": st.column_config.NumberColumn("Price", format="NT$ %.1f"),
                "Market_Value": st.column_config.NumberColumn("Market Value", format="NT$ %.0f"),
                "Unrealized_Gain": st.column_config.NumberColumn("Unrealized", format="NT$ %.0f"),
                "Weight": st.column_config.ProgressColumn("Weight", format="%.1f%%", min_value=0, max_value=1),
                "Gain_Pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
                "Shares": st.column_config.NumberColumn("Shares", format="%.0f"),
            }
        )

    st.markdown("---")

    # 5. BANKED PROFITS
    st.markdown("### 🔒 Realized & Banked")
    rc1, rc2, rc3 = st.columns(3)
    total_banked = realized_profit + total_dividends
    
    rc1.metric("Total Banked Cash", f"NT$ {total_banked:,.0f}")
    rc2.metric("Realized Sales", f"NT$ {realized_profit:,.0f}")
    rc3.metric("Dividends Received", f"NT$ {total_dividends:,.0f}")

    st.caption("Values in NTD. Real-time data via TWSE (twstock) with Yahoo Finance fallback.")

except Exception as e:
    st.error(f"Error loading dashboard: {e}")
