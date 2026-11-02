
import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="ETH Signal Assistant", page_icon="📊", layout="wide")
st.title("📊 ETH Trading Signal Assistant")
st.caption("ETH/USDT · Analyse · Keine automatische Ausführung")
st.warning("Signale sind unsicher. Der Bot handelt nicht automatisch und garantiert keine Gewinne.")

@st.cache_data(ttl=60)
def get_data(interval):
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "ETHUSDT", "interval": interval, "limit": 200},
        timeout=15
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json(), columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "qv", "trades", "tb", "tq", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

interval = st.selectbox("Zeitrahmen", ["5m", "15m", "1h"], index=1)

if st.button("Daten aktualisieren"):
    st.cache_data.clear()

try:
    df = get_data(interval)
    df["ema9"] = df.close.ewm(span=9, adjust=False).mean()
    df["ema21"] = df.close.ewm(span=21, adjust=False).mean()
    df["rsi"] = calculate_rsi(df.close)

    last, prev = df.iloc[-1], df.iloc[-2]
    price = float(last.close)
    rsi = float(last.rsi)

    cross_up = prev.ema9 <= prev.ema21 and last.ema9 > last.ema21
    cross_down = prev.ema9 >= prev.ema21 and last.ema9 < last.ema21

    if cross_up and 50 <= rsi <= 70:
        signal = "LONG-KANDIDAT"
        reason = "EMA-Kreuzung nach oben und RSI passend."
    elif cross_down and 30 <= rsi <= 50:
        signal = "SHORT-KANDIDAT"
        reason = "EMA-Kreuzung nach unten und RSI passend."
    else:
        signal = "WAIT – WARTEN"
        reason = "Kein bestätigtes Kreuzungssignal."

    a, b, c = st.columns(3)
    a.metric("ETH/USDT", f"${price:,.2f}")
    b.metric("RSI", f"{rsi:.1f}")
    c.metric("Signal", signal)

    st.write(reason)
    st.caption("Kerzenzeit (UTC): " + str(last.time))

    st.subheader("ETH-Chart")
    st.line_chart(df.tail(100).set_index("time")[["close", "ema9", "ema21"]])

    st.subheader("Risikorechner – 5.000-$-Challenge")
    capital = st.number_input("Challenge-Größe ($)", min_value=100.0, value=5000.0)
    risk = st.number_input("Risiko (%)", min_value=0.1, max_value=2.0, value=0.25)
    stop = st.number_input("Stop-Abstand (%)", min_value=0.1, max_value=5.0, value=0.5)

    loss = capital * risk / 100
    position = loss / (stop / 100)
    st.metric("Rechnerischer Verlust am Stop", f"${loss:.2f}")
    st.metric("Positionswert rechnerisch", f"${position:.2f}")
    st.caption("Gebühren, Slippage und Challenge-Regeln sind nicht eingerechnet.")

except requests.RequestException:
    st.error("Marktdaten nicht erreichbar. Bitte später erneut versuchen.")
except Exception as e:
    st.error("Fehler beim Laden. Bitte Seite neu laden.")
    st.exception(e)

st.caption("Technische Indikatoren sind keine sichere Prognose. Keine Anlageberatung.")
