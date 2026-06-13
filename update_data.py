"""
KOSPI / KOSDAQ 과매수·과매도 (Upside/Downside Volume) 일일 수집 스크립트 v2
GitHub Actions가 매 거래일 장마감 후 실행하여 data/history.csv에 누적 기록

오실레이터 정의 (엑셀 시트와 동일한 방식):
  - 상승종목 거래대금 비중(Up%)이 50% 이상이면  +Up%
  - 하락종목 거래대금 비중(Down%)이 50% 초과면  -Down%
  - +80% 이상 = 과매수,  -80% 이하 = 과매도(Panic Selling 구간)
"""
import os
import time
import pandas as pd
import FinanceDataReader as fdr

DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "history.csv")

MARKETS = [
    ("KOSPI", "KS11"),
    ("KOSDAQ", "KQ11"),
]


def retry(fn, n=4, wait=15):
    """KRX 일시 차단(503 등) 대비 재시도"""
    last = None
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"  재시도 {i + 1}/{n} ... ({type(e).__name__})")
            time.sleep(wait)
    raise last


def oscillator(up_pct):
    """부호 있는 오실레이터: 우세한 쪽 비중에 +/- 부호"""
    return round(up_pct, 2) if up_pct >= 50 else round(-(100 - up_pct), 2)


def judge(osc):
    if osc >= 90:
        return "PANIC BUYING (90% Up Day)"
    if osc >= 80:
        return "과매수 (+80% 이상)"
    if osc <= -90:
        return "PANIC SELLING (90% Down Day)"
    if osc <= -80:
        return "과매도 (-80% 이하)"
    return "중립"


def collect_market(market, index_code):
    df = retry(lambda: fdr.StockListing(market))
    df = df[df["Volume"] > 0].copy()

    up = df[df["Changes"] > 0]
    dn = df[df["Changes"] < 0]

    up_vol, dn_vol = int(up["Volume"].sum()), int(dn["Volume"].sum())
    up_amt, dn_amt = int(up["Amount"].sum()), int(dn["Amount"].sum())
    pts_g = float(up["Changes"].sum())
    pts_l = float(-dn["Changes"].sum())

    ks = retry(lambda: fdr.DataReader(index_code, "2020-01-01"))
    trade_date = ks.index[-1].strftime("%Y-%m-%d")
    idx_close = round(float(ks["Close"].iloc[-1]), 2)
    peak = float(ks["Close"].cummax().iloc[-1])
    dd = round((idx_close / peak - 1) * 100, 2)

    up_pct_vol = round(up_vol / (up_vol + dn_vol) * 100, 2)
    up_pct_amt = round(up_amt / (up_amt + dn_amt) * 100, 2)
    pts_up_pct = round(pts_g / (pts_g + pts_l) * 100, 2) if (pts_g + pts_l) > 0 else 50.0

    osc = oscillator(up_pct_amt)

    return {
        "date": trade_date,
        "market": market,
        "index_close": idx_close,
        "drawdown_pct": dd,
        "oscillator": osc,
        "up_pct_amt": up_pct_amt,
        "up_pct_vol": up_pct_vol,
        "points_up_pct": pts_up_pct,
        "up_vol": up_vol,
        "down_vol": dn_vol,
        "up_amt": up_amt,
        "down_amt": dn_amt,
        "advancers": len(up),
        "decliners": len(dn),
        "signal": judge(osc),
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = []
    for market, idx in MARKETS:
        print(f"[{market}] 수집 중 ...")
        rows.append(collect_market(market, idx))
        time.sleep(3)  # KRX 부하 방지

    new = pd.DataFrame(rows)

    if os.path.exists(CSV_PATH):
        hist = pd.read_csv(CSV_PATH)
        # 같은 (날짜, 시장) 중복 제거 — 주말/휴일 실행 시 마지막 거래일이 다시 잡힘
        keys = set(zip(new["date"], new["market"]))
        hist = hist[~hist.apply(lambda r: (r["date"], r["market"]) in keys, axis=1)]
        hist = pd.concat([hist, new], ignore_index=True)
    else:
        hist = new

    hist = hist.sort_values(["date", "market"]).reset_index(drop=True)
    hist.to_csv(CSV_PATH, index=False)

    for r in rows:
        print(f"[OK] {r['date']} {r['market']:6s} | 지수 {r['index_close']:,} | "
              f"OSC {r['oscillator']:+.2f}% | DD {r['drawdown_pct']}% | {r['signal']}")


if __name__ == "__main__":
    main()
