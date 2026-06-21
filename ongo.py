from func import *
from daangn_mail import run_daangn_mail
from cafe_scrap import run_cafe_scrap


# chrome://version/ 에서 '프로필경로' 복사, 난 왜 디폴트만 되지?? 뭔... 딴건 필요 없쓰....


def goScript(getDict):

    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(1.5)

    with sync_playwright() as p:

        profile_name = "User_A"  # 나중에 동적으로 바뀔 값

        automated_user_data_dir = os.path.join(
            os.getenv('LOCALAPPDATA'),
            f'Google\\Chrome\\Automation Data\\{profile_name}'
        )

        def launch_chrome():
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
            time.sleep(1.5)
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=automated_user_data_dir,
                headless=False,
                channel="chrome",
                no_viewport=True,
                accept_downloads=True,
                downloads_path=TEMP_DIR,
                args=["--profile-directory=Default", "--window-size=1200,800", "--window-position=0,0"],
            )
            pg_page = ctx.pages[0] if ctx.pages else ctx.new_page()
            pg_page.goto("https://naver.com")
            pg_page.wait_for_load_state("load")
            return ctx, pg_page

        try:
            context, page = launch_chrome()

            if getDict.get('login_check', True):
                pg.alert('로그인 완료 후 확인 누르세요!')

            last_period = 'am' if datetime.now().hour < 12 else 'pm'

            # 여기서부터 무한 반복
            while True:
                current_period = 'am' if datetime.now().hour < 12 else 'pm'
                if current_period != last_period:
                    print(f"크롬 재시작 ({last_period} → {current_period})")
                    try:
                        context.close()
                    except Exception:
                        pass
                    context, page = launch_chrome()
                    last_period = current_period
                    print("크롬 재시작 완료")

                try:
                    # run_daangn_mail(context, page)
                    run_cafe_scrap(context, page)
                    pg.alert('어떻게 할까아아아!!')
                except Exception as e:
                    print(f"에러 발생, 브라우저 재시작: {e}")
                    try:
                        context.close()
                    except Exception:
                        pass
                    time.sleep(5)
                    context, page = launch_chrome()
                    last_period = 'am' if datetime.now().hour < 12 else 'pm'
                    continue

                wait_sec = random.uniform(60, 90)
                print(f"대기 중... {wait_sec:.1f}초")
                time.sleep(wait_sec)

        except Exception as e:
            print(f"초기화 실패: {e}")
