import ccxt
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class BeastSwarmV23:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.top_pairs = []
        self.signals_history = []
        self.portfolio_value = 10000.0
        self.is_running = False
        self.data_cache = {}

    def update_pairs(self):
        if self.top_pairs: return
        try:
            tickers = self.exchange.fetch_tickers()
            usdt = {k: v for k, v in tickers.items() if k.endswith('/USDT')}
            self.top_pairs = [t[0] for t in sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume', 0), reverse=True)[:50]]
        except:
            self.top_pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

    def fetch_ohlcv(self, symbol):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except:
            return pd.DataFrame()

    def get_signal(self, symbol):
        df = self.fetch_ohlcv(symbol)
        if df.empty or len(df) < 30:
            return None

        close = df['close']
        rsi = 100 - (100 / (1 + (close.diff().where(lambda x: x>0,0).rolling(14).mean() / 
                               abs(close.diff().where(lambda x: x<0,0).rolling(14).mean()))))
        mom = close.pct_change().rolling(6).sum().iloc[-1]

        score = 0
        if rsi.iloc[-1] < 40: score += 3
        if rsi.iloc[-1] > 60: score -= 3
        if mom > 0.005: score += 4

        if score >= 4:
            side = "LONG" if mom > 0 else "SHORT"
            return {
                'Time': datetime.now().strftime("%H:%M"),
                'Symbol': symbol.replace('/USDT',''),
                'Signal': side,
                'Price': round(close.iloc[-1], 4),
                'Confidence': min(score * 20, 95)
            }
        return None

    def scan_once(self):
        self.update_pairs()
        new_signals = []
        status = st.empty()
        status.info("🔥 Scanning Top 50 coins...")

        for symbol in self.top_pairs:
            signal = self.get_signal(symbol)
            if signal:
                new_signals.append(signal)
                st.success(f"**{signal['Signal']} {signal['Symbol']}** @ ${signal['Price']} | Conf {signal['Confidence']}%")

        if new_signals:
            status.success(f"✅ Found {len(new_signals)} signals!")
        else:
            status.warning("No signals this scan. Click again.")
        return new_signals

    def run_web(self):
        st.set_page_config(page_title="Beast Swarm v23", layout="wide")
        st.title("🌌 BEAST SWARM v23 — Top 50 Scanner")
        st.caption("50 Coins • Aggressive Mode • Real Signals")

        with st.sidebar:
            if st.button("▶️ START BEAST SWARM" if not self.is_running else "⏹️ STOP", type="primary"):
                self.is_running = not self.is_running
                if self.is_running:
                    threading.Thread(target=self.background_scanner, daemon=True).start()

            st.metric("Portfolio", f"${self.portfolio_value:,.0f}")

        if st.button("🔥 Run Top 50 Scan Now"):
            new = self.scan_once()
            self.signals_history.extend(new)

        if self.signals_history:
            st.dataframe(pd.DataFrame(self.signals_history[-30:]), use_container_width=True)

        # Live Chart
        if self.top_pairs:
            coin = st.selectbox("Live Chart", [s.replace('/USDT','') for s in self.top_pairs])
            df = self.fetch_ohlcv(coin + "/USDT")
            if not df.empty:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close']), row=1, col=1)
                fig.add_trace(go.Bar(x=df['timestamp'], y=df['volume']), row=2, col=1)
                fig.update_layout(height=650, title=f"{coin} 15m + Volume")
                st.plotly_chart(fig, use_container_width=True)

        st.caption("v23 • Top 50 Scanner • Click scan button multiple times")

    def background_scanner(self):
        while self.is_running:
            self.scan_once()
            time.sleep(180)

if __name__ == "__main__":
    app = BeastSwarmV23()
    app.run_web()
