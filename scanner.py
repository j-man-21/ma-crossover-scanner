import time
import yfinance as yf
import pandas as pd
import requests


MIN_PRICE = 4
MAX_PRICE = 10
MIN_VOLUME = 1_000_000


def get_stock_list():

    url = (
        "https://raw.githubusercontent.com/"
        "datasets/s-and-p-500-companies/master/"
        "data/constituents.csv"
    )

    df = pd.read_csv(url)

    return df["Symbol"].tolist()


def check_stock(ticker):

    try:

        data = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            progress=False
        )

        if len(data) < 30:
            return None

        close = data["Close"].squeeze()
        volume = data["Volume"].squeeze()

        price = float(close.iloc[-1])
        avg_volume = float(volume.tail(20).mean())

        if price < MIN_PRICE or price > MAX_PRICE:
            return None

        if avg_volume < MIN_VOLUME:
            return None


        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()


        crossed_up = (
            ma5.iloc[-2] <= ma10.iloc[-2]
            and ma5.iloc[-1] > ma10.iloc[-1]
        )

        crossed_down = (
            ma5.iloc[-2] >= ma10.iloc[-2]
            and ma5.iloc[-1] < ma10.iloc[-1]
        )


        if not crossed_up and not crossed_down:
            return None


        separation = (
            (ma5.iloc[-1] - ma10.iloc[-1])
            / ma10.iloc[-1]
        ) * 100


        day_change = (
            (close.iloc[-1]-close.iloc[-2])
            / close.iloc[-2]
        ) * 100


        score = (
            abs(day_change) * .5
            + abs(separation) * .5
        )


        return {
            "ticker": ticker,
            "price": round(price,2),
            "signal":
                "Bullish" if crossed_up else "Bearish",
            "change":
                round(day_change,2),
            "separation":
                round(separation,2),
            "volume":
                int(avg_volume),
            "score":
                round(score,2)
        }


    except Exception:
        return None



if __name__ == "__main__":

    stocks = get_stock_list()

    results = []

    for i, stock in enumerate(stocks, start=1):

    print(f"Scanning {i}/{len(stocks)}: {stock}")

    if "." in stock:
        continue

    result = check_stock(stock)
        if result:
            results.append(result)


    results = sorted(
        results,
        key=lambda x: x["score"],
        reverse=True
    )


    print("RESULTS")
    print("----------------")

    for r in results[:20]:
        print(r)
