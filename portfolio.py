import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="My Portfolio", layout="wide")
st.title("📈 My Leveraged Portfolio")

# 2. Load Data
holdings_data = st.secrets.get("holdings", [])
sales_data = st.secrets.get("sales", [])
dividends_data = st.secrets.get("dividends", [])
expenses_data = st.secrets.get("expenses", [])

# 3. Calculate Financials
# A. Realized Profit (Past Sales)
realized_profit = 0
if sales_data:
    realized_profit = sum([item["Profit"] for item in sales_data])

# B. Dividends
total_dividends = 0
if dividends_data:
    total_dividends = sum([item["Amount"] for item in dividends_data])

# C. Expenses (Loan Interest, Fees, Taxes)
total_expenses = 0
if expenses_data:
    total_expenses = sum([item["Amount"] for item in expenses_data])

# 4. Fetch Live Data
def load_holdings():
    if not holdings_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(holdings_data)
    tickers = " ".join(df["Ticker"].tolist())
    
    if len(df) > 0:
        # Fetch data
        data = yf.download(tickers, period="1d")['Close']
    
    current_prices = []
    for ticker in df["Ticker"]:
        try:
            # Handle data structure variations
            if len(df) == 1:
                price = float(data.iloc[-1])
            else:
                price = float(data[ticker].iloc[-1])
        except:
            price = 0.0
        current_prices.append(price)
    
    df["Current_Price"] = current_prices
    df["Market_Value"] = df["Shares"] * df["Current_Price"]
    df["Unrealized_Gain"] = df["Market_Value"] - (df["Shares"] * df["Cost_Basis"])
    df["Gain_Pct"] = (df["Unrealized_Gain"] / (df["Shares"] * df["Cost_Basis"])) * 100
    
    return df

try:
    df = load_holdings()

    # 5. Calculate Totals
    if not df.empty:
        total_market_value = df["Market_Value"].sum()
        unrealized_profit = df["Unrealized_Gain"].sum()
        total_invested_capital = (df["Shares"] * df["Cost_Basis"]).sum()
    else:
        total_market_value = 0
        unrealized_profit = 0
        total_invested_capital = 0

    # The Logic: (Paper Gains + Real Cash + Dividends) - (Costs)
    gross_profit = unrealized_profit + realized_profit + total_dividends
    net_lifetime_profit = gross_profit - total_expenses

    # 6. Display Metrics
    # Top Row: The Big Picture
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Lifetime Profit", f"${net_lifetime_profit:,.0f}", 
                delta=f"{net_lifetime_profit:,.0f}", 
                help="Total Gains - Total Expenses")
    
    col2.metric("Total Expenses (Fees/Interest)", f"-${total_expenses:,.0f}", 
                delta_color="inverse")
    
    col3.metric("Portfolio Market Value", f"${total_market_value:,.0f}")

    # Second Row: Breakdown
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unrealized (Open)", f"${unrealized_profit:,.0f}", delta=f"{unrealized_profit:,.0f}")
    c2.metric("Realized Sales", f"${realized_profit:,.0f}")
    c3.metric("Dividends Collected", f"${total_dividends:,.0f}")
    c4.metric("Current Invested Capital", f"${total_invested_capital:,.0f}")

    # 7. Holdings Table
    if not df.empty:
        st.subheader("Current Holdings")
        display_df = df.copy()
        # Format columns
        display_df["Current_Price"] = display_df["Current_Price"].map("${:,.1f}".format)
        display_df["Market_Value"] = display_df["Market_Value"].map("${:,.0f}".format)
        display_df["Unrealized_Gain"] = display_df["Unrealized_Gain"].map("${:,.0f}".format)
        display_df["Gain_Pct"] = display_df["Gain_Pct"].map("{:,.2f}%".format)
        st.dataframe(display_df[["Ticker", "Shares", "Current_Price", "Market_Value", "Unrealized_Gain", "Gain_Pct"]], use_container_width=True)

    # 8. Expenses Log (Collapsible)
    with st.expander("🔻 View Expenses Log (Interest & Fees)"):
        if expenses_data:
            st.dataframe(pd.DataFrame(expenses_data))
        else:
            st.info("No expenses recorded yet.")

except Exception as e:
    st.error(f"Something went wrong: {e}")
