from ongo import *
import ctypes
import os

def _load_suit_fonts():
    font_dir = os.path.join(os.path.dirname(__file__), "font")
    for fname in ("SUIT-Regular.ttf", "SUIT-Medium.ttf", "SUIT-Bold.ttf", "SUIT-SemiBold.ttf"):
        path = os.path.join(font_dir, fname)
        if os.path.exists(path):
            ctypes.windll.gdi32.AddFontResourceW(path)

_load_suit_fonts()
FONT = "SUIT"


def th():
    getDict = {'login_check': login_check_var.get()}
    onth = threading.Thread(target=lambda: goScript(getDict))
    onth.daemon = True
    onth.start()


root = Tk()
root.title("당근 & 크롤링 자동화")
root.geometry("300x210+500+300")
root.resizable(False, False)
root.configure(bg="#f2f2f2")

# 타이틀 바
title_bar = Frame(root, bg="#1a1a2e", height=44)
title_bar.pack(fill=X)
title_bar.pack_propagate(False)
Label(title_bar, text="당근 & 크롤링 자동화", bg="#1a1a2e", fg="white",
      font=(FONT, 11, "bold")).pack(side=LEFT, padx=14, pady=10)

# 본문
body = Frame(root, bg="#f2f2f2", padx=16, pady=14)
body.pack(fill=BOTH, expand=True)

# 옵션 그룹
opt = LabelFrame(body, text=" 옵션 ", bg="#f2f2f2",
                 font=(FONT, 9, "bold"), fg="#666666",
                 padx=12, pady=8, relief=GROOVE)
opt.pack(fill=X)

login_check_var = BooleanVar(value=True)
Checkbutton(opt, text="로그인 체크", variable=login_check_var,
            bg="#f2f2f2", font=(FONT, 9), fg="#333333",
            activebackground="#f2f2f2", cursor="hand2"
            ).pack(anchor=W)

# 시작 버튼
Button(body, text="시작하기", command=th,
       font=(FONT, 11, "bold"),
       bg="#3d7cf0", fg="white",
       activebackground="#2f6bdc", activeforeground="white",
       relief=FLAT, cursor="hand2", pady=8
       ).pack(fill=X, pady=(12, 0))

root.mainloop()
