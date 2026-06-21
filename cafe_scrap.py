from func import *


CAFE_LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cafe_list.txt')


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


def scrap_cafe_detail(context, page):
    """이미 열린 상세 탭(page)에서 제목/내용/날짜 뽑는 함수 (아직 미완성)
    iframe id='cafe_main' 내부 기준으로 작업."""
    frame = page.frame_locator('#cafe_main')
    title = frame.locator('.title_text').inner_text().strip()
    print(f"제목: {title}")

    # se-main-container 내용 뽑아서 print 한번 해줘!! (내용 + 이미지)
    container = frame.locator('.se-main-container')
    content = container.inner_text().strip()
    print(f"내용:\n{content}")

    imgs = container.locator('img')
    img_count = imgs.count()
    print(f"이미지 {img_count}개:")
    for j in range(img_count):
        src = imgs.nth(j).get_attribute('src') or imgs.nth(j).get_attribute('data-src')
        print(f"  - {src}")
    pg.alert('보자공?')
    # TODO: 내용/날짜 등 상세 작업 예정