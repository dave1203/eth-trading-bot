
import streamlit as st
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime, timezone

st.set_page_config(page_title="ETH Trading Assistant", page_icon="📊", layout="centered")
st.title("📊 ETH Trading Signal Assistant")
st.warning("Nur Analyse. Keine automatische Orderausführung. Signale sind unsicher und garantieren keine Gewinne.")

# Telegram Secrets
try:
    TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = str(st.secrets.get("TELEGRAM_CHAT_ID", ""))
except Exception:
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def telegram_send(message):
    if not TOKEN or not CHAT_ID:
        return False, "Telegram-Zugangsdaten fehlen in Streamlit Secrets."
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=15)
        data = r.json()
        if r.ok and data.get("ok"):
            return True, "Telegram-Nachricht gesendet."
        return False, f"Telegram-Fehler: {data.get('description', r.status_code)}"
    except Exception as e:
        return False, f"Telegram-Verbindung fehlgeschlagen: {e}"

@st.cache_data(ttl=60)
def load_eth(interval, limit=250):
    url = "https://data-api.binance.vision/api/v3/klines"
    response = requests.get(
        url,
        params={"symbol": "ETHUSDT", "interval": interval, "limit": limit},
        timeout=20
    )
    response.raise_for_status()
    raw = response.json()

    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]

    df = pd.DataFrame(raw, columns=cols)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

timeframe = st.selectbox(
    "Zeitrahmen",
    ["5m", "15m", "1h", "4h"],
    index=1
)

fast_ema = st.slider("Schneller EMA", 5, 30, 9)
slow_ema = st.slider("Langsamer EMA", 15, 100, 21)
rsi_period = st.slider("RSI-Periode", 5, 30, 14)

risk_pct = st.slider(
    "Risiko pro Trade (%)",
    0.1, 2.0, 0.5, 0.1
)

account_size = st.number_input(
    "Challenge-Kontogröße ($)",
    min_value=100,
    value=5000,
    step=500
)

stop_pct = st.slider(
    "Stop-Loss-Abstand (%)",
    0.2, 3.0, 1.0, 0.1
)

st.caption("Kursdaten: ETH/USDT · Binance öffentliche Marktdaten")

if st.button("🔄 Daten aktualisieren", use_container_width=True):
    st.cache_data.clear()

try:
    df = load_eth(timeframe)

    df["ema_fast"] = df["close"].ewm(
        span=fast_ema, adjust=False
    ).mean()

    df["ema_slow"] = df["close"].ewm(
        span=slow_ema, adjust=False
    ).mean()

    df["rsi"] = calc_rsi(df["close"], rsi_period)

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(latest["close"])
    rsi = float(latest["rsi"])

    if (
        latest["ema_fast"] > latest["ema_slow"]
        and previous["ema_fast"] <= previous["ema_slow"]
        and rsi < 70
    ):
        signal = "LONG"

    elif (
        latest["ema_fast"] < latest["ema_slow"]
        and previous["ema_fast"] >= previous["ema_slow"]
        and rsi > 30
    ):
        signal = "SHORT"

    elif latest["ema_fast"] > latest["ema_slow"] and rsi < 65:
        signal = "LONG (Trend)"

    elif latest["ema_fast"] < latest["ema_slow"] and rsi > 35:
        signal = "SHORT (Trend)"

    else:
        signal = "WAIT"

    st.metric("ETH/USDT", f"${price:,.2f}")
    st.metric("RSI", f"{rsi:.1f}")
    st.metric("Signal", signal)

    st.line_chart(
        df.set_index("time")[["close", "ema_fast", "ema_slow"]]
    )

    st.dataframe(
        df[["time", "close", "ema_fast", "ema_slow", "rsi"]].tail(10),
        use_container_width=True
    )

    risk_dollars = account_size * risk_pct / 100

    stop_price_long = price * (1 - stop_pct/100)
    stop_price_short = price * (1 + stop_pct/100)

    target_long = price * (1 + 2*stop_pct/100)
    target_short = price * (1 - 2*stop_pct/100)

    st.subheader("Risikorechner (Beispiel, kein Trade)")
    st.write(f"Risiko bei {risk_pct:.1f}%: **${risk_dollars:.2f}**")

    st.write(
        f"LONG – SL: ${stop_price_long:,.2f} "
        f"· TP (2R): ${target_long:,.2f}"
    )

    st.write(
        f"SHORT – SL: ${stop_price_short:,.2f} "
        f"· TP (2R): ${target_short:,.2f}"
    )

    st.caption(
        "Beispielwerte. Gebühren, Slippage und Challenge-Regeln "
        "sind nicht berücksichtigt."
    )

    msg = (
        f"📊 ETH SIGNAL\n"
        f"Signal: {signal}\n"
        f"Preis: ${price:,.2f}\n"
        f"RSI: {rsi:.1f}\n"
        f"Zeitrahmen: {timeframe}\n"
        f"Zeit (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n"
        "⚠️ Nur Analyse, keine Order ausgeführt."
    )

    if st.button("📨 Signal an Telegram senden", use_container_width=True):
        ok, text = telegram_send(msg)
        (st.success if ok else st.error)(text)

except Exception as e:
    st.error(f"Fehler beim Laden der ETH-Daten: {e}")
    st.info(
        "Wenn Binance Vision nicht erreichbar ist, "
        "kann die Serverregion oder Verbindung blockiert sein."
    )

st.divider()

if st.button("📨 Telegram-Test senden", use_container_width=True):
    ok, text = telegram_send(
        "✅ Telegram-Test: ETH Trading Assistant ist verbunden."
    )
    (st.success if ok else st.error)(text)

st.caption(
    "Nur Analyse. Keine Anlageberatung. "
    "Keine automatische Ausführung. Kein Gewinnversprechen."
)
