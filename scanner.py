import yfinance as yf
import pandas as pd
import requests

MIN_PRICE = 4.00
MAX_PRICE = 10.00
MIN_VOLUME = 1_000_000

BATCH_SIZE = 50
MAX_RESULTS = 20


def get_stock_list():
    """
    Get a broad current U.S. stock universe from NASDAQ Trader.
    """
    urls = [
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    ]

    symbols = set()

    for url in urls:
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            lines = response.text.splitlines()

            for line in lines[1:]:
                if not line or line.startswith("File Creation"):
                    continue

                parts = line.split("|")

                if "nasdaqlisted" in url:
                    symbol = parts[0]
                    test_issue = parts[3]
                else:
                    symbol = parts[1]
                    test_issue = parts[4]

                if (
                    symbol
                    and symbol.isalpha()
                    and test_issue == "N"
                ):
                    symbols.add(symbol)

        except Exception as e:
            print(f"Symbol list error: {e}")

    return sorted(symbols)


def check_batch(data, tickers):
    results = []

    if data is None or data.empty:
        return results

    for ticker in tickers:
        try:
            if ticker not in data.columns.get_level_values(1):
                continue

            stock = data.xs(ticker, axis=1, level=1)

            if "Close" not in stock or "Volume" not in stock:
                continue

            close = stock["Close"].dropna()
            volume = stock["Volume"].dropna()

            if len(close) < 60:
                continue

            price = float(close.iloc[-1])
            avg_volume = float(volume.tail(20).mean())

            # PRICE FILTER
            if price < MIN_PRICE or price > MAX_PRICE:
                continue

            # VOLUME FILTER
            if avg_volume < MIN_VOLUME:
                continue

            # MOVING AVERAGES
            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()

            # Check the last TWO trading days for a crossover.
            bullish = False
            bearish = False
            crossover_days_ago = None

            for days_ago in [0, 1]:
                today = -(days_ago + 1)
                yesterday = -(days_ago + 2)

                if (
                    ma5.iloc[yesterday] <= ma10.iloc[yesterday]
                    and ma5.iloc[today] > ma10.iloc[today]
                ):
                    bullish = True
                    crossover_days_ago = days_ago
                    break

                if (
                    ma5.iloc[yesterday] >= ma10.iloc[yesterday]
                    and ma5.iloc[today] < ma10.iloc[today]
                ):
                    bearish = True
                    crossover_days_ago = days_ago
                    break

            if not bullish and not bearish:
                continue

            separation = (
                (ma5.iloc[-1] - ma10.iloc[-1])
                / ma10.iloc[-1]
            ) * 100

            day_change = (
                (close.iloc[-1] - close.iloc[-2])
                / close.iloc[-2]
            ) * 100

            # Ranking:
            # 50% price movement
            # 50% MA separation
            score = (
                abs(day_change) * 0.50
                + abs(separation) * 0.50
            )

            results.append({
                "ticker": ticker,
                "price": round(price, 2),
                "signal": "Bullish" if bullish else "Bearish",
                "change": round(day_change, 2),
                "separation": round(separation, 2),
                "volume": int(avg_volume),
                "crossover_days_ago": crossover_days_ago,
                "score": round(score, 2)
            })

        except Exception:
            continue

    return results


def run_scanner():

    stocks = get_stock_list()

    print(f"Stocks found: {len(stocks)}")

    all_results = []

    # Process stocks in small batches to control memory.
    for start in range(0, len(stocks), BATCH_SIZE):

        batch = stocks[start:start + BATCH_SIZE]

        print(
            f"Scanning {start + 1}-"
            f"{min(start + BATCH_SIZE, len(stocks))} "
            f"of {len(stocks)}"
        )

        try:
            data = yf.download(
                batch,
                period="6mo",
                interval="1d",
                progress=False,
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                timeout=15
            )

            results = check_batch(data, batch)

            all_results.extend(results)

            # Release batch data before continuing.
            del data

        except Exception as e:
            print(f"Batch error: {e}")
            continue

    # Highest scores first.
    all_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return all_results[:MAX_RESULTS]


if __name__ == "__main__":

    results = run_scanner()

    print("\nRESULTS")
    print("=" * 60)

    for r in results:
        print(
            f"{r['ticker']:6} "
            f"${r['price']:7.2f} "
            f"{r['signal']:7} "
            f"Change {r['change']:6.2f}% "
            f"MA Sep {r['separation']:6.2f}% "
            f"Score {r['score']:5.2f}"
        )
