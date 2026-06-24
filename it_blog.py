from func import *
from openai import OpenAI
import re
import requests


# 클라이언트 객체 생성 (여기에 API 키 입력)
client = OpenAI(
    api_key=,
    base_url="https://api.perplexity.ai" # 목적지를 OpenAI에서 퍼플렉시티로 변경!
)

# 네이버 검색 API 키 (https://developers.naver.com/apps 에서 발급)





def it_blog():
    # 실행 예시
    # topic = "부천 휴대폰 성지 갤럭시s26 플러스 합리적으로 사는 방법?!"
    keyword1="갤럭시s26 플러스"
    # article = generate_it_post(topic, keyword)
    # print(article)
    image_urls = search_naver_image(keyword1, display=30)
    # html = clean_and_convert_to_html(article)
    # print(html)


    pg.alert('체크체크!!!')


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