# K-Panic Monitor (KOSPI · KOSDAQ)

과매수/과매도 오실레이터(±80% 기준) + 90% Day + MDD 추이 대시보드

## 구성
| 파일 | 역할 |
|---|---|
| `app.py` | Streamlit 대시보드 |
| `update_data.py` | 매 거래일 자동 수집 (GitHub Actions) |
| `backfill_data.py` | 과거 데이터 소급 수집 (집/회사 PC에서 1회 실행) |
| `data/history.csv` | 누적 데이터 (5/21~6/11 KOSPI 시드 포함) |
| `.github/workflows/daily_update.yml` | 평일 16:40 KST 자동 실행 |

## 배포 (5분)
1. GitHub 새 레포 생성 (Public) → 파일 전체 업로드
   - `.github/workflows/daily_update.yml` 경로 유지 (업로드 시 파일명 칸에 경로째 입력)
2. Settings → Actions → General → Workflow permissions → **Read and write** 선택
3. Actions 탭 → Daily Market Data Update → **Run workflow** 1회 수동 실행
4. share.streamlit.io → New app → Main file: `app.py` → Deploy

## 과거 추이 채우기 (선택)
KOSDAQ 과거치 등을 채우려면 **국내 IP PC에서**:
```
pip install pykrx pandas finance-datareader
python backfill_data.py 20260101
```
생성된 `data/history.csv`를 레포에 업로드 (기존 파일 덮어쓰기)

## 판정 기준
- 오실레이터 = 상승종목 거래대금 비중(우세 시 +) / 하락종목 비중(우세 시 -)
- **+80% 이상 = 과매수 / -80% 이하 = 과매도**
- ±90% = Panic Buying / Panic Selling (Lowry 90% Day)
- 추세 반전 확정: -90% Day(투매) → +90% Day(매수 쇄도) 순서 확인
