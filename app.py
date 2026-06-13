"""
KOSPI / KOSDAQ Panic Monitor v2
- 과매수·과매도 오실레이터 (±80% 기준 판정, 90% Day 추적)
- 오실레이터 추이 차트 + MDD(Drawdown) 추이 차트
"""
import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import FinanceDataReader as fdr

st.set_page_config(page_title="K-Panic Monitor", page_icon="📉", layout="wide")

CSV_PATH = os.path.join("data", "history.csv")
MARKETS = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}
COLORS = {"KOSPI": "royalblue", "KOSDAQ": "darkorange"}


# ---------------------------------------------------------------- 유틸
def oscillator(up_pct):
    return up_pct if up_pct >= 50 else -(100 - up_pct)


def judge(osc):
    if osc >= 90:
        return "🟢 PANIC BUYING — 90% Up Day", "green"
    if osc >= 80:
        return "🟢 과매수 (+80% 이상)", "green"
    if osc <= -90:
        return "🔴 PANIC SELLING — 90% Down Day", "red"
    if osc <= -80:
        return "🔴 과매도 (-80% 이하)", "red"
    return "⚪ 중립", "gray"


@st.cache_data(ttl=600)
def load_snapshot(market):
    df = fdr.StockListing(market)
    return df[df["Volume"] > 0].copy()


@st.cache_data(ttl=600)
def load_index(code, start="2020-01-01"):
    return fdr.DataReader(code, start)


def compute_updown(df):
    up = df[df["Changes"] > 0]
    dn = df[df["Changes"] < 0]
    up_amt, dn_amt = up["Amount"].sum(), dn["Amount"].sum()
    up_vol, dn_vol = up["Volume"].sum(), dn["Volume"].sum()
    up_pct_amt = up_amt / (up_amt + dn_amt) * 100
    return {
        "up_pct_amt": up_pct_amt,
        "up_pct_vol": up_vol / (up_vol + dn_vol) * 100,
        "oscillator": oscillator(up_pct_amt),
        "advancers": len(up),
        "decliners": len(dn),
    }


def load_history():
    if os.path.exists(CSV_PATH):
        h = pd.read_csv(CSV_PATH)
        h["date"] = pd.to_datetime(h["date"])
        return h
    return None


# ---------------------------------------------------------------- 헤더
st.title("📉 K-Panic Monitor")
st.caption("KOSPI · KOSDAQ | 과매수·과매도 오실레이터(±80%) + 90% Day + MDD 추적 | 데이터: KRX")

hist = load_history()

# ---------------------------------------------------------------- ① 오늘의 판정 (양 시장)
st.header("① 오늘의 과매수 / 과매도")

cols = st.columns(2)
live_ok = {}
for col, (market, code) in zip(cols, MARKETS.items()):
    with col:
        try:
            snap = load_snapshot(market)
            t = compute_updown(snap)
            ks = load_index(code, "2025-01-01")
            trade_date = ks.index[-1].strftime("%Y-%m-%d")
            idx_now = float(ks["Close"].iloc[-1])
            idx_chg = (idx_now / float(ks["Close"].iloc[-2]) - 1) * 100
            live_ok[market] = True
        except Exception:
            live_ok[market] = False
            # KRX 일시 차단 시 누적 CSV의 마지막 데이터로 폴백
            if hist is not None and (hist["market"] == market).any():
                last = hist[hist["market"] == market].iloc[-1]
                t = {"oscillator": last["oscillator"],
                     "up_pct_amt": last["up_pct_amt"],
                     "up_pct_vol": last["up_pct_vol"],
                     "advancers": int(last["advancers"]),
                     "decliners": int(last["decliners"])}
                trade_date = last["date"].strftime("%Y-%m-%d")
                idx_now, idx_chg = last["index_close"], 0.0
                st.warning("실시간 조회 실패 — 마지막 저장 데이터 표시 중")
            else:
                st.error(f"{market} 데이터 조회 실패")
                continue

        verdict, vcolor = judge(t["oscillator"])
        st.subheader(f"{market}  ({trade_date})")
        st.markdown(f"### {verdict}")

        m1, m2, m3 = st.columns(3)
        m1.metric("지수", f"{idx_now:,.2f}", f"{idx_chg:+.2f}%")
        m2.metric("오실레이터", f"{t['oscillator']:+.2f}%")
        m3.metric("상승/하락", f"{t['advancers']} / {t['decliners']}")

        # 미니 게이지 (-100 ~ +100)
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number",
            value=t["oscillator"],
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": COLORS[market]},
                "steps": [
                    {"range": [-100, -90], "color": "#d62728"},
                    {"range": [-90, -80], "color": "#ff9896"},
                    {"range": [-80, 80], "color": "#ececec"},
                    {"range": [80, 90], "color": "#98df8a"},
                    {"range": [90, 100], "color": "#2ca02c"},
                ],
                "threshold": {"line": {"color": "black", "width": 2},
                              "value": t["oscillator"]},
            },
        ))
        fig_g.update_layout(height=220, margin=dict(t=20, b=10, l=30, r=30))
        st.plotly_chart(fig_g, use_container_width=True)

st.info("**판정 기준** — 오실레이터 **+80% 이상 = 과매수**, **-80% 이하 = 과매도**(Panic Selling 구간). "
        "정통 Lowry 룰의 추세 반전은 **-90% 데이(투매) 출현 후 +90% 데이(매수 쇄도)** 확인. "
        "-80% 이하가 짧은 기간 반복되면 매도 에너지 소진 → 바닥 근접 신호.")

# ---------------------------------------------------------------- 시장 선택 (추이 차트용)
st.divider()
sel = st.radio("추이 차트 시장 선택", list(MARKETS.keys()), horizontal=True)

# ---------------------------------------------------------------- ② 과매수/과매도 추이
st.header(f"② {sel} 과매수 / 과매도 추이")

if hist is not None and (hist["market"] == sel).any():
    h = hist[hist["market"] == sel].sort_values("date")

    bar_colors = ["#d62728" if v <= -80 else "#2ca02c" if v >= 80 else "#9ecae1"
                  for v in h["oscillator"]]

    fig_o = make_subplots(specs=[[{"secondary_y": True}]])
    fig_o.add_trace(go.Bar(x=h["date"], y=h["oscillator"], name="오실레이터",
                           marker_color=bar_colors))
    fig_o.add_trace(go.Scatter(x=h["date"], y=h["index_close"], name=sel,
                               line=dict(color="black", width=1.5)), secondary_y=True)
    for y, c in [(80, "green"), (-80, "red"), (90, "darkgreen"), (-90, "darkred")]:
        fig_o.add_hline(y=y, line_dash="dot", line_color=c, opacity=0.7)
    fig_o.update_yaxes(title_text="오실레이터 (%)", range=[-100, 100], secondary_y=False)
    fig_o.update_yaxes(title_text=f"{sel} 지수", secondary_y=True)
    fig_o.update_layout(height=440, margin=dict(t=20, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig_o, use_container_width=True)

    # 극단일 카운트
    n80 = int((h["oscillator"] <= -80).sum())
    n90 = int((h["oscillator"] <= -90).sum())
    p80 = int((h["oscillator"] >= 80).sum())
    p90 = int((h["oscillator"] >= 90).sum())
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("과매도일 (-80% 이하)", f"{n80}일")
    s2.metric("Panic Selling (-90%)", f"{n90}일")
    s3.metric("과매수일 (+80% 이상)", f"{p80}일")
    s4.metric("Panic Buying (+90%)", f"{p90}일")
else:
    st.warning("아직 누적 데이터가 없습니다. backfill_data.py로 과거를 채우거나, "
               "GitHub Actions 첫 실행 후부터 추이가 쌓입니다.")

# ---------------------------------------------------------------- ③ MDD 추이
st.header("③ MDD (Drawdown) 추이")

period = st.radio("기간", ["6개월", "1년", "2년", "전체(2020~)"], horizontal=True, index=1)
days = {"6개월": 182, "1년": 365, "2년": 730, "전체(2020~)": 10000}[period]

fig_d = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.55, 0.45],
                      vertical_spacing=0.06,
                      subplot_titles=(f"{sel} 지수 & 전고점", "Drawdown 추이 (KOSPI vs KOSDAQ)"))

dd_metrics = {}
for market, code in MARKETS.items():
    try:
        ks = load_index(code)
    except Exception:
        continue
    kp = ks.loc[ks.index >= (ks.index[-1] - pd.Timedelta(days=days))].copy()
    kp["Peak"] = kp["Close"].cummax()
    kp["DD"] = (kp["Close"] / kp["Peak"] - 1) * 100
    dd_metrics[market] = {
        "cur": kp["DD"].iloc[-1],
        "mdd": kp["DD"].min(),
        "mdd_date": kp["DD"].idxmin().strftime("%Y-%m-%d"),
        "peak": kp["Peak"].iloc[-1],
        "recover": (kp["Peak"].iloc[-1] / kp["Close"].iloc[-1] - 1) * 100,
    }
    if market == sel:
        fig_d.add_trace(go.Scatter(x=kp.index, y=kp["Close"], name=sel,
                                   line=dict(color=COLORS[market], width=1.8)), row=1, col=1)
        fig_d.add_trace(go.Scatter(x=kp.index, y=kp["Peak"], name="전고점",
                                   line=dict(color="gray", width=1, dash="dot")), row=1, col=1)
    fig_d.add_trace(go.Scatter(x=kp.index, y=kp["DD"], name=f"{market} DD",
                               line=dict(color=COLORS[market], width=1.3)), row=2, col=1)

fig_d.add_hline(y=-10, line_dash="dash", line_color="orange", row=2, col=1,
                annotation_text="-10% 조정")
fig_d.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1,
                annotation_text="-20% 약세장")
fig_d.update_layout(height=640, margin=dict(t=40, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig_d, use_container_width=True)

if dd_metrics:
    mc = st.columns(len(dd_metrics) * 2)
    i = 0
    for market, m in dd_metrics.items():
        mc[i].metric(f"{market} 현재 DD", f"{m['cur']:.2f}%")
        mc[i + 1].metric(f"{market} MDD ({period})", f"{m['mdd']:.2f}%", m["mdd_date"])
        i += 2

# ---------------------------------------------------------------- ④ 히스토리 테이블
st.header("④ 히스토리")
if hist is not None:
    show = hist.sort_values(["date", "market"], ascending=[False, True]).copy()
    show["date"] = show["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        show[["date", "market", "index_close", "drawdown_pct", "oscillator",
              "up_pct_amt", "up_pct_vol", "points_up_pct",
              "advancers", "decliners", "signal"]],
        use_container_width=True, hide_index=True, height=400,
    )
else:
    st.caption("누적 데이터 없음")

st.caption("⚠️ 정보 제공 목적이며 투자 권유가 아닙니다. 장중 접속 시 미확정 데이터가 표시될 수 있습니다.")
