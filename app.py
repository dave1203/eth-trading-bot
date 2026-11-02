
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
    url = "https://data-api.binance.vision/api/v3/klines"
    response = requests.get(
        url,
        params={"symbol": "ETHUSDT", "interval": interval, "limit": 200},
        timeout=20,
    )
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise ValueError("Binance hat keine Kerzendaten geliefert.")
    columns = [
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(rows, columns=columns)
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df.dropna(subset=["close"])

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

interval = st.selectbox("Zeitrahmen", ["5m", "15m", "1h"], index=1)

if st.button("Daten aktualisieren"):
    st.cache_data.clear()

try:
    df = get_data(interval)
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["rsi"] = calculate_rsi(df["close"])

    last = df.iloc[-1]
    previous = df.iloc[-2]
    price = float(last["close"])
    rsi = float(last["rsi"])

    cross_up = previous["ema9"] <= previous["ema21"] and last["ema9"] > last["ema21"]
    cross_down = previous["ema9"] >= previous["ema21"] and last["ema9"] < last["ema21"]

    if cross_up and 50 <= rsi <= 70:
        signal = "LONG-KANDIDAT"
        reason = "EMA-Kreuzung nach oben und RSI im gewählten Bereich."
    elif cross_down and 30 <= rsi <= 50:
        signal = "SHORT-KANDIDAT"
        reason = "EMA-Kreuzung nach unten und RSI im gewählten Bereich."
    else:
        signal = "WAIT – WARTEN"
        reason = "Kein passendes EMA-Kreuzungssignal."

    col1, col2, col3 = st.columns(3)
    col1.metric("ETH/USDT", f"${price:,.2f}")
    col2.metric("RSI", f"{rsi:.1f}")
    col3.metric("Signal", signal)
    st.write(reason)
    st.caption(f"Letzte Kerze (UTC): {last['time']}")

    st.subheader("ETH-Chart")
    chart = df.tail(100).set_index("time")[["close", "ema9", "ema21"]]
    st.line_chart(chart)

    st.subheader("Risikorechner – 5.000-$-Challenge")
    capital = st.number_input("Challenge-Größe ($)", min_value=100.0, value=5000.0, step=100.0)
    risk = st.number_input("Risiko pro Trade (%)", min_value=0.1, max_value=2.0, value=0.25, step=0.05)
    stop_distance = st.number_input("Stop-Abstand (%)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)

    risk_amount = capital * risk / 100
    position_value = risk_amount / (stop_distance / 100)
    st.metric("Geplanter Verlust am Stop ($)", f"${risk_amount:,.2f}")
    st.metric("Rechnerischer Positionswert ($)", f"${position_value:,.2f}")
    st.caption("Nur mathematische Schätzung. Gebühren, Slippage, Hebel und Challenge-Regeln sind nicht berücksichtigt.")

except requests.RequestException as error:
    st.error("Marktdaten konnten nicht geladen werden. Prüfe die Verbindung oder versuche es später.")
    st.caption(f"Technischer Hinweis: {type(error).__name__}")
except (ValueError, IndexError) as error:
    st.error("Die Marktdaten sind leer oder unvollständig.")
    st.caption(f"Technischer Hinweis: {error}")
except Exception as error:
    st.error("Unerwarteter Fehler im Dashboard.")
    st.caption(f"Technischer Hinweis: {type(error).__name__}: {error}")

st.caption("Technische Indikatoren sind keine sichere Prognose. Keine Anlageberatung.")
