import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt

# --- CONFIGURATION ---
st.set_page_config(page_title="My Portfolio", layout="wide")

# Custom CSS for the "Hero" number and table alignment
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
    /* Make the metrics look like cards */
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
# Corrected Name Map (Grok was right!)
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
    
    # Fetch Data via yfinance
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
    df["Cost_Value"] = df["Shares"] * df["Cost_Basis"]
    df["Unrealized_Gain"] = df["Market_Value"] - df["Cost_Value"]
    df["Gain_Pct"] = (df["Unrealized_Gain"] / df["Cost_Value"]) * 100
    
    # Add Name Mapping
    df["Name"] = df["Ticker"].map(NAME_MAP).fillna(df["Ticker"])
    
    return df

try:
    df = load_holdings()
    
    # Portfolio Aggregates
    stock_value = df["Market_Value"].sum() if not df.empty else 0
    total_cost_basis = df["Cost_Value"].sum() if not df.empty else 0
    unrealized_profit = df["Unrealized_Gain"].sum() if not df.empty else 0
    total_assets = stock_value + total_cash
    
    # P&L Logic
    gross_investment_pnl = unrealized_profit + realized_profit + total_dividends
    net_lifetime_pnl = gross_investment_pnl - total_expenses
    
    # Allocation Logic
    bond_val = df[df["Ticker"].str.contains("00725")]["Market_Value"].sum() if not df.empty else 0
    equity_val = stock_value - bond_val
    cash_val = total_cash
    
    # --- LAYOUT START ---

    # SECTION 1: HERO HEADER (Total Assets)
    st.markdown(f'<div class="hero-label">TOTAL ASSETS (Stocks + Cash)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-metric">NT$ {total_assets:,.0f}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # SECTION 2: HIGH LEVEL SUMMARY
    c1, c2, c3 = st.columns(3)
    
    c1.metric(
        "Investment P&L (Gross)", 
        f"NT$ {gross_investment_pnl:,.0f}",
        delta="Pre-Fee Performance",
        help="Realized + Unrealized + Dividends (Before Expenses)"
    )
    
    c2.metric(
        "Total Fees & Interest", 
        f"- NT$ {total_expenses:,.0f}",
        delta="Expenses",
        delta_color="inverse"
    )
    
    c3.metric(
        "Cumulative Net P&L", 
        f"NT$ {net_lifetime_pnl:,.0f}",
        delta="Net After Fees",
        help="This is your final profit after paying the bank."
    )

    # SECTION 3: CURRENT POSITION & ALLOCATION
    st.markdown("### 🟢 Current Position")
    
    # Allocation Chart (Colorful!)
    alloc_df = pd.DataFrame({
        'Category': ['Bonds', 'Equities', 'Cash'],
        'Value': [bond_val, equity_val, cash_val],
        'Color': ['#1f77b4', '#2ca02c', '#7f7f7f'] # Blue, Green, Gray
    })
    # Calculate percentages for label
    alloc_df['Percentage'] = alloc_df['Value'] / total_assets
    
    # Create horizontal stacked bar
    chart = alt.Chart(alloc_df).mark_bar(size=30).encode(
        x=alt.X('Value', axis=None, stack='normalize'),
        color=alt.Color('Category', scale=alt.Scale(domain=['Bonds', 'Equities', 'Cash'], range=['#4c78a8', '#59a14f', '#bab0ac']), legend=None),
        tooltip=['Category', alt.Tooltip('Value', format=',.0f'), alt.Tooltip('Percentage', format='.1%')]
    ).properties(height=40)
    
    st.caption("📊 Portfolio Allocation")
    st.altair_chart(chart, use_container_width=True)
    
    # Metric Row
    col_a, col_b, col_c = st.columns(3)
    curr_return_pct = (unrealized_profit / total_cost_basis * 100) if total_cost_basis else 0
    
    col_a.metric("Unrealized Gains", f"NT$ {unrealized_profit:,.0f}", delta=f"{curr_return_pct:.2f}% Return")
    col_b.metric("Stock Market Value", f"NT$ {stock_value:,.0f}")
    col_c.metric("Portfolio Age", "Since Jan 2026")

    # Holdings Table with TOTALS
    if not df.empty:
        # Calculate Weight
        df["Weight"] = (df["Market_Value"] / stock_value) * 100
        
        # Sort by Market Value
        df_sorted = df.sort_values(by="Market_Value", ascending=False).copy()
        
        # Prepare Display Data
        display_df = pd.DataFrame()
        display_df["Company"] = df_sorted["Name"]
        display_df["Ticker"] = df_sorted["Ticker"]
        display_df["Price"] = df_sorted["Current_Price"].map("NT$ {:,.1f}".format)
        display_df["Shares"] = df_sorted["Shares"]
        display_df["Market Value"] = df_sorted["Market_Value"]
        display_df["Weight"] = df_sorted["Weight"].map("{:.1f}%".format)
        display_df["Unrealized"] = df_sorted["Unrealized_Gain"]
        display_df["Return"] = df_sorted["Gain_Pct"].map("{:,.2f}%".format)
        
        # ADD TOTAL ROW
        total_row = pd.DataFrame({
            "Company": ["TOTALS"],
            "Ticker": [""],
            "Price": [""],
            "Shares": [""], # Summing shares of different stocks makes no sense
            "Market Value": [stock_value],
            "Weight": ["100%"],
            "Unrealized": [unrealized_profit],
            "Return": [f"{(unrealized_profit/total_cost_basis*100):.2f}%"]
        })
        
        # Format the numbers for the main rows (converting to string)
        # We do this *after* calculating totals so we can do math
        display_df["Market Value"] = display_df["Market Value"].map("NT$ {:,.0f}".format)
        display_df["Unrealized"] = display_df["Unrealized"].map("NT$ {:,.0f}".format)
        
        # Format the totals row
        total_row["Market Value"] = total_row["Market Value"].map("NT$ {:,.0f}".format)
        total_row["Unrealized"] = total_row["Unrealized"].map("NT$ {:,.0f}".format)

        # Combine
        final_table = pd.concat([display_df, total_row], ignore_index=True)
        
        st.dataframe(final_table, use_container_width=True, hide_index=True)

    st.markdown("---")

    # SECTION 4: BANKED PROFITS
    st.markdown("### 🔒 Realized & Banked")
    rc1, rc2, rc3 = st.columns(3)
    total_banked = realized_profit + total_dividends
    
    rc1.metric("Total Banked Cash", f"NT$ {total_banked:,.0f}", help="Cash actually received")
    rc2.metric("Realized Sales", f"NT$ {realized_profit:,.0f}")
    rc3.metric("Dividends Received", f"NT$ {total_dividends:,.0f}")

    st.caption("Values in NTD. Data delayed by 15 mins (Yahoo Finance).")

except Exception as e:
    st.error(f"Error loading dashboard: {e}")
