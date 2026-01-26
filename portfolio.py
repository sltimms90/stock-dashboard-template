import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="My Portfolio", layout="wide")
# --- PASSWORD PROTECTION ---
# 1. Look for the password in secrets
if "app_password" in st.secrets:
    password = st.secrets["app_password"]
    
    # 2. Create a simple login box
    # If the user hasn't entered the password yet, show the input
    if "authenticated" not in st.session_state:
        entered_password = st.text_input("🔒 Enter Password to View Portfolio", type="password")
        if st.button("Login"):
            if entered_password == password:
                st.session_state["authenticated"] = True
                st.rerun()  # Refresh to show the app
            else:
                st.error("Wrong password")
        st.stop()  # Stop here, do not run the rest of the code!

# --- END PROTECTION ---
st.title("📈 My Leveraged Portfolio")

# 1. Load Data
holdings_data = st.secrets.get("holdings", [])
sales_data = st.secrets.get("sales", [])
dividends_data = st.secrets.get("dividends", [])
expenses_data = st.secrets.get("expenses", [])
cash_data = st.secrets.get("cash", [])

# 2. Calculate Totals
realized_profit = sum([item["Profit"] for item in sales_data]) if sales_data else 0
total_dividends = sum([item["Amount"] for item in dividends_data]) if dividends_data else 0
total_expenses = sum([item["Amount"] for item in expenses_data]) if expenses_data else 0
total_cash = sum([item["Amount"] for item in cash_data]) if cash_data else 0

# 3. Fetch Live Data
def load_holdings():
    if not holdings_data: return pd.DataFrame()
    df = pd.DataFrame(holdings_data)
    tickers = " ".join(df["Ticker"].tolist())
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
    return df

try:
    df = load_holdings()
    
    # Calculate Portfolio Totals
    stock_value = df["Market_Value"].sum() if not df.empty else 0
    unrealized_profit = df["Unrealized_Gain"].sum() if not df.empty else 0
    
    # TOTAL ASSETS = Stocks + Cash
    total_assets = stock_value + total_cash
    
    # NET LIFETIME PROFIT = (Unrealized + Realized + Divs) - Expenses
    net_lifetime_profit = (unrealized_profit + realized_profit + total_dividends) - total_expenses

    # 4. Display Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Net Lifetime Profit", f"${net_lifetime_profit:,.0f}", delta=f"{net_lifetime_profit:,.0f}")
    col2.metric("Total Expenses", f"-${total_expenses:,.0f}", delta_color="inverse")
    col3.metric("Total Assets (Stocks + Cash)", f"${total_assets:,.0f}")

    st.markdown("---")
    
    # Breakdown Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Value", f"${stock_value:,.0f}")
    c2.metric("Cash on Hand", f"${total_cash:,.0f}")
    c3.metric("Realized Sales", f"${realized_profit:,.0f}")
    c4.metric("Dividends", f"${total_dividends:,.0f}")

    if not df.empty:
        st.subheader("Current Holdings")
        # Format for display
        display_df = df.copy()
        display_df["Current_Price"] = display_df["Current_Price"].map("${:,.1f}".format)
        display_df["Market_Value"] = display_df["Market_Value"].map("${:,.0f}".format)
        display_df["Unrealized_Gain"] = display_df["Unrealized_Gain"].map("${:,.0f}".format)
        display_df["Gain_Pct"] = display_df["Gain_Pct"].map("{:,.2f}%".format)
        st.dataframe(display_df[["Ticker", "Shares", "Current_Price", "Market_Value", "Unrealized_Gain", "Gain_Pct"]], use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")

