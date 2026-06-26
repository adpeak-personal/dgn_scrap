from func import *
from upload import (BACKEND_BASE, auth_headers, download_image,
                    upload_image_to_gcs)
import html


CAFE_LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cafe_list.txt')

# ── 백엔드 연동 설정 ──────────────────────────────────────────────
BOARD_SLUG = "hotdeal"
PSTATIC_PREFIX = "https://cafeptthumb-phinf.pstatic.net"
CAFE_REFERER = "https://cafe.naver.com/"

# 제목/링크 → 쇼핑몰 매핑 (zk-front src/data/constants.ts MALLS 기준)
MALL_NAMES = ["쿠팡", "11번가", "G마켓", "옥션", "SSG닷컴", "롯데온", "위메프", "티몬",
              "인터파크", "네이버쇼핑", "카카오쇼핑", "다나와", "에누리", "GS샵", "CJ온스타일"]
MALL_DOMAINS = {
    "coupang.com": "쿠팡", "coupa.ng": "쿠팡",
    "11st.co.kr": "11번가",
    "gmarket.co.kr": "G마켓",
    "auction.co.kr": "옥션",
    "ssg.com": "SSG닷컴",
    "lotteon.com": "롯데온",
    "wemakeprice.com": "위메프", "wmp.kr": "위메프",
    "tmon.co.kr": "티몬", "tmon.kr": "티몬",
    "interpark.com": "인터파크",
    "smartstore.naver.com": "네이버쇼핑", "shopping.naver.com": "네이버쇼핑", "naver.me": "네이버쇼핑",
    "gsshop.com": "GS샵",
    "cjonstyle.com": "CJ온스타일",
    "danawa.com": "다나와",
    "enuri.com": "에누리",
}
# 제목 안에 들어있는 별칭(한글/영문/약칭) → 표준 mall명
MALL_ALIASES = {
    "쿠팡": "쿠팡", "coupang": "쿠팡",
    "11번가": "11번가", "11st": "11번가", "십일번가": "11번가",
    "G마켓": "G마켓", "지마켓": "G마켓", "gmarket": "G마켓",
    "옥션": "옥션", "auction": "옥션",
    "SSG닷컴": "SSG닷컴", "SSG": "SSG닷컴", "쓱": "SSG닷컴", "이마트몰": "SSG닷컴",
    "롯데온": "롯데온", "lotteon": "롯데온",
    "위메프": "위메프", "wemakeprice": "위메프",
    "티몬": "티몬", "tmon": "티몬",
    "인터파크": "인터파크", "interpark": "인터파크",
    "네이버쇼핑": "네이버쇼핑", "네이버": "네이버쇼핑", "스마트스토어": "네이버쇼핑", "네쇼": "네이버쇼핑",
    "카카오쇼핑": "카카오쇼핑", "카카오": "카카오쇼핑",
    "다나와": "다나와",
    "에누리": "에누리",
    "GS샵": "GS샵", "GS홈쇼핑": "GS샵",
    "CJ온스타일": "CJ온스타일", "CJ몰": "CJ온스타일",
}


def read_cafe_list():
    """cafe_list.txt 한 줄씩 읽어서 링크 리스트 반환 (빈 줄 제외)"""
    with open(CAFE_LIST_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def parse_cafe_date(text):
    """오늘 글('HH:MM')만 datetime으로 반환, 그 외(날짜 표기)는 None."""
    text = text.strip()
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', text)  # 17:30 (오늘)
    if m:
        h, mi = map(int, m.groups())
        return datetime.now().replace(hour=h, minute=mi, second=0, microsecond=0)
    return None


def run_cafe_scrap(context, page):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 카페 스크랩 시작...")
    links = read_cafe_list()
    last_check_str = read_last_check_time('cafe1', default=None)
    threshold = parse_mail_date(last_check_str) if last_check_str else None  # 없으면 오늘 글 전체 통과
    for idx, link in enumerate(links, 1):
        print(f"[{idx}/{len(links)}] 이동: {link}")
        try:
            page.goto(link, wait_until="commit")

            # .article-board 요소 나올떄까지 대기
            page.wait_for_selector('.article-board', timeout=10000)

            # .article-table 하위 tbody 마지막 요소의 tr 리스트 뽑아서 print
            rows = page.locator('.article-table tbody').last.locator('tr')
            count = rows.count()
            print(f"  tr 개수: {count}")
            for i in range(count - 1, -1, -1):
                # rows.nth(i) 여기 안에 td_normal type_date 요소의 텍스트 좀 찾아주라
                date_text = rows.nth(i).locator('.td_normal.type_date').inner_text().strip()
                post_dt = parse_cafe_date(date_text)
                if post_dt is None:  # 오늘(HH:MM) 글이 아니면 패스
                    print(f"  [{i + 1}] {date_text} → 오늘 글 아님, 패스")
                    continue
                if threshold is not None and post_dt <= threshold:  # 기준 시간 이전이면 패스
                    print(f"  [{i + 1}] {date_text} → 기준({threshold:%m.%d %H:%M}) 이전, 패스")
                    continue

                print(f"  [{i + 1}] {date_text}")

                # .inner_list .article 새 탭에서 나오게 클릭 → 두번째 탭으로 변경
                with context.expect_page() as new_page_info:
                    rows.nth(i).locator('.inner_list .article').click(modifiers=["Control"])
                new_tab = new_page_info.value
                new_tab.bring_to_front()  # 화면에 보이는 탭을 두번째 탭으로 전환
                new_tab.wait_for_load_state("load")

                # iframe id="cafe_main" 내부의 .title_text 나올때까지 대기
                new_tab.frame_locator('#cafe_main').locator('.title_text').wait_for(timeout=10000)

                # 상세 작업
                scrap_cafe_detail(context, new_tab)

                pg.alert('잘 들어가졌나 체크 한번!!!')

                # 상세 탭 닫고 목록 탭으로 복귀
                new_tab.close()
                page.bring_to_front()
            
            pg.alert('리스트 나온거 확인!!!')
        except Exception:
            pg.alert('에러 체크크크!!!')
            pass
        page.wait_for_load_state("load")
        delay()


# ── 백엔드 업로드 헬퍼 ────────────────────────────────────────────
# 공통 헬퍼(auth_headers / download_image / upload_image_to_gcs)는 upload.py 에서 import.


def create_post(title: str, content_html: str, extra_data: dict):
    """백엔드 /api/posts 로 글 작성. 성공 시 post id, 실패 시 None."""
    try:
        r = requests.post(f"{BACKEND_BASE}/api/posts",
                          headers={**auth_headers(), "Content-Type": "application/json"},
                          json={"board_slug": BOARD_SLUG, "title": title,
                                "content": content_html, "extra_data": extra_data},
                          timeout=30)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        print(f"  글 작성 실패: {e}")
        return None


# ── 파싱 헬퍼 ────────────────────────────────────────────────────
def parse_price_from_title(title: str):
    """제목에서 가격 파싱 (write/page.tsx parsePriceFromTitle 포팅)."""
    m = re.search(r'([\d,]+)\s*원', title)
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            pass
    m = re.search(r'([\d.]+)\s*만원', title)
    if m:
        try:
            return round(float(m.group(1)) * 10000)
        except ValueError:
            pass
    return None


def detect_mall_from_title(title: str):
    """제목에 별칭이 substring으로 포함되면 표준 mall명 반환.
    예: '지마켓) 스파오 후아요...' → 'G마켓'.
    별칭은 대소문자 무관."""
    t = title.lower()
    for alias, name in MALL_ALIASES.items():
        if alias.lower() in t:
            return name
    return None


def detect_mall_from_urls(urls):
    for u in urls:
        if not u:
            continue
        for domain, name in MALL_DOMAINS.items():
            if domain in u:
                return name
    return None


URL_RE = re.compile(r'https?://[^\s)"\'<>]+')


def extract_comment_info(frame):
    """댓글(최대 3개)에서 (URL, 상품번호) 반환. 못 찾은 항목은 None.
    상품번호는 5자리 이상 숫자."""
    url, number = None, None
    try:
        boxes = frame.locator('.comment_list .comment_text_box')
        n = min(boxes.count(), 3)
        for i in range(n):
            text = boxes.nth(i).inner_text().strip()
            if url is None:
                m = URL_RE.search(text)
                if m:
                    url = m.group(0)
            if number is None:
                m = re.search(r'\b(\d{5,})\b', text)
                if m:
                    number = m.group(1)
            if url and number:
                break
    except Exception:
        pass
    return url, number


def _build_oglink_card(comp):
    """oglink 컴포넌트에서 (카드 HTML, href) 반환. href 없으면 None."""
    try:
        href = comp.locator('a').first.get_attribute('href') or ''
    except Exception:
        return None
    if not href:
        return None

    def _text(sel):
        try:
            loc = comp.locator(sel).first
            if loc.count() > 0:
                return loc.inner_text().strip()
        except Exception:
            pass
        return ''

    og_title = _text('.se-oglink-title') or _text('.og_title')
    og_desc = _text('.se-oglink-summary') or _text('.og_summary')
    og_url = _text('.se-oglink-url') or _text('.og_url') or href

    img_src = ''
    try:
        img = comp.locator('img').first
        if img.count() > 0:
            img_src = (img.get_attribute('src')
                       or img.get_attribute('data-lazy-src')
                       or img.get_attribute('data-src') or '')
    except Exception:
        pass

    img_html = (
        f'<img src="{html.escape(img_src, quote=True)}" alt="" '
        f'style="width:120px;height:120px;object-fit:cover;flex:none;background:#f3f4f6">'
    ) if img_src else ''
    title_html = (
        f'<div style="font-weight:600;font-size:14px;line-height:1.4;'
        f'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;'
        f'overflow:hidden">{html.escape(og_title)}</div>'
    ) if og_title else ''
    desc_html = (
        f'<div style="font-size:12px;color:#6b7280;line-height:1.4;'
        f'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;'
        f'overflow:hidden">{html.escape(og_desc)}</div>'
    ) if og_desc else ''
    url_html = (
        f'<div style="font-size:11px;color:#9ca3af;white-space:nowrap;'
        f'overflow:hidden;text-overflow:ellipsis;margin-top:auto">{html.escape(og_url)}</div>'
    )

    card = (
        f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer" '
        f'style="display:flex;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;'
        f'text-decoration:none;color:inherit;max-width:520px;margin:12px 0;background:#fff">'
        f'{img_html}'
        f'<div style="padding:10px 14px;display:flex;flex-direction:column;gap:4px;min-width:0;flex:1">'
        f'{title_html}{desc_html}{url_html}'
        f'</div></a>'
    )
    return card, href


def scrap_cafe_detail(context, page):
    """상세 탭(iframe #cafe_main)에서 제목/본문/이미지를 뽑아 hotdeal 게시판에 업로드.
    진입 직후 3초 대기 → F5(콘텐츠 안 보이는 화면 방지) → title 다시 대기 → 본 작업 1회.
    본문 맨 마지막에 꼬리(링크 카드 / a태그 / 상품번호) 1개 부착.
    우선순위:
      1) oglink (.se-section-oglink) 있으면 → 링크 카드
      2) 없고 URL이 있으면 (본문 → 댓글) → <a> 태그
      3) 없고 상품번호(5자리+) 있으면 (본문 → 댓글) → 텍스트
    셋 다 없으면 패스. 1·2의 경우 deal_url을 채워 '최저가 바로가기'에 연결."""
    time.sleep(3)
    try:
        page.reload(wait_until="load")
        page.frame_locator('#cafe_main').locator('.title_text').wait_for(timeout=10000)
    except Exception:
        print("  새로고침 후 title 못 찾음 → 패스")
        return

    frame = page.frame_locator('#cafe_main')

    if frame.locator('.article_permission_blind').count() > 0:
        print("  가입 전용(블라인드) 글 → 패스")
        return

    title = frame.locator('.title_text').inner_text().strip()
    print(f"제목: {title}")

    container = frame.locator('.se-main-container')
    comps = container.locator(':scope > .se-component')
    comp_count = comps.count()

    parts_buffer = []  # ('text', 원문) / ('img', html) - 순서 유지
    body_texts = []   # 상품번호 추출용
    text_urls = []    # 본문 URL (꼬리 후보 / mall 판정)
    oglink = None     # (card_html, href)
    img_uploaded = 0

    for i in range(comp_count):
        comp = comps.nth(i)
        cls = comp.get_attribute('class') or ''

        # 링크 박스(oglink) → 본문에 안 넣고 첫 번째만 꼬리 후보로 저장
        if 'oglink' in cls:
            if oglink is None:
                oglink = _build_oglink_card(comp)
            continue

        # 이미지 → pstatic 만 GCS 업로드
        if 'se-image' in cls:
            try:
                img = comp.locator('img').first
                src = (img.get_attribute('src')
                       or img.get_attribute('data-lazy-src')
                       or img.get_attribute('data-src'))
            except Exception:
                src = None
            if src and src.startswith(PSTATIC_PREFIX):
                dl = download_image(src, referer=CAFE_REFERER)
                if dl:
                    body, ct = dl
                    ext = 'png' if 'png' in ct else 'jpg'
                    url = upload_image_to_gcs(body, f"cafe_{i}.{ext}", ct)
                    if url:
                        parts_buffer.append(('img', f'<img src="{url}">'))
                        img_uploaded += 1
            continue

        # 텍스트 → 일단 버퍼링. URL은 꼬리/판정용으로 따로 수집.
        if 'se-text' in cls:
            try:
                paras = comp.locator('.se-text-paragraph')
                for j in range(paras.count()):
                    t = paras.nth(j).inner_text().strip()
                    if t:
                        parts_buffer.append(('text', t))
                        body_texts.append(t)
                        for m in URL_RE.finditer(t):
                            text_urls.append(m.group(0))
                links = comp.locator('a')
                for j in range(links.count()):
                    href = links.nth(j).get_attribute('href')
                    if href and href.startswith('http'):
                        text_urls.append(href)
            except Exception:
                pass
            continue

    # oglink 카드가 있으면 본문 텍스트에서 URL 제거 (카드와 중복 방지)
    strip_urls = oglink is not None
    html_parts = []
    for kind, val in parts_buffer:
        if kind == 'img':
            html_parts.append(val)
        else:  # 'text'
            text = URL_RE.sub('', val).strip() if strip_urls else val
            if text:
                html_parts.append(f'<p>{html.escape(text)}</p>')

    # 꼬리 결정
    deal_url = None
    tail_html = None
    c_url, c_num = None, None

    if oglink is not None:
        tail_html, deal_url = oglink
    else:
        url = text_urls[0] if text_urls else None
        if url is None:
            c_url, c_num = extract_comment_info(frame)
            url = c_url
        if url:
            deal_url = url
            tail_html = (
                f'<p><a href="{html.escape(url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{html.escape(url)}</a></p>'
            )
        else:
            body_combined = ' '.join(body_texts)
            m = re.search(r'\b(\d{5,})\b', body_combined)
            num = m.group(1) if m else c_num
            if num:
                tail_html = f'<p>{html.escape(num)}</p>'

    if tail_html is None:
        print("  링크/상품번호 없음 → 패스")
        return

    html_parts.append(tail_html)
    content_html = ''.join(html_parts).strip()

    # 쇼핑몰 / 가격
    mall = detect_mall_from_title(title)
    if mall is None:
        urls_for_mall = ([deal_url] if deal_url else []) + text_urls
        mall = detect_mall_from_urls(urls_for_mall)
    price = parse_price_from_title(title)

    extra_data = {
        "mall": mall,
        "price": price,
        "is_ended": False,
        "deal_url": deal_url,   # 있으면 프론트 '최저가 바로가기' 연결됨
        "source_url": page.url,
    }

    print(f"  쇼핑몰: {mall} / 가격: {price} / 이미지: {img_uploaded}개 / 링크: {deal_url}")
    post_id = create_post(title, content_html, extra_data)
    if post_id:
        print(f"  ✅ 업로드 완료 (post id={post_id})")