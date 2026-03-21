# Naver Review Insight

> 광고 없는 진짜 리뷰를 찾아드립니다 — Selenium 기반 네이버 맛집 리뷰 신뢰도 분석 플랫폼

---

## 프로젝트 개요

수많은 광고성 리뷰 속에서 **진짜 방문자 리뷰만** 걸러내어, AI 기반 신뢰도 점수로 수치화하고 시각화해서 보여주는 플랫폼입니다.

### 핵심 가정
- 취미로 리뷰를 적는 사람과 악의적으로 부정 리뷰를 남기는 사람은 분석 대상에서 제외
- 광고·체험단 글은 음식점명 언급 시 맞춤법·띄어쓰기 오류가 거의 없다고 가정
- LightGBM 모델의 `predict_proba`를 기반으로 광고 확률을 산출, `is_ad=0`이 찐리뷰

### 주요 기능
- **실시간 수집** — Selenium으로 네이버 지도 리뷰 동적 크롤링
- **광고 필터링** — LightGBM 모델 기반 광고 리뷰 자동 분류 (`is_ad` 컬럼)
- **신뢰도 수치화** — `predict_proba` 기반 0~100점 신뢰 점수 산출 및 별점 변환
- **지역 검색** — 서울 25개구 기반 맛집 검색 지원
- **직관적 시각화** — 음식점 카드, 찐리뷰 토글 필터, 관리자 데이터 현황 대시보드

---

## 현재 개발 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| Crawling | Selenium 기반 실시간 크롤러 | ✅ 완료 |
| Scoring | LightGBM `predict_proba` 기반 신뢰도 로직 | ✅ 완료 |
| DB | Supabase `table1` / `table2` 구성 | ✅ 완료 |
| UI | Streamlit 멀티페이지 (메인·상세·관리자) | 🔄 진행중 |
| NLP Pipeline | ET5 맞춤법 교정 + KoElectra 감성 분석 | ✅ 완료 |

---

## 디렉토리 구조

```
naver_real_review/
├── app.py                      # 앱 엔트리 포인트 및 페이지 라우팅
├── final_sync_processor.py     # 피처 생성 + LightGBM 예측 후 Table1 → Table2 이동
├── lgbm_final.pkl              # 학습된 LightGBM 모델
├── .env                        # Supabase 환경변수 (비공개)
├── requirements.txt
└── review/
    ├── __init__.py
    ├── crawler.py              # Selenium 실시간 크롤러
    ├── final_pipeline.py       # ReviewAnalyzer 클래스 (전체 파이프라인)
    ├── nlp_processor.py        # ET5 교정 + KoElectra 감성 분석
    ├── scoring.py              # 신뢰도 점수 산출 및 별점 변환
    ├── sync_and_clean.py       # 분석 완료 후 Table1 정리
    ├── ui_components.py        # 커스텀 CSS 및 카드 렌더링
    └── visualizer.py           # 워드클라우드 & 차트 출력
```

---

## 실행 방법

### 1. 환경 설정

```bash
pip install streamlit pandas selenium webdriver-manager matplotlib wordcloud \
            supabase python-dotenv lightgbm joblib emoji tqdm
```

> Chrome 브라우저 및 ChromeDriver 환경이 선행되어야 합니다.

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

### 3. 앱 실행

```bash
streamlit run app.py
```

### 4. Streamlit Cloud 배포

1. GitHub에 레포지토리 푸시
2. [Streamlit Cloud](https://streamlit.io/cloud) 접속 후 레포 연결
3. **Settings > Secrets**에 환경변수 등록

```toml
SUPABASE_URL = "your_supabase_url"
SUPABASE_KEY = "your_supabase_anon_key"
```

4. `requirements.txt` 확인 후 Deploy

---

## 파일별 역할

### `app.py`
- 전체 앱 흐름 및 페이지 라우팅 (Main ↔ Detail ↔ Admin)
- Supabase `table2`에서 페이지네이션으로 전체 데이터 로드 (1000건 제한 우회)
- 메인 페이지: 음식점 카드 10개씩 더보기, 점수 높은순/낮은순 정렬, 지역·음식점명 검색
- 상세 페이지: 전체 리뷰 표시 + 찐리뷰만 토글 필터 + 신뢰 점수 뱃지
- 관리자 페이지: 크롤링 제어(좌) + 데이터 현황 대시보드(우) 2컬럼 레이아웃

### `crawler.py`
- `run_manual_crawler(region, place_limit, review_limit)` — 관리자 페이지에서 호출하는 메인 수집 함수
- `crawl_naver_reviews_bulk()` — 특정 장소 URL에서 리뷰 최대 N건 수집 후 `table1`에 적재
- 최신순 정렬 클릭, 더보기 버튼 반복 클릭, 방문일·방문횟수·태그 파싱 포함

### `final_sync_processor.py`
- `start_sync()` — `table1` 전체 데이터를 불러와 피처 생성 → LightGBM 예측 → `table2` 저장 → `table1` 삭제
- `build_features()` — review_len, place_name_cnt, emoji_cnt 등 11개 피처 자동 생성
- `lgbm_final.pkl` 모델 로드 후 `predict_proba` 산출, `is_ad` 컬럼 결정 (threshold: 0.21)
- `내돈내산` 키워드 시 `is_ad=0` 강제 적용, 협찬 명시 시 `is_ad=1` 강제 적용

### `scoring.py`
- `calculate_trust_score(predict_proba)` — `100 - (predict_proba * 100)`으로 신뢰 점수 산출
- `get_star_rating(avg_score)` — 90점↑ ⭐×5 / 70점↑ ⭐×4 / 50점↑ ⭐×3 / 30점↑ ⭐×2 / 10점↑ ⭐×1
- `get_restaurant_summary(df)` — 음식점별 평균 신뢰도 집계 및 정렬

### `ui_components.py`
- `apply_custom_style()` — 앱 전체 커스텀 CSS 적용
- `render_restaurant_card()` — 음식점 카드 HTML 렌더링 (툴팁·별점·해시태그 포함)

### `nlp_processor.py`
- ET5(`j5ng/et5-typos-corrector`)로 맞춤법 교정
- KoElectra(`Copycats/koelectra-base-v3-generalized-sentiment-analysis`)로 긍/부정 판별
- 고유명사 보호 로직(`protect_nouns_logic`) 포함

### `visualizer.py`
- 리뷰 텍스트 기반 워드클라우드 생성
- 한글 폰트 파일 경로 지정 필요

---

## Supabase 테이블 구조

| 테이블 | 역할 |
|---|---|
| `table1` | 크롤러가 수집한 원본 데이터 임시 적재 |
| `table2` | LightGBM 분석·피처 엔지니어링 완료된 최종 데이터 |

`final_sync_processor.py`의 `start_sync()` 실행 시 `table1` → 분석 → `table2` 저장 후 `table1` 자동 삭제.

### table2 주요 컬럼

| 컬럼 | 설명 |
|---|---|
| `place_name` | 음식점명 |
| `region_name` | 수집 지역 (예: 강남구) |
| `review_text` | 리뷰 본문 |
| `is_ad` | 광고 여부 (`0` = 찐리뷰, `1` = 광고의심) |
| `predict_proba` | LightGBM 광고 확률 (0.0 ~ 1.0) |
| `visit_date` | 방문일 |
| `user_nickname` | 작성자 닉네임 |

---

## 신뢰도 점수 산출 방식

```
predict_proba (LightGBM 광고 확률)
  │
  ▼
신뢰 점수 = 100 - (predict_proba × 100)
  │
  ▼
음식점 신뢰도 = 해당 음식점 전체 리뷰 신뢰 점수 평균
  │
  ▼
별점 변환 (90↑ ★5 / 70↑ ★4 / 50↑ ★3 / 30↑ ★2 / 10↑ ★1)
```

---

## 검색 기능

- **지역 검색**: `"강남구 맛집"`, `"마포구"` 등 서울 25개구 이름 인식 → `region_name` 기준 필터
- **음식점 검색**: 구 이름 없으면 `place_name` 기준 검색
- **복합 검색**: `"강남구 스시"` → 강남구 내 스시 관련 음식점 필터

---

## 향후 계획

- [ ] 비지도 학습(GMM 군집화)을 활용한 광고 리뷰 자동 분류 고도화
- [ ] 워드클라우드 및 통계 차트 상세 페이지 연동
- [ ] DB 연동을 통한 상권 변화 추이 추적
- [ ] 테스트 데이터셋 구축 및 모델 성능 평가 체계 마련
- [ ] 분석 관련한 그래프 넣기
