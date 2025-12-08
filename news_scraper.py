# ===================================================================
# 1. 라이브러리 설치 및 Import
# ===================================================================
# !pip install requests beautifulsoup4 pandas urllib3 newspaper3k
# !pip install playwright
# !playwright install
import nest_asyncio
nest_asyncio.apply()
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import random
# (삭제) from transformers import pipeline
import logging
from newspaper import Article # 1순위 스크레이퍼
from playwright.sync_api import sync_playwright # 2순위 스크레이퍼

# ===================================================================
# 2. SSL/TLS 경고 메시지 및 불필요한 로그 비활성화
# ===================================================================
urllib3.disable_warnings(InsecureRequestWarning)
logging.getLogger("newspaper").setLevel(logging.ERROR)

# ===================================================================
# 3. API 설정 및 User-Agent
# ===================================================================
client_id = "joP0cBV9ZbhnxyJ1L8F7"
client_secret = "luDJekwory"
query = "데이터 분석"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
]

# (삭제) --- Hugging Face 요약 모델 로드 ---

# ===================================================================
# 4. 유틸리티 함수 (스크레이핑 로직 - 이전과 동일)
# ===================================================================
def clean_text(text):
    text = re.sub(r"\s+", " ", text); text = re.sub(r"\[[^\]]*\]", "", text)
    return text.strip()

def fetch_with_playwright(url, headers):
    html = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=headers['User-Agent'])
            page.goto(url, timeout=10000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(1000, 2000))
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"    -> [Warn] Playwright 실행 실패: {e}")
    return html

def get_article_content_and_reporter(naver_link, original_link):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    content, reporter = "", "기자명 없음"

    # 1. 네이버 뷰어
    if "n.news.naver.com" in naver_link:
        try:
            res = requests.get(naver_link, headers=headers, verify=False, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                elem = soup.select_one("article#dic_area") or soup.select_one("#newsct_article")
                if elem: content = elem.get_text(" ", strip=True)
                rep_elem = soup.select_one(".byline_s") or soup.select_one(".media_end_head_journalist_name")
                if rep_elem: reporter = rep_elem.get_text(strip=True)
                if content: return clean_text(content), reporter or "기자명 없음"
        except Exception as e:
            # print(f"  -> [Warn] 1순위(Naver) 실패 ({e}), 2순위로 전환...") # 로그 너무 많아짐
            pass

    # 2. newspaper3k
    try:
        # print(f"  -> [Info] 2순위(newspaper3k) 스크레이핑 시도...")
        article = Article(original_link, language='ko')
        article.headers = headers; article.download(); article.parse()
        content = article.text; authors = article.authors
        if authors:
            cleaned_authors = [a for a in authors if not a.startswith("Var ") and "Byline" not in a and "Molongui" not in a]
            reporter = ', '.join(cleaned_authors) if cleaned_authors else "기자명 없음"
        if content and len(content) > 150:
            if not reporter or reporter == "기자명 없음":
                match = re.search(r"([가-힣]{2,5})\s?(기자|특파원|논설위원)", content)
                if match: reporter = match.group(0).strip()
            return content, reporter
        else:
            # print(f"  -> [Warn] 2순위(newspaper3k) 본문 못 찾음, 3순위로 전환...")
            pass
    except Exception as e:
        # print(f"  -> [Warn] 2순위(newspaper3k) 실패 ({e}), 3순위로 전환...")
        pass

    # 3. Playwright
    try:
        # print(f"  -> [Info] 3순위(Playwright) 스크레이핑 시도...")
        html = fetch_with_playwright(original_link, headers)
        if not html: return "본문 없음 (Playwright 실패)", "기자명 없음"
        article = Article(original_link, language='ko'); article.download(input_html=html); article.parse()
        content = article.text; authors = article.authors
        if authors:
            cleaned_authors = [a for a in authors if not a.startswith("Var ") and "Byline" not in a and "Molongui" not in a]
            reporter = ', '.join(cleaned_authors) if cleaned_authors else "기자명 없음"
        if content and (not reporter or reporter == "기자명 없음"):
            match = re.search(r"([가-힣]{2,5})\s?(기자|특파원|논설위원)", content)
            if match: reporter = match.group(0).strip()
        return content or "본문 없음", reporter
    except Exception as e:
        print(f"  -> [Warn] 3순위(Playwright) 최종 실패: {e}")
        return f"에러: {e}", "기자명 없음"

# ===================================================================
# 5. (삭제됨) 동적 요약 함수
# ===================================================================

# ===================================================================
# 6. 메인 로직 (1000개 성공 목표로 수정됨)
# ===================================================================
url = "https://openapi.naver.com/v1/search/news.json"
naver_api_headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
results_for_csv = [] # 최종 CSV에 저장될 '성공한' 데이터만 담을 리스트
TARGET_COUNT = 1000 # 목표 성공 개수
current_api_start = 1 # API 호출 시작 인덱스
successful_scrapes_count = 0 # 성공 카운터
processed_api_items_count = 0 # API에서 가져온 총 아이템 수 (중복 방지용)

print(f"--- 네이버 뉴스 API 수집 및 스크레이핑 시작 (목표: {TARGET_COUNT}개 성공) ---")

# (수정됨) 성공 카운터가 목표에 도달하거나, API가 더 이상 결과를 주지 않을 때까지 반복
while successful_scrapes_count < TARGET_COUNT and current_api_start <= 901: # API는 최대 1000개까지만 (start=901이 마지막)
    params = {
        "query": query,
        "display": 100, # 한 번에 100개씩
        "start": current_api_start,
        "sort": "date"
    }

    print(f"\n--- API 호출 (start={current_api_start}) ---")
    response = requests.get(url, headers=naver_api_headers, params=params)

    if response.status_code == 200:
        items = response.json().get("items", [])
        if not items:
            print("  -> API 결과 없음. 수집 종료.")
            break # 더 이상 가져올 기사가 없으면 루프 종료

        print(f"  -> API에서 {len(items)}개 아이템 수신.")
        processed_api_items_count += len(items)

        # 받아온 100개의 아이템을 하나씩 처리
        for item in items:
            title = BeautifulSoup(item["title"], "html.parser").get_text()
            naver_link = item.get("link")
            original_link = item.get("originallink", naver_link)
            date = item.get("pubDate", "")

            # 1. 스크레이핑 시도
            content, reporter = get_article_content_and_reporter(naver_link, original_link)

            # 2. 스크레이핑 결과 필터링
            is_valid_content = True
            FILTER_WORDS = ["저작권", "발행인", "등록번호", "Copyright", "무단전재", "재배포 금지", "청소년보호책임자"]
            MIN_CONTENT_LENGTH = 250
            if not content or content.startswith(("본문 없음", "에러:")):
                is_valid_content = False
            elif len(content) < MIN_CONTENT_LENGTH:
                is_valid_content = False
            elif any(word in content for word in FILTER_WORDS):
                is_valid_content = False

            # 3. 스크레이핑 성공 시에만 CSV 리스트에 추가하고 카운터 증가
            if is_valid_content:
                successful_scrapes_count += 1
                record = {"번호": successful_scrapes_count, "제목": title, "link": original_link, "기자": reporter, "날짜": date, "내용요약": content}
                results_for_csv.append(record)
                # 진행 상황 표시 (매 10개 성공 시)
                if successful_scrapes_count % 10 == 0:
                     print(f"\r  -> 성공 {successful_scrapes_count}/{TARGET_COUNT} 달성 (API 항목 {processed_api_items_count}개 처리)", end="")

                # 목표 개수 달성 시 즉시 모든 루프 종료
                if successful_scrapes_count >= TARGET_COUNT:
                    print("\n--- 목표 개수 달성! ---")
                    break # 내부 for 루프 종료
            else:
                # 실패 시 로그 (너무 많으면 주석 처리)
                # print(f"  -> 스크레이핑 실패: {title[:20]}...")
                pass

            time.sleep(0.05) # 개별 기사 처리 딜레이

        # (수정) 목표 개수 달성 시 외부 while 루프도 종료해야 함
        if successful_scrapes_count >= TARGET_COUNT:
            break

        # 다음 API 호출을 위해 start 인덱스 증가
        current_api_start += 100
        time.sleep(0.5) # API 호출 간격

    elif response.status_code == 429:
        print(f"  -> [Error] API 호출 제한(429). 10초 후 재시도...")
        time.sleep(10) # API 제한 시 더 길게 대기
    else:
        print(f"  -> [Error] API 호출 실패: {response.status_code}. 수집 종료.")
        break # 심각한 에러 시 루프 종료

# --- 루프 종료 후 ---
print("\n\n--- 모든 작업 완료 ---")
df = pd.DataFrame(results_for_csv)

if not df.empty:
    # 번호 컬럼은 이미 successful_scrapes_count로 생성됨
    file_name = f"naver_news_{successful_scrapes_count}_scraped.csv" # 파일 이름에 실제 성공 개수 포함
    df.to_csv(file_name, index=False, encoding="utf-8-sig")
    print(f"✅ CSV 파일 저장 완료 (총 {len(df)}개 기사): {file_name}")
    if successful_scrapes_count < TARGET_COUNT:
        print(f"⚠️ 목표({TARGET_COUNT}개)보다 적은 {successful_scrapes_count}개의 기사만 수집되었습니다. (API 제한 또는 스크레이핑 실패율 때문)")
else:
    print("⚠️ 처리 결과: 성공적으로 스크레이핑된 기사가 없습니다.")