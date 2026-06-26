from func import *
from openai import OpenAI
from dotenv import load_dotenv
from upload import upload_image_url_to_gcs
import os
import re
import requests

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
PPLX_KEY = os.getenv("PPLX_KEY")

# 클라이언트 객체 생성 (여기에 API 키 입력)
client = OpenAI(
    api_key=PPLX_KEY,
    base_url="https://api.perplexity.ai" # 목적지를 OpenAI에서 퍼플렉시티로 변경!
)

# 네이버 검색 API 키 (https://developers.naver.com/apps 에서 발급)





def it_blog():
    # 실행 예시
    topic = "부천 휴대폰 성지 갤럭시s26 플러스 합리적으로 사는 방법?!"
    keyword = "갤럭시s26 플러스"
    article = generate_it_post(topic, keyword)
    image_urls = search_naver_image(keyword, display=30)
    final_html = build_blog_html(article, image_urls)
    print(final_html)
    pg.alert('최종 HTML 체크!!')


def build_blog_html(article: str, image_urls: list[str]) -> str:
    """article + 네이버 이미지 URL 리스트 → 업로드 가능한 최종 HTML.

    1) article 을 HTML 블록으로 변환
    2) 문단 수에 따라 image_urls 에서 랜덤 2~3개 선택 → GCS 업로드
    3) 블록 사이에 균등 간격으로 <img> 삽입
    """
    blocks = [b for b in clean_and_convert_to_html(article).split('\n') if b.strip()]
    n_blocks = len(blocks)
    if n_blocks == 0 or not image_urls:
        return '\n'.join(blocks)

    # 문단(블록) 수에 따라 2~3개 (블록 4개 미만이면 1개만)
    if n_blocks < 4:
        n_images = 1
    elif n_blocks < 8:
        n_images = 2
    else:
        n_images = 3
    n_images = min(n_images, len(image_urls))

    # 랜덤 추출 → GCS 업로드 (실패한 건 건너뜀)
    picks = random.sample(image_urls, n_images)
    ts = int(time.time())
    gcs_urls = []
    for i, src in enumerate(picks):
        gcs = upload_image_url_to_gcs(src, f"itblog_{ts}_{i}.jpg")
        if gcs:
            gcs_urls.append(gcs)
    if not gcs_urls:
        return '\n'.join(blocks)

    # 블록 사이 균등 위치 계산 (예: 블록 9개 / 이미지 2개 → step=3 → [3, 6])
    step = max(1, n_blocks // (len(gcs_urls) + 1))
    positions = [(i + 1) * step for i in range(len(gcs_urls))]

    # 뒤에서부터 삽입해야 앞쪽 인덱스가 깨지지 않음
    for pos, url in zip(reversed(positions), reversed(gcs_urls)):
        img_html = (f'<p style="text-align:center;">'
                    f'<img src="{url}" style="max-width:100%;height:auto;" /></p>')
        blocks.insert(pos, img_html)

    return '\n'.join(blocks)




def search_naver_image(query: str, display: int = 1, sort: str = "sim",
                       filter_size: str = "large") -> list[str]:
    """
    네이버 이미지 검색 API로 이미지 URL 리스트를 반환.

    Args:
        query: 검색어
        display: 가져올 이미지 개수 (1~100)
        sort: "sim"(정확도순) / "date"(날짜순)
        filter_size: "all" / "large" / "medium" / "small"

    Returns:
        이미지 URL 리스트 (썸네일 아닌 원본 link 기준)
    """
    url = "https://openapi.naver.com/v1/search/image"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": max(1, min(display, 30)),
        "sort": sort,
        "filter": filter_size,
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    return [it["link"] for it in items]


def naver_image_tag(query: str, alt: str | None = None,
                    width: str = "100%") -> str:
    """
    네이버에서 이미지 1장 검색해서 바로 붙일 수 있는 <img> 태그 문자열로 반환.
    검색 결과가 없으면 빈 문자열.
    """
    urls = search_naver_image(query, display=1)
    if not urls:
        return ""
    safe_alt = (alt or query).replace('"', '&quot;')
    return f'<img src="{urls[0]}" alt="{safe_alt}" style="width:{width};height:auto;" />'



def generate_it_post(topic, keyword):
    system_prompt = """
    너는 10년 차 IT 전문 블로거이자 휴대폰 성지의 내부자야.
    [절대 규칙]
    1. AI 특유의 기계적인 인사말(안녕하세요 등), 뻔한 미사여구 절대 금지.
    2. 모든 정보는 최신 실시간 검색 결과를 바탕으로 팩트(숫자, 가격, 정책) 위주로 작성할 것.
    3. 타사(경쟁사) 이름이나 특정 대리점 추천은 절대 하지 말고, 오직 '찍고' 플랫폼을 간접적으로 어필할 것.
    4. 특수문자는 (. , ? ' ")만 허용하며, [1], [2] 같은 검색 출처 인용구는 출력에서 완전히 제거할 것.
    """
    
    user_prompt = f"핵심 키워드 : {keyword} / 주제: {topic}\n라는 주제로 IT 정보성 글을 작성해주고, '찍고' 라는 사이트를 홍보하기 위함이므로 타 사이트 언급(폰사와,세모폰,성지나라 등 기타)은 다 빼주고 내 사이트에서 살 수 있다고 자연스레 해줘 바로 업로드 할 수 있는 블로그 글로 만들어줘"

    response = client.chat.completions.create(
        model="sonar", # 2. 퍼플렉시티의 빠르고 저렴한 최신 검색 모델
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    
    return response.choices[0].message.content




def _inline_format(text: str) -> str:
    """줄 안쪽의 인라인 마크다운 처리 (**, 남은 *, # 제거)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = text.replace('*', '')
    text = text.replace('#', '')
    return text.strip()


def clean_and_convert_to_html(article: str) -> str:
    """
    퍼플렉시티 결과물(article) 정리 후 HTML로 변환.

    처리 내용:
      - [1], [2][5] 같은 출처 표시 제거
      - --- (수평선) 제거
      - #, ## 헤딩 -> <h1>, <h2> ...
      - **bold** -> <strong>
      - 마크다운 표 -> <table>
      - - / * / 숫자. 리스트 -> <ul>, <ol>
      - > 인용 -> <blockquote>
      - 일반 문장 -> <p>
    """
    # 1) 출처 표시 제거: [숫자] 모두 제거
    text = re.sub(r'\[\d+\]', '', article)

    # 2) 들여쓰기/끝쪽 공백 정리
    lines = [ln.strip() for ln in text.split('\n')]

    html_parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 빈 줄
        if not line:
            i += 1
            continue

        # 수평선
        if re.fullmatch(r'-{3,}', line):
            i += 1
            continue

        # 헤딩
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            level = len(m.group(1))
            html_parts.append(f'<h{level}>{_inline_format(m.group(2))}</h{level}>')
            i += 1
            continue

        # 인용문
        if line.startswith('>'):
            content = line.lstrip('>').strip()
            html_parts.append(f'<blockquote>{_inline_format(content)}</blockquote>')
            i += 1
            continue

        # 표 (헤더 다음 줄이 |---|---| 형태)
        if line.startswith('|') and line.endswith('|') \
                and i + 1 < len(lines) and re.fullmatch(r'\|[\s\-:|]+\|', lines[i + 1]):
            header_cells = [c.strip() for c in line.strip('|').split('|')]
            i += 2
            body_rows = []
            while i < len(lines) and lines[i].startswith('|') and lines[i].endswith('|'):
                body_rows.append([c.strip() for c in lines[i].strip('|').split('|')])
                i += 1

            buf = ['<table border="1" style="border-collapse:collapse;">']
            buf.append('<thead><tr>')
            buf.extend(f'<th>{_inline_format(c)}</th>' for c in header_cells)
            buf.append('</tr></thead><tbody>')
            for row in body_rows:
                buf.append('<tr>')
                buf.extend(f'<td>{_inline_format(c)}</td>' for c in row)
                buf.append('</tr>')
            buf.append('</tbody></table>')
            html_parts.append(''.join(buf))
            continue

        # 번호 리스트
        if re.match(r'^\d+\.\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                content = re.sub(r'^\d+\.\s+', '', lines[i])
                items.append(f'<li>{_inline_format(content)}</li>')
                i += 1
            html_parts.append('<ol>' + ''.join(items) + '</ol>')
            continue

        # 불릿 리스트 (- 또는 *)
        if re.match(r'^[-*]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[-*]\s+', lines[i]):
                content = re.sub(r'^[-*]\s+', '', lines[i])
                items.append(f'<li>{_inline_format(content)}</li>')
                i += 1
            html_parts.append('<ul>' + ''.join(items) + '</ul>')
            continue

        # 일반 문단
        html_parts.append(f'<p>{_inline_format(line)}</p>')
        i += 1

    return '\n'.join(html_parts)