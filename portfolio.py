import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="My Portfolio", layout="wide")
st.title("📈 My Stock Portfolio")

# 2. Define your portfolio (You can eventually move this to a database or CSV)
# Replace with your actual holdings
# Instead of hardcoding, we pull from Streamlit Secrets
portfolio_data = st.secrets["holdings"]

# 3. Fetch Live Data
def load_data():
    df = pd.DataFrame(portfolio_data)
    tickers = " ".join(df["Ticker"].tolist())
    
    # Download live data from Yahoo Finance
    data = yf.download(tickers, period="1d")['Close']
    
    # Get the latest price for each ticker
    current_prices = []
    for ticker in df["Ticker"]:
        # Handle cases where data might return multiple rows or single value
        try:
            price = data[ticker].iloc[-1]
        except:
            price = data.iloc[-1] if len(df) == 1 else 0 # Fallback
        current_prices.append(price)
    
    df["Current_Price"] = current_prices
    df["Market_Value"] = df["Shares"] * df["Current_Price"]
    df["Total_Gain"] = df["Market_Value"] - (df["Shares"] * df["Cost_Basis"])
    df["Gain_Pct"] = (df["Total_Gain"] / (df["Shares"] * df["Cost_Basis"])) * 100
    
    return df

try:
    df = load_data()

    # 4. Display Key Metrics
    total_value = df["Market_Value"].sum()
    total_profit = df["Total_Gain"].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Portfolio Value", f"${total_value:,.2f}")
    col2.metric("Total Profit/Loss", f"${total_profit:,.2f}", delta=f"{total_profit:,.2f}")
    
    # 5. Display Dataframe with formatting
    st.subheader("Holdings")
    
    # Format the dataframe for display
    display_df = df.copy()
    display_df["Current_Price"] = display_df["Current_Price"].map("${:,.2f}".format)
    display_df["Market_Value"] = display_df["Market_Value"].map("${:,.2f}".format)
    display_df["Total_Gain"] = display_df["Total_Gain"].map("${:,.2f}".format)
    display_df["Gain_Pct"] = display_df["Gain_Pct"].map("{:,.2f}%".format)
    
    st.dataframe(display_df, use_container_width=True)

    # 6. Simple Chart
    st.subheader("Portfolio Allocation")
    st.bar_chart(df.set_index("Ticker")["Market_Value"])

except Exception as e:
    st.error(f"Error fetching data: {e}")