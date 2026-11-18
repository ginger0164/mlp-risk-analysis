"""Download raw market data for the PF1/PF2 market-risk study.

Run on your own computer (Python 3.9+, standard library only, no installs):

    python fetch_pf2_data.py

It creates a folder "pf2_raw_data" next to this script and a zip file
"pf2_raw_data.zip". Attach the zip in the chat.

What it downloads (raw, unmodified provider files):
  - Yahoo Finance daily chart JSON (prices, adjusted close, dividends, splits),
    2015-01-01 to today, for the 23 MLP names, SPY (market factor) and
    HYG (high-yield bond ETF, backup credit factor).
  - FRED daily series: DCOILWTICO (WTI oil, $/bbl), DGS10 (10-year Treasury
    yield, percent), BAMLH0A0HYM2 (ICE BofA US high-yield OAS, percent).
A manifest records the URL, download time (UTC), file size and SHA-256 hash of
every file, so the data can be traced and checked later.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

START = "2015-01-01"
MLP_TICKERS = ("DMLP ARLP WES UAN ET HESM MPLX SPH EPD CQP DKL GEL MMLP PAA "
               "USAC CAPL GLP SUN WLKP BSM MNR TXO NRP").split()
EXTRA_TICKERS = ["SPY", "HYG"]
FRED_SERIES = ["DCOILWTICO", "DGS10", "BAMLH0A0HYM2"]
HEADERS = {"User-Agent": "Mozilla/5.0 (academic portfolio risk research)"}

OUT = Path(__file__).resolve().parent / "pf2_raw_data"


def fetch(url: str) -> bytes:
    last_error = None
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=60) as response:
                return response.read()
        except Exception as exc:  # network errors, HTTP 429, etc.
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_error}")


def epoch(day: str) -> int:
    return int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp())


def yahoo(ticker: str) -> dict:
    end = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    params = urlencode({"period1": epoch(START), "period2": epoch(end),
                        "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{params}"
    data = fetch(url)
    obj = json.loads(data)
    result = (obj.get("chart") or {}).get("result")
    if not result:
        raise RuntimeError(f"{ticker}: empty Yahoo response {str(obj)[:200]}")
    n = len(result[0].get("timestamp") or [])
    return {"name": f"{ticker}.json", "url": url, "bytes": data, "rows": n}


def fred(series: str) -> dict:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={START}"
    data = fetch(url)
    text = data.decode("utf-8", "replace")
    if "," not in text.splitlines()[0]:
        raise RuntimeError(f"{series}: unexpected FRED response {text[:200]}")
    return {"name": f"{series}.csv", "url": url, "bytes": data,
            "rows": max(0, len(text.strip().splitlines()) - 1)}


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    manifest, failures = [], []
    jobs = [(yahoo, t) for t in MLP_TICKERS + EXTRA_TICKERS] + [(fred, s) for s in FRED_SERIES]
    for func, key in jobs:
        try:
            item = func(key)
            (OUT / item["name"]).write_bytes(item["bytes"])
            manifest.append({"file": item["name"], "url": item["url"], "rows": item["rows"],
                             "size_bytes": len(item["bytes"]),
                             "sha256": hashlib.sha256(item["bytes"]).hexdigest(),
                             "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                             "status": "ok"})
            print(f"ok      {item['name']:<22} {item['rows']:>6} rows")
        except Exception as exc:
            failures.append(key)
            manifest.append({"file": key, "status": "failed", "error": str(exc)[:300]})
            print(f"FAILED  {key:<22} {exc}")
        time.sleep(0.5)  # be polite to the providers
    (OUT / "manifest.json").write_text(json.dumps({
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": sys.version.split()[0], "start": START, "files": manifest}, indent=2), encoding="utf-8")
    archive = shutil.make_archive(str(OUT), "zip", root_dir=OUT)
    print(f"\nSaved {len(manifest) - len(failures)} files to {OUT}")
    print(f"Attach this file in the chat: {archive}")
    if failures:
        print("Some downloads failed; run the script again later:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
