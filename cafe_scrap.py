from func import *
import html
import hmac
import hashlib
import base64


CAFE_LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cafe_list.txt')

# ── 백엔드 연동 설정 ──────────────────────────────────────────────
BACKEND_BASE = "http://localhost:3041"        # zk-back .env PORT
JWT_SECRET = "dev-secret-change-me"           # zk-back .env JWT_SECRET 와 동일해야 함
MASTER_USER_ID = 13                            # changyong112@naver.com (마스터 고정)
MASTER_ROLE = "ADMIN"
BOARD_SLUG = "hotdeal"
PSTATIC_PREFIX = "https://cafeptthumb-phinf.pstatic.net"

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
    threshold = parse_mail_date(read_last_check_time('cafe1'))  # 기준 시간 (이전이면 패스)
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
                if post_dt <= threshold:  # 기준 시간 이전이면 패스
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

                # 상세 탭 닫고 목록 탭으로 복귀
                new_tab.close()
                page.bring_to_front()
            
            pg.alert('리스트 나온거 확인!!!')
        except Exception:
            pass
        page.wait_for_load_state("load")
        delay()


# ── 백엔드 업로드 헬퍼 ────────────────────────────────────────────
def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def make_master_token() -> str:
    """zk-back JWT_SECRET 로 마스터(user 13) access 토큰을 직접 서명해서 반환.
    (/api/auth/master 로그인과 동일한 Bearer 토큰 — 비밀번호 없이 고정 발급)"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": MASTER_USER_ID, "role": MASTER_ROLE, "type": "access",
               "iat": now, "exp": now + 3600}
    seg = (_b64url(json.dumps(header, separators=(',', ':')).encode()) + b'.' +
           _b64url(json.dumps(payload, separators=(',', ':')).encode()))
    sig = hmac.new(JWT_SECRET.encode(), seg, hashlib.sha256).digest()
    return (seg + b'.' + _b64url(sig)).decode()


_master_token = None


def auth_headers() -> dict:
    """매 호출마다 토큰 재사용 (만료 1h)."""
    global _master_token
    if _master_token is None:
        _master_token = make_master_token()
    return {"Authorization": f"Bearer {_master_token}"}


def download_pstatic_image(url: str):
    """pstatic 이미지 다운로드 (Referer 필요). (bytes, content_type) 반환, 실패 시 None."""
    try:
        r = requests.get(url, headers={
            "Referer": "https://cafe.naver.com/",
            "User-Agent": "Mozilla/5.0",
        }, timeout=30)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "image/jpeg")
        if not ct.startswith("image/"):
            ct = "image/jpeg"
        return r.content, ct
    except Exception as e:
        print(f"    이미지 다운로드 실패: {e}")
        return None


def upload_image_to_gcs(content: bytes, filename: str, content_type: str):
    """백엔드 /api/upload/image 로 업로드 → GCS tmp URL 반환, 실패 시 None."""
    try:
        files = {"file": (filename, content, content_type)}
        r = requests.post(f"{BACKEND_BASE}/api/upload/image",
                          headers=auth_headers(), files=files, timeout=60)
        r.raise_for_status()
        return r.json().get("url")
    except Exception as e:
        print(f"    이미지 업로드 실패: {e}")
        return None


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
    for name in MALL_NAMES:
        if name in title:
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


def extract_comment_link(frame):
    """댓글 3개까지에서 첫 URL 또는 상품번호(8자리+) 추출. 없으면 None."""
    try:
        boxes = frame.locator('.comment_list .comment_text_box')
        n = min(boxes.count(), 3)
        for i in range(n):
            text = boxes.nth(i).inner_text().strip()
            m = URL_RE.search(text)
            if m:
                return m.group(0)
            m = re.search(r'\b(\d{8,})\b', text)  # 상품번호 힌트
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def scrap_cafe_detail(context, page):
    """상세 탭(iframe #cafe_main)에서 제목/본문/이미지/쇼핑몰/가격을 뽑아
    백엔드(hotdeal 게시판)로 업로드한다."""
    frame = page.frame_locator('#cafe_main')

    # 가입해야 볼 수 있는 글 → 패스
    if frame.locator('.article_permission_blind').count() > 0:
        print("  가입 전용(블라인드) 글 → 패스")
        return

    title = frame.locator('.title_text').inner_text().strip()
    print(f"제목: {title}")

    container = frame.locator('.se-main-container')
    comps = container.locator(':scope > .se-component')
    comp_count = comps.count()

    html_parts = []   # 본문 HTML 조각 (순서 유지)
    hint_urls = []    # 쇼핑몰/딜 링크 힌트
    img_uploaded = 0

    for i in range(comp_count):
        comp = comps.nth(i)
        cls = comp.get_attribute('class') or ''

        # 링크 박스(oglink) → 본문 제외, 힌트로만 사용
        if 'oglink' in cls:
            try:
                href = comp.locator('a').first.get_attribute('href')
                if href:
                    hint_urls.append(href)
            except Exception:
                pass
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
                dl = download_pstatic_image(src)
                if dl:
                    body, ct = dl
                    ext = 'png' if 'png' in ct else 'jpg'
                    url = upload_image_to_gcs(body, f"cafe_{i}.{ext}", ct)
                    if url:
                        html_parts.append(f'<img src="{url}">')
                        img_uploaded += 1
            continue

        # 텍스트 → <p>, 본문 내 링크도 힌트 수집
        if 'se-text' in cls:
            try:
                paras = comp.locator('.se-text-paragraph')
                for j in range(paras.count()):
                    t = paras.nth(j).inner_text().strip()
                    if t:
                        html_parts.append(f'<p>{html.escape(t)}</p>')
                links = comp.locator('a')
                for j in range(links.count()):
                    href = links.nth(j).get_attribute('href')
                    if href and href.startswith('http'):
                        hint_urls.append(href)
            except Exception:
                pass
            continue

    # 쇼핑몰 / 가격
    mall = detect_mall_from_title(title)
    price = parse_price_from_title(title)
    deal_url = hint_urls[0] if hint_urls else None

    # 쿠팡이거나 본문 링크 없음 → 댓글(3개)에서 링크/상품번호, 없으면 패스
    if mall == '쿠팡' or not hint_urls:
        c = extract_comment_link(frame)
        if c:
            deal_url = deal_url or c
            hint_urls.append(c)
        elif not deal_url:
            print("  쿠팡/링크없음 + 댓글에도 링크 없음 → 패스")
            return

    if mall is None:
        mall = detect_mall_from_urls(hint_urls)

    content_html = ''.join(html_parts).strip()
    if not content_html:
        print("  본문 내용 없음 → 패스")
        return

    extra_data = {
        "mall": mall,
        "price": price,
        "is_ended": False,
        "deal_url": deal_url,
        "source_url": page.url,
    }

    print(f"  쇼핑몰: {mall} / 가격: {price} / 이미지: {img_uploaded}개 / 링크: {deal_url}")
    post_id = create_post(title, content_html, extra_data)
    if post_id:
        print(f"  ✅ 업로드 완료 (post id={post_id})")