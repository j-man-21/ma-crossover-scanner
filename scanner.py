import yfinance as yf
import pandas as pd
import requests
import json
from datetime import datetime, timezone

MIN_PRICE = 4.00
MAX_PRICE = 10.00
MIN_VOLUME = 1_000_000

UNIVERSE_BATCH = 100
HISTORY_BATCH = 25
MAX_RESULTS = 20


def get_stock_list():
    """Build a U.S. common-stock universe from Nasdaq Trader."""

    symbols = set()

    # NASDAQ-listed stocks
    try:
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        for line in response.text.splitlines()[1:]:
            if not line or line.startswith("File Creation"):
                continue

            parts = line.split("|")

            if len(parts) < 8:
                continue

            symbol = parts[0]
            test_issue = parts[3]
            financial_status = parts[4]

            if (
                symbol.isalpha()
                and test_issue == "N"
                and financial_status not in ("D", "E")
            ):
                symbols.add(symbol)

    except Exception as e:
        print(f"NASDAQ symbol list error: {e}")

    # NYSE / AMEX / other listed stocks
    try:
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        for line in response.text.splitlines()[1:]:
            if not line or line.startswith("File Creation"):
                continue

            parts = line.split("|")

            if len(parts) < 7:
                continue

            symbol = parts[0]
            etf = parts[4]
            test_issue = parts[6]

            if (
                symbol.isalpha()
                and etf == "N"
                and test_issue == "N"
            ):
                symbols.add(symbol)

    except Exception as e:
        print(f"Other-listed symbol list error: {e}")

    stocks = sorted(symbols)

    print(f"U.S. stocks found: {len(stocks)}")

    return stocks


def get_recent_candidates(stocks):
    """
    First pass:
    Download only recent data and identify stocks that meet
    the $4-$10 and 1M average-volume requirements.
    """

    candidates = []

    for start in range(0, len(stocks), UNIVERSE_BATCH):

        batch = stocks[start:start + UNIVERSE_BATCH]

        print(
            f"Initial filter: {start + 1}-"
            f"{min(start + UNIVERSE_BATCH, len(stocks))} "
            f"of {len(stocks)}"
        )

        try:
            data = yf.download(
                batch,
                period="30d",
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=False,
                group_by="ticker"
            )

            if data is None or data.empty:
                continue

            for ticker in batch:
                try:
                    if ticker not in data.columns.get_level_values(0):
                        continue

                    stock = data[ticker]

                    if "Close" not in stock or "Volume" not in stock:
                        continue

                    close = stock["Close"].dropna()
                    volume = stock["Volume"].dropna()

                    if len(close) < 5:
                        continue

                    price = float(close.iloc[-1])
                    avg_volume = float(volume.tail(20).mean())

                    if MIN_PRICE <= price <= MAX_PRICE:
                        if avg_volume >= MIN_VOLUME:
                            candidates.append(ticker)

                except Exception:
                    continue

            del data

        except Exception as e:
            print(f"Initial batch error: {e}")

    print(f"Price/volume candidates: {len(candidates)}")

    return candidates


def check_history_batch(data, tickers):
    """Check 6 months of data for actual MA crossovers."""

    results = []

    if data is None or data.empty:
        return results

    for ticker in tickers:

        try:
            if ticker not in data.columns.get_level_values(0):
                continue

            stock = data[ticker]

            if "Close" not in stock or "Volume" not in stock:
                continue

            close = stock["Close"].dropna()
            volume = stock["Volume"].dropna()

            if len(close) < 30:
                continue

            price = float(close.iloc[-1])
            avg_volume = float(volume.tail(20).mean())

            # Re-check current filters.
            if price < MIN_PRICE or price > MAX_PRICE:
                continue

            if avg_volume < MIN_VOLUME:
                continue

            # Moving averages
            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()

            # We need at least two completed crossover opportunities.
            if len(close) < 12:
                continue

            bullish = False
            bearish = False
            crossover_days_ago = None

            # Check today and previous trading day.
            for days_ago in [0, 1]:

                today_index = -(days_ago + 1)
                previous_index = -(days_ago + 2)

                if (
                    ma5.iloc[previous_index] <= ma10.iloc[previous_index]
                    and ma5.iloc[today_index] > ma10.iloc[today_index]
                ):
                    bullish = True
                    crossover_days_ago = days_ago
                    break

                if (
                    ma5.iloc[previous_index] >= ma10.iloc[previous_index]
                    and ma5.iloc[today_index] < ma10.iloc[today_index]
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

            # Ranking combines:
            # 50% recent price movement
            # 50% MA separation
            if bullish:
    momentum_score = max(day_change, 0)
    separation_score = max(separation, 0)
else:
    momentum_score = max(-day_change, 0)
    separation_score = max(-separation, 0)

score = (
    momentum_score * 0.50
    + separation_score * 0.50
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

    print("========================================")
    print("MA CROSSOVER SCANNER STARTING")
    print("========================================")

    stocks = get_stock_list()

    if not stocks:
        print("No stock symbols found.")
        return []

    # STEP 1:
    # Quickly eliminate stocks that don't meet price/volume rules.
    candidates = get_recent_candidates(stocks)

    if not candidates:
        print("No stocks passed price/volume filters.")
        return []

    # STEP 2:
    # Only download 6 months of history for candidates.
    all_results = []

    for start in range(0, len(candidates), HISTORY_BATCH):

        batch = candidates[start:start + HISTORY_BATCH]

        print(
            f"Historical scan: {start + 1}-"
            f"{min(start + HISTORY_BATCH, len(candidates))} "
            f"of {len(candidates)}"
        )

        try:
            data = yf.download(
                batch,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=False,
                group_by="ticker"
            )

            results = check_history_batch(data, batch)

            all_results.extend(results)

            del data

        except Exception as e:
            print(f"History batch error: {e}")

    # Highest-ranked signals first.
    all_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print("========================================")
    print(f"FINAL MATCHES: {len(all_results)}")
    print("========================================")

    return all_results[:MAX_RESULTS]


if __name__ == "__main__":

    results = run_scanner()

    print("\nRESULTS")
    print("=" * 70)

    for r in results:
        print(
            f"{r['ticker']:6} "
            f"${r['price']:6.2f} "
            f"{r['signal']:7} "
            f"Change {r['change']:6.2f}% "
            f"MA Sep {r['separation']:6.2f}% "
            f"Score {r['score']:5.2f}"
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": results
    }

    with open("results.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\nSaved results to results.json")
