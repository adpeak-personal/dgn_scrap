from func import *




def run_daangn_mail(context, page):
    clear_temp_dir()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 당근 메일 체크 시작...")

    try:
        page.goto("https://mail.naver.com", wait_until="commit")
    except Exception:
        pass
    page.wait_for_load_state("load")
    page.wait_for_selector('.mail_item')
    items = page.locator('.mail_item').all()

    print(f"전체 mail_item 수: {len(items)}")
    last_check_str = read_last_check_time('dgnmail')
    last_check_dt = parse_mail_date(last_check_str)
    print(f"기준 시간: {last_check_str} → {last_check_dt}")

    filterDaaangnList = []
    most_recent_mail_date = None
    for item in items:
        sender_text = item.locator('.mail_sender').text_content()
        title_text = item.locator('.mail_title_link .text').text_content()
        lastDate = item.locator('.mail_date').first.text_content().strip()
        mail_dt = parse_mail_date(lastDate)
        print(f"  [{lastDate}] → {mail_dt} / 기준: {last_check_dt} / 통과: {mail_dt > last_check_dt}")

        if mail_dt <= last_check_dt:
            break

        if most_recent_mail_date is None:
            most_recent_mail_date = lastDate
        if "당근" in sender_text and "수집" in title_text:
            filterDaaangnList.append(item)
        

    print(f"필터링된 메일 수: {len(filterDaaangnList)}")
    if len(filterDaaangnList) == 0:
        print("새 메일 없음 → 1분 대기")
        return

    filterDaaangnList.reverse()
    seen_texts = set()
    deduped = []
    for item in filterDaaangnList:
        item_text = item.text_content()
        m = re.search(r"['''']([^'''']+)['''']", item_text)
        text = m.group(1) if m else ""
        print(f"  텍스트: [{text}] / 중복: {text in seen_texts}")
        if text and text not in seen_texts:
            seen_texts.add(text)
            deduped.append(item)
    filterDaaangnList = deduped
    print(f"중복 제거 후 메일 수: {len(filterDaaangnList)}")

    dgnWorkCount = -1
    while True:
        dgnWorkCount += 1
        if dgnWorkCount >= len(filterDaaangnList):
            break
        item = filterDaaangnList[dgnWorkCount]
        item_text = item.text_content()
        print(f"item 전체 텍스트: [{item_text}]")
        m = re.search(r"['''']([^'''']+)['''']", item_text)
        targetText = m.group(1) if m else ""
        print(f"따옴표 안 텍스트: {targetText}")

        if targetText == "":
            back_to_main(new_tab, page)
            dgnWorkCount -= 1
            continue

        # 1. 메일 클릭 → 팝업 열림
        with context.expect_page() as popup_info:
            item.click()
        popup = popup_info.value
        popup.wait_for_load_state("load")
        delay()
        popup.bring_to_front()

        # 2 & 3. 팝업에서 new_lead_email 클릭 → 원래 창에서 새 탭 열림
        with context.expect_page() as new_tab_info:
            popup.locator('a[href*="new_lead_email"]').click()
        new_tab = new_tab_info.value
        new_tab.wait_for_load_state("load")
        delay()

        # 3. 새 탭 열렸으니 팝업 닫기
        popup.close()
        delay()

        # 4. 새 탭으로 이동
        new_tab.bring_to_front()
        delay()

        # 5. 특정 버튼 체크 후 다음 작업
        target = new_tab.locator('.css-gw53lc.egrz2us3')
        if target.count() > 0:
            for i in range(target.count()):
                if "네이버" in target.nth(i).text_content():
                    target.nth(i).click()
                    delay(1, 2)
                    new_tab.wait_for_load_state("networkidle")
                    delay(1, 2)
                    break
        else:
            print("해당 클래스 없음 또는 네이버 텍스트 없음 → 패스")

        # new_tab (원래 창의 두번째 탭) 으로 작업
        new_tab.wait_for_selector('.c-gAVjGw')
        rows = new_tab.locator('.c-gAVjGw tr').all()
        print(f"tr 개수: {len(rows)}")
        if len(rows) == 0:
            back_to_main(new_tab, page)
            dgnWorkCount -= 1
            continue

        targetSiteEl = new_tab.locator('._1e3k2fr9._1bw2s1dc.h4cur7s._1e3k2fr1._1e3k2fr0._1e3k2fr2')
        targetSiteName = targetSiteEl.text_content()
        print(f"사이트 이름: {targetSiteName}")

        delay(1, 2)
        download_info = None
        for row in rows:
            tds = row.locator('td')
            ths = row.locator('th')
            print(f"  td개수: {tds.count()} / th개수: {ths.count()}")
            if tds.count() == 0:
                continue
            first_td_text = tds.nth(0).text_content()
            print(f"  tr 비교: [{first_td_text}] vs targetText: {targetText}")
            if targetText in first_td_text:
                with new_tab.expect_download() as download_info:
                    tds.nth(5).locator('button').first.click()
                    break

        if download_info is None:
            print("매칭 row 없음 → 패스")
            back_to_main(new_tab, page)
            continue

        delay(2, 3)
        try:
            download = download_info.value
            save_path = os.path.join(TEMP_DIR, download.suggested_filename)
            download.save_as(save_path)
            while not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                time.sleep(0.5)
            print(f"다운로드 완료: {save_path}")
            excel_data = read_excel_with_password(save_path)
            print(f"엑셀 데이터 ({len(excel_data)}행):")
            for row in excel_data:
                print(row)
        except Exception as excel_err:
            print(f"엑셀 읽기 실패: {excel_err}")
            back_to_main(new_tab, page)
            dgnWorkCount -= 1
            continue

        # 사이트에 요청 시작

        targetRoute = ""
        siteLink = ""

        if "애드" in targetSiteName:
            targetRoute = "topby"
            siteLink = "https://api.adpeak.kr/zapier/dgn/"
        elif "리치" in targetSiteName:
            targetRoute = "richby"
            siteLink = "https://api.richby.co.kr/zapier/dgn/"
        elif "위드" in targetSiteName:
            targetRoute = "withby"
            siteLink = "https://api.withby.kr/zapier/dgn/"
        
        route = siteLink + targetRoute

        print(f"요청 URL: {route}")
        payload = {
            "targetText": targetText,
            "excelData": [list(row) for row in excel_data],
        }
        try:
            res = requests.post(route, json=payload, timeout=10)
            print(f"요청 완료: {res.status_code} / {res.text}")
        except Exception as req_err:
            print(f"요청 실패: {req_err}")

        # 이제 요청하기이이이이~~~!!!!
        back_to_main(new_tab, page)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 메일 처리 완료!")

    if most_recent_mail_date:
        write_last_check_time(key='dgnmail')
    print("모든 메일 처리 완료 → 1분 대기")