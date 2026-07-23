import yfinance as yf
import pandas as pd


# Your screener rules
MIN_PRICE = 4
MAX_PRICE = 10
MIN_VOLUME = 1_000_000


def check_stock(ticker):

    try:
        data = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False
        )

        if len(data) < 20:
            return None

        close = data["Close"]
        volume = data["Volume"]

        current_price = float(close.iloc[-1])
        avg_volume = float(volume.tail(20).mean())

        # Price filter
        if current_price < MIN_PRICE or current_price > MAX_PRICE:
            return None

        # Volume filter
        if avg_volume < MIN_VOLUME:
            return None

        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()

        yesterday_cross = (
            ma5.iloc[-2] < ma10.iloc[-2]
            and ma5.iloc[-1] > ma10.iloc[-1]
        )

        yesterday_cross_down = (
            ma5.iloc[-2] > ma10.iloc[-2]
            and ma5.iloc[-1] < ma10.iloc[-1]
        )

        if not (yesterday_cross or yesterday_cross_down):
            return None

        separation = (
            (ma5.iloc[-1] - ma10.iloc[-1])
            / ma10.iloc[-1]
        ) * 100

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "volume": round(avg_volume),
            "signal": "Bullish" if yesterday_cross else "Bearish",
            "ma_separation": round(separation, 2)
        }

    except Exception:
        return None


print("Scanner ready")
