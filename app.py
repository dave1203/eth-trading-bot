
import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timezone

st.set_page_config(page_title="ETH Watcher V6", page_icon="📊")
st.title("📊 ETH Trading Signal Assistant")
st.warning("Keine automatische Trade-Ausführung. Signale sind unsicher.")

# Telegram Secrets
try:
    TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", ""))
except Exception:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def telegram_send(message):
    if not TOKEN or not CHAT_ID:
        return False, "Telegram Secrets fehlen!"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=15
        )
        response.raise_for_status()
        return True, "Telegram Nachricht gesendet!"
    except Exception as e:
        return False, str(e)

# Einstellungen
timeframe = st.selectbox("Zeitrahmen", ["5m", "15m", "1h"], index=1)
fast_ema = st.slider("Fast EMA", 5, 30, 9)
slow_ema = st.slider("Slow EMA", 20, 100, 21)
rsi_period = st.slider("RSI Periode", 5, 30, 14)

@st.cache_data(ttl=15)
def get_data(tf):
    response = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "ETHUSDT", "interval": tf, "limit": 250},
        timeout=15
    )
    response.raise_for_status()
    data = pd.DataFrame(response.json())
    data["close"] = data[4].astype(float)
    data["time"] = pd.to_datetime(data[0], unit="ms", utc=True)
    return data

def analyze(data):
    data["ema_fast"] = data["close"].ewm(span=fast_ema).mean()
    data["ema_slow"] = data["close"].ewm(span=slow_ema).mean()

    delta = data["close"].diff()
    gain = delta.clip(lower=0).rolling(rsi_period).mean()
    loss = -delta.clip(upper=0).rolling(rsi_period).mean()
    data["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    data["signal"] = np.where(
        (data["ema_fast"] > data["ema_slow"]) & (data["rsi"] >= 55),
        "LONG WATCH",
        np.where(
            (data["ema_fast"] < data["ema_slow"]) & (data["rsi"] <= 45),
            "EXIT WATCH",
            "WAIT"
        )
    )
    return data

# Telegram Test
if st.button("📨 Telegram Test senden"):
    success, message = telegram_send("✅ ETH Watcher V6 ist verbunden!")
    if success:
        st.success(message)
    else:
        st.error(message)

# Daten
try:
    data = analyze(get_data(timeframe))
    latest = data.iloc[-1]

    st.metric("ETH/USDT", f"${latest.close:,.2f}")
    st.metric("RSI", f"{latest.rsi:.1f}")
    st.metric("Signal", latest.signal)

    st.line_chart(
        data.set_index("time")[["close", "ema_fast", "ema_slow"]]
    )

    st.subheader("Telegram Monitoring")

    if "last_signal" not in st.session_state:
        st.session_state.last_signal = ""

    if st.button("▶ Signal prüfen und Telegram senden"):
        signal = str(latest.signal)
        if signal != "WAIT":
            success, message = telegram_send(
                f"📊 ETH SIGNAL\n\n"
                f"Signal: {signal}\n"
                f"Preis: ${latest.close:,.2f}\n"
                f"RSI: {latest.rsi:.1f}\n"
                f"Zeit: {datetime.now(timezone.utc).isoformat()}\n\n"
                f"⚠️ Keine Order ausgeführt."
            )
            st.success(message) if success else st.error(message)
        else:
            st.info("Aktuell kein Signal.")

except Exception as error:
    st.error(f"Fehler: {error}")

st.caption("Nur Analyse. Keine Anlageberatung. Keine automatische Ausführung.")
