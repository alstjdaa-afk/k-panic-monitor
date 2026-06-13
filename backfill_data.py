"""
과거 데이터 백필 스크립트 — 집/회사 PC(국내 IP)에서 1회 실행
pykrx로 과거 거래일별 전종목 데이터를 받아 data/history.csv를 소급 생성

사용법:
  pip install pykrx pandas finance-datareader
  python backfill_data.py 20260101          # 2026-01-01부터 오늘까지
  python backfill_data.py 20251201 20260610 # 기간 지정

완료 후 생성된 data/history.csv를 GitHub 레포의 data/ 폴더에 업로드하면
대시보드에 과거 추이가 바로 표시됩니다. (이후는 GitHub Actions가 자동 누적)
"""
import os
import sys
import time
import pandas as pd
from pykrx import stock
import FinanceDataReader as fdr

DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, "history.csv")

MARKETS = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}


def oscillator(up_pct):
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


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "20260101"
    end = sys.argv[2] if len(sys.argv) > 2 else pd.Timestamp.today().strftime("%Y%m%d")

    os.makedirs(DATA_DIR, exist_ok=True)

    # 지수 데이터 (날짜 기준 + 종가 + Drawdown 계산용)
    idx_data = {}
    for market, code in MARKETS.items():
        ks = fdr.DataReader(code, "2020-01-01")
        ks["Peak"] = ks["Close"].cummax()
        ks["DD"] = (ks["Close"] / ks["Peak"] - 1) * 100
        idx_data[market] = ks

    trading_days = idx_data["KOSPI"].loc[
        (idx_data["KOSPI"].index >= pd.to_datetime(start))
        & (idx_data["KOSPI"].index <= pd.to_datetime(end))
    ].index

    rows = []
    for i, d in enumerate(trading_days, 1):
        dstr = d.strftime("%Y%m%d")
        for market, code in MARKETS.items():
            try:
                df = stock.get_market_ohlcv_by_ticker(dstr, market=market)
                df = df[df["거래량"] > 0]
                up = df[df["등락률"] > 0]
                dn = df[df["등락률"] < 0]

                up_vol, dn_vol = int(up["거래량"].sum()), int(dn["거래량"].sum())
                up_amt, dn_amt = int(up["거래대금"].sum()), int(dn["거래대금"].sum())

                chg = df["종가"] * df["등락률"] / (100 + df["등락률"]) * 100 / 100
                # 등락폭(원) 근사: 종가와 등락률로 역산
                pts = df["종가"] - df["종가"] / (1 + df["등락률"] / 100)
                pts_g = float(pts[pts > 0].sum())
                pts_l = float(-pts[pts < 0].sum())

                up_pct_amt = round(up_amt / (up_amt + dn_amt) * 100, 2)
                up_pct_vol = round(up_vol / (up_vol + dn_vol) * 100, 2)
                pts_up = round(pts_g / (pts_g + pts_l) * 100, 2) if (pts_g + pts_l) > 0 else 50.0
                osc = oscillator(up_pct_amt)

                ks = idx_data[market]
                idx_close = round(float(ks.loc[d, "Close"]), 2)
                dd = round(float(ks.loc[d, "DD"]), 2)

                rows.append({
                    "date": d.strftime("%Y-%m-%d"), "market": market,
                    "index_close": idx_close, "drawdown_pct": dd,
                    "oscillator": osc, "up_pct_amt": up_pct_amt,
                    "up_pct_vol": up_pct_vol, "points_up_pct": pts_up,
                    "up_vol": up_vol, "down_vol": dn_vol,
                    "up_amt": up_amt, "down_amt": dn_amt,
                    "advancers": len(up), "decliners": len(dn),
                    "signal": judge(osc),
                })
            except Exception as e:
                print(f"  ! {dstr} {market} 실패: {e}")
            time.sleep(0.7)  # KRX 부하 방지 (차단 예방)

        print(f"[{i}/{len(trading_days)}] {dstr} 완료")

    new = pd.DataFrame(rows)
    if os.path.exists(CSV_PATH):
        hist = pd.read_csv(CSV_PATH)
        keys = set(zip(new["date"], new["market"]))
        hist = hist[~hist.apply(lambda r: (r["date"], r["market"]) in keys, axis=1)]
        new = pd.concat([hist, new], ignore_index=True)

    new = new.sort_values(["date", "market"]).reset_index(drop=True)
    new.to_csv(CSV_PATH, index=False)
    print(f"\n✅ 총 {len(new)}행 저장 → {CSV_PATH}")
    print("이 파일을 GitHub 레포의 data/ 폴더에 업로드하세요.")


if __name__ == "__main__":
    main()
