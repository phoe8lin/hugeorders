"""
20240911创建-超级大单扫描程序
20240912更新-自动扫描和简化表格
20240913更新-优化结果表格显示
20240914更新-添加价格信息和百分比变动

更新内容：
1. 添加大单的挂单价格
2. 添加标的的现价
3. 计算现价距离大单还需要涨/跌的百分比
4. 将默认运行间隔改为1分钟
5. 优化表格显示以包含新增信息
"""

import ccxt
from collections import defaultdict
import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

st.set_page_config(page_icon=":dart:", layout="wide")

# 创建交易所对象
exchange = ccxt.binance()

# 获取所有支持的交易对列表
markets = exchange.load_markets()
symbols = list(markets.keys())

# Streamlit 应用标题
st.title('Super Large Order Scanner')

# Streamlit 侧边栏
st.sidebar.title('Settings')

# 扫描间隔设置（默认为1分钟）
scan_interval = st.sidebar.slider('Scan Interval (minutes)', 1, 60, 1)

# 选择要扫描的交易对
selected_symbols = st.sidebar.multiselect('Select Trading Pairs to Scan', symbols, default=['BTC/USDT', 'ETH/USDT'])

def fetch_ticker(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        st.error(f"Error fetching ticker for {symbol}: {e}")
        return None

def fetch_and_aggregate_order_book(symbol, limit=1000):
    try:
        order_book = exchange.fetch_order_book(symbol, limit=limit)
        aggregated_bids = defaultdict(float)
        aggregated_asks = defaultdict(float)
        
        for price, amount in order_book['bids']:
            aggregated_bids[price] += amount
        for price, amount in order_book['asks']:
            aggregated_asks[price] += amount
        
        aggregated_bids = sorted(aggregated_bids.items(), key=lambda x: x[0], reverse=True)
        aggregated_asks = sorted(aggregated_asks.items(), key=lambda x: x[0])
        
        return aggregated_bids, aggregated_asks
    except Exception as e:
        st.error(f"Error fetching order book for {symbol}: {e}")
        return [], []

def check_large_orders(bids, asks, current_price):
    top_bids = sorted(bids, key=lambda x: x[1], reverse=True)[:5]
    top_asks = sorted(asks, key=lambda x: x[1], reverse=True)[:5]
    
    bid_top1_price, bid_top1_amount = top_bids[0]
    ask_top1_price, ask_top1_amount = top_asks[0]
    bid_top2to5_sum = sum(amount for _, amount in top_bids[1:5])
    ask_top2to5_sum = sum(amount for _, amount in top_asks[1:5])

    bid_ratio = bid_top1_amount / ask_top2to5_sum if ask_top2to5_sum != 0 else float('inf')
    ask_ratio = ask_top1_amount / bid_top2to5_sum if bid_top2to5_sum != 0 else float('inf')

    bid_percent_change = (bid_top1_price - current_price) / current_price * 100
    ask_percent_change = (ask_top1_price - current_price) / current_price * 100

    return (bid_top1_amount > ask_top2to5_sum, ask_top1_amount > bid_top2to5_sum, 
            bid_top1_price, ask_top1_price, bid_top1_amount, ask_top1_amount, 
            bid_top2to5_sum, ask_top2to5_sum, bid_ratio, ask_ratio, 
            bid_percent_change, ask_percent_change)

def scan_selected_symbols():
    large_orders = []
    for symbol in selected_symbols:
        current_price = fetch_ticker(symbol)
        if current_price is None:
            continue
        bids, asks = fetch_and_aggregate_order_book(symbol)
        if bids and asks:
            (large_bid, large_ask, bid_top1_price, ask_top1_price, bid_top1_amount, ask_top1_amount,
             bid_top2to5_sum, ask_top2to5_sum, bid_ratio, ask_ratio, 
             bid_percent_change, ask_percent_change) = check_large_orders(bids, asks, current_price)
            if large_bid or large_ask:
                large_orders.append({
                    'symbol': symbol,
                    'large_order_side': 'BID' if large_bid else 'ASK',
                    'current_price': current_price,
                    'large_order_price': bid_top1_price if large_bid else ask_top1_price,
                    'ratio': bid_ratio if large_bid else ask_ratio,
                    'percent_to_large_order': bid_percent_change if large_bid else ask_percent_change,
                    'top1_amount': bid_top1_amount if large_bid else ask_top1_amount,
                    'opposite_top2to5_sum': ask_top2to5_sum if large_bid else bid_top2to5_sum,
                    
                })
    return large_orders

def color_large_order_side(val):
    color = 'green' if val == 'BID' else 'red'
    return f'color: {color}; font-weight: bold'

def color_percent_change(val):
    color = 'green' if val > 0 else 'red'
    return f'color: {color}'

def main():
    st.subheader("Large Order Scanner")

    # 创建占位符
    status_placeholder = st.empty()
    result_placeholder = st.empty()

    while True:
        if selected_symbols:
            status_placeholder.info("Scanning...")
            large_orders = scan_selected_symbols()
            df = pd.DataFrame(large_orders)
            if not df.empty:
                styled_df = df.style.map(color_large_order_side, subset=['large_order_side'])
                styled_df = styled_df.map(color_percent_change, subset=['percent_to_large_order'])
                styled_df = styled_df.format({
                    'current_price': '{:,.4f}',
                    'large_order_price': '{:,.4f}',
                    'ratio': '{:.4f}',
                    'percent_to_large_order': '{:.4f}%',
                    'top1_amount': '{:,.4f}',
                    'opposite_top2to5_sum': '{:,.4f}',
                    
                })
                result_placeholder.dataframe(styled_df, use_container_width=True)
            else:
                result_placeholder.info("No large orders found in this scan.")
            scan_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
            status_placeholder.success(f"Last scan: {scan_time} (UTC+8)")
            time.sleep(scan_interval * 60)
        else:
            status_placeholder.warning("Please select at least one trading pair to start scanning.")
            time.sleep(5)  # 等待5秒后再次检查

if __name__ == "__main__":
    main()
