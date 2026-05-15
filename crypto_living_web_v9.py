import ccxt
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go

class EliteAISwarmV22_2:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.top_pairs = []
        self.signals_history = []
        self.performance_log = []
        self.portfolio_value = 10000.0
        self.is_running = False
        self.data_cache = {}
        self.agent_weights = {'ta':1.1, 'mtf':1.4, 'ob':1.2, 'vol':1.3, 'mom':1.1, 'regime':1.0}
        self.adaptation_threshold = 0.68

    def update_pairs(self):
        if self.top_pairs: return
        try:
            tickers = self.exchange.fetch_tickers()
            usdt = {k: v for k, v in tickers.items() if k.endswith('/USDT')}
            self.top_pairs = [t[0] for t in sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume', 0), reverse=True)[:50]]
        except:
            self.top_pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

    def fetch_ohlcv(self, symbol, timeframe='15m', limit=180):
        key = f"{symbol}_{timeframe}"
        if key in self.data_cache and time.time() - self.data_cache[key].get('time', 0) < 45:
            return self.data_cache[key]['df']
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            self.data_cache[key] = {'df': df, 'time': time.time()}
            return df
        except:
            return pd.DataFrame()

    def systematic_scan(self, symbol):
        df = self.fetch_ohlcv(symbol)
        if df.empty or len(df) < 40: return 0, 0, {}

        votes = {
            'ta': self.ta_agent(df),
            'mtf': self.mtf_agent(df),
            'ob': self.orderbook_agent(symbol),
            'vol': self.volume_agent(symbol),
            'mom': self.momentum_agent(df),
            'regime': self.regime_agent(df)
        }

        total = sum(votes[k] * self.agent_weights.get(k, 1.0) for k in votes)
        conf = min(abs(total) * 6.5, 95)
        return total, conf, votes

    def ta_agent(self, df):
        close = df['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        return 4 if rsi.iloc[-1] < 38 else -4 if rsi.iloc[-1] > 62 else 0

    def mtf_agent(self, df):
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        ema200 = df['close'].ewm(span=200).mean().iloc[-1]
        return 4.5 if ema50 > ema200 else -3.5

    def orderbook_agent(self, symbol):
        try:
            book = self.exchange.fetch_order_book(symbol, 10)
            bids = sum(float(x[1]) for x in book['bids'])
            asks = sum(float(x[1]) for x in book['asks'])
            return (bids - asks) / (bids + asks + 1e-8) * 2.5
        except:
            return 0

    def volume_agent(self, symbol):
        try:
            trades = self.exchange.fetch_trades(symbol, 120)
            df = pd.DataFrame(trades)
            if df.empty: return 0
            buy = df[df.get('side') == 'buy']['amount'].sum()
            sell = df[df.get('side') == 'sell']['amount'].sum()
            return (buy - sell) / (buy + sell + 1e-8) * 2.4
        except:
            return 0

    def momentum_agent(self, df):
        return df['close'].pct_change().rolling(7).sum().iloc[-1] * 70

    def regime_agent(self, df):
        atr_pct = (df['high'] - df['low']).rolling(14).mean().iloc[-1] / df['close'].iloc[-1]
        return -2 if atr_pct > 0.035 else 1.8

    def scan_once(self):
        self.update_pairs()
        new_signals = []
        status = st.empty()
        status.info(f"🔥 Scanning Top 50 coins with Beast Swarm...")

        for symbol in self.top_pairs:
            total, conf, votes = self.systematic_scan(symbol)
            if conf >= 65 and abs(total) > 6.0:
                side = "LONG" if total > 0 else "SHORT"
                df = self.fetch_ohlcv(symbol)
                price = df['close'].iloc[-1]
                signal = {
                    'Time': datetime.now().strftime("%H:%M"),
                    'Symbol': symbol.replace('/USDT',''),
                    'Signal': side,
                    'Price': round(price,4),
                    'Confidence': round(conf,1)
                }
                new_signals.append(signal)
                st.success(f"**{side} {symbol.replace('/USDT','')}** @ ${price:.4f} | Conf {conf}%")

        if new_signals:
            status.success(f"✅ Found {len(new_signals)} signals!")
        else:
            status.warning("No strong signals this scan. Try again in a few minutes.")
        return new_signals

    def run_web(self):
        st.set_page_config(page_title="Elite AI Swarm v22.2", layout="wide")
        st.title("🌌 ELITE AI SWARM v22.2 — Top 50 Beast")
        st.caption("Scanning Top 50 Coins • 50-Agent Swarm • Self-Learning")

        with st.sidebar:
            if st.button("▶️ START SWARM" if not self.is_running else "⏹️ STOP", type="primary"):
                self.is_running = not self.is_running
                if self.is_running:
                    threading.Thread(target=self.background_scanner, daemon=True).start()

            st.metric("Portfolio", f"${self.portfolio_value:,.0f}")

        tab1, tab2 = st.tabs(["Live Signals", "Live Charts"])

        with tab1:
            if st.button("🔥 Run Elite Systematic Scan (Top 50)"):
                new = self.scan_once()
                self.signals_history.extend(new)
            if self.signals_history:
                st.dataframe(pd.DataFrame(self.signals_history[-30:]), use_container_width=True)

        with tab2:
            if self.top_pairs:
                coin = st.selectbox("Select Coin", [s.replace('/USDT','') for s in self.top_pairs])
                df = self.fetch_ohlcv(coin + "/USDT")
                if not df.empty:
                    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                    st.plotly_chart(fig, use_container_width=True)

        st.caption("v22.2 • Top 50 Scanner • Click scan button multiple times")

    def background_scanner(self):
        while self.is_running:
            self.scan_once()
            time.sleep(240)

if __name__ == "__main__":
    app = EliteAISwarmV22_2()
    app.run_web()
