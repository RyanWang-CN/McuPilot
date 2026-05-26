"""McuPilot Setup — Splash + 环境检测 + PyWebView GUI"""
import os, sys, json, threading, subprocess, time, tkinter as tk
from PIL import Image, ImageDraw, ImageTk

TOOLS_ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(TOOLS_ROOT, 'assets', 'setup_ui_v2_working.html')
REQ_PATH = os.path.join(TOOLS_ROOT, 'requirements.txt')

# ── Splash ───────────────────────────────────────────
class Splash:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.W, self.H = 490, 260
        self.root.geometry(f'{self.W}x{self.H}+'
            f'{(self.root.winfo_screenwidth()-self.W)//2}+'
            f'{(self.root.winfo_screenheight()-self.H)//2}')
        self.root.attributes('-alpha', 0.0)

        c = tk.Canvas(self.root, width=self.W, height=self.H,
                      bg='#fafafc', highlightthickness=0, bd=0)
        c.pack()

        # 微渐变
        for i in range(self.H):
            t = i/self.H; r=int(250-8*t); g=int(250-5*t); b=int(252-2*t)
            c.create_line(0, i, self.W, i, fill=f'#{r:02x}{g:02x}{b:02x}')
        # 极淡优雅底纹 — 两条 Lissajous 风格曲线
        import math
        for y0, amp, freq, ph in [(140, 30, 0.018, 0), (190, 20, 0.025, 1.2)]:
            pts = []
            for x in range(-10, self.W+10, 2):
                pts.extend([x, y0 + math.sin(x*freq+ph)*amp])
            c.create_line(*pts, fill='#eaeaf0', width=1, smooth=True)

        # 衬线
        c.create_rectangle(3, 3, self.W-4, self.H-4, fill='', outline='#d8d8e0', width=1)

        # 图标 — 加载 PNG
        png = os.path.join(TOOLS_ROOT, 'assets', 'mcupilot_iconsp.png')
        if os.path.exists(png):
            sz = 108
            img = Image.open(png).resize((sz, sz), Image.LANCZOS)
            self._icon_img = ImageTk.PhotoImage(img)
            c.create_image(84, 89, image=self._icon_img, anchor='center')

        # 标题
        c.create_text(170, 42, text='McuPilot', font=('Segoe UI', 20, 'bold'),
                      fill='#1a1a24', anchor='w')
        c.create_text(170, 66, text='项目配置向导 \u00b7 环境准备',
                      font=('Microsoft YaHei', 8), fill='#7a7a88', anchor='w')
        c.create_line(170, 84, self.W-38, 84, fill='#e8e8ee')
        c.create_text(170, 98, text='RyanWang  \u00b7  MIT License  \u00a9 2026',
                      font=('Segoe UI', 7), fill='#b0b0ba', anchor='w')

        # 日志行
        self.logs = []
        log_y = 118
        for _ in range(4):
            self.logs.append(c.create_text(170, log_y, text='',
                font=('Consolas', 8), fill='#888', anchor='w'))
            log_y += 14

        # 进度条
        bar_y = log_y + 10; bar_h = 4
        self._bar_y = bar_y; self._bar_w = self.W - 76
        # 轨道
        track = Image.new('RGBA', (self._bar_w, bar_h), (0,0,0,0))
        tdraw = ImageDraw.Draw(track)
        tdraw.rounded_rectangle([0,0,self._bar_w-1,bar_h-1], radius=2, fill=(0xe8,0xe8,0xee,255))
        self._track_img = ImageTk.PhotoImage(track)
        c.create_image(38 + self._bar_w//2, bar_y+bar_h//2, image=self._track_img)
        # 填充
        self._bar_img = None
        self.pct = c.create_text(self.W-40, bar_y+14, text='', font=('Consolas', 8),
                                 fill='#a0a0b0', anchor='e')

        # 按钮区
        btn_y = bar_y + 30
        btns_bg = '#f3f6f9'
        self.btn_frame = tk.Frame(self.root, bg=btns_bg)
        self.btn_install = tk.Label(self.btn_frame, text='安装',
            font=('Microsoft YaHei', 10), fg='#ea580c', bg=btns_bg, cursor='hand2')
        self.btn_exit = tk.Label(self.btn_frame, text='退出',
            font=('Microsoft YaHei', 10), fg='#999', bg=btns_bg, cursor='hand2')
        for b in [self.btn_install, self.btn_exit]:
            b.bind('<Enter>', lambda e, w=b: w.config(fg='#d04a0a' if w is self.btn_install else '#666'))
            b.bind('<Leave>', lambda e, w=b: w.config(fg='#ea580c' if w is self.btn_install else '#999'))
        self._btn_y = btn_y

        self.c = c
        self._fade_in()

    def _fade_in(self):
        for a in range(1, 12):
            self.root.attributes('-alpha', a/11); self.root.update(); time.sleep(0.01)

    def _fade_out(self):
        for a in range(11, -1, -1):
            self.root.attributes('-alpha', a/11); self.root.update(); time.sleep(0.012)

    def log(self, i, color, text):
        self.c.itemconfig(self.logs[i], text=text, fill=color); self.root.update()

    def set_bar(self, pct):
        fw = max(4, int(self._bar_w * pct / 100))
        if fw < 4: fw = 4
        fill = Image.new('RGBA', (fw, 4), (0,0,0,0))
        fdraw = ImageDraw.Draw(fill)
        fdraw.rounded_rectangle([0,0,fw-1,3], radius=2, fill=(0xea,0x58,0x0c,255))
        if hasattr(self, '_bar_img') and self._bar_img:
            self.c.delete('bar_fill')
        self._bar_img = ImageTk.PhotoImage(fill)
        self.c.create_image(38 + fw//2, self._bar_y+2, image=self._bar_img, anchor='center', tags='bar_fill')
        self.c.itemconfig(self.pct, text=f'{int(pct)}%'); self.root.update()

    def show_buttons(self, install_cb, exit_cb):
        self._install_cb = install_cb
        self._exit_cb = exit_cb
        self.btn_install.bind('<Button-1>', lambda e: install_cb())
        self.btn_exit.bind('<Button-1>', lambda e: exit_cb())
        self.btn_install.pack(side='left', padx=(0, 16))
        self.btn_exit.pack(side='left')
        self.c.create_window(self.W//2, self._btn_y, window=self.btn_frame)
        self.root.update()

    def disable_btns(self):
        self.btn_install.unbind('<Button-1>')
        self.btn_exit.unbind('<Button-1>')
        self.btn_install.config(fg='#ddd')
        self.btn_exit.config(fg='#ddd')

    def enable_btns(self):
        self.btn_install.bind('<Button-1>', lambda e: self._install_cb())
        self.btn_exit.bind('<Button-1>', lambda e: self._exit_cb())
        self.btn_install.config(fg='#ea580c')
        self.btn_exit.config(fg='#aaa')

    def destroy(self): self.root.destroy()

# ── 检测逻辑 ─────────────────────────────────────────
def check_python():
    v = sys.version_info
    return (v.major>=3 and v.minor>=10), f'{v.major}.{v.minor}.{v.micro}'

def check_pip_deps():
    # 包名 → import 名映射（pip 包名和 Python import 名不同的情况）
    import_map = {
        'pylink-square': 'pylink',
        'python-dotenv': 'dotenv',
        'pyyaml': 'yaml',
        'pywin32': 'win32com',
        'llama-cloud': 'llama_cloud',
        'pyelftools': 'elftools',
        'mcp': 'mcp',
        'filelock': 'filelock',
        'customtkinter': 'customtkinter',
    }
    missing = []
    try:
        with open(REQ_PATH, encoding='utf-8') as f:
            reqs = [l.split('#')[0].strip().split('>=')[0].split('==')[0].strip().split('[')[0]
                    for l in f if l.strip() and not l.startswith('#')]
    except: return True, []
    for pkg in reqs:
        if not pkg: continue
        mod = import_map.get(pkg, pkg.replace('-', '_'))
        try: __import__(mod)
        except ImportError: missing.append(pkg)
    return len(missing)==0, missing

def install_deps():
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', REQ_PATH, '-q'],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except: return False

# ── GUI 启动 ─────────────────────────────────────────
# 先创建窗口对象，稍后再 start()，确保焦点正确
def create_gui():
    import webview
    class Api:
        def browse_folder(self):
            import tkinter.filedialog as fd
            r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)
            p = fd.askdirectory(title="选择 Keil 工程目录"); r.destroy()
            return p or ""
        def check_env(self, project_path):
            from core.project_wizard import check_env
            return json.dumps(check_env(project_path), ensure_ascii=False)
        def deploy(self, project_path, params_json, clients_json):
            from core.project_wizard import deploy
            params = json.loads(params_json); clients = json.loads(clients_json)
            def progress(step_idx, status, msg):
                js = f"onStepUpdate({step_idx}, '{status}', {json.dumps(msg, ensure_ascii=False)})"
                webview.windows[0].evaluate_js(js)
            threading.Thread(target=deploy,
                args=(project_path, params, clients, TOOLS_ROOT, progress), daemon=True).start()

    import tkinter as tk
    r = tk.Tk(); r.withdraw()
    sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
    r.destroy()
    window = webview.create_window(
        title='McuPilot — 项目配置向导',
        url='file://' + HTML_PATH,
        js_api=Api(),
        width=780, height=760,
        x=(sw-780)//2, y=(sh-760)//2,
        resizable=False,
        background_color='#f3f4f6',
    )
    return window

def start_gui():
    import webview
    webview.start(debug=False)

# ── 主入口 ───────────────────────────────────────────
if __name__ == '__main__':
    # 先创建 GUI 窗口对象（隐藏），splash 关闭后自动获得焦点
    gui_win = create_gui()
    s = Splash()

    # 1. Python
    s.log(0, '#555', '[Python ] Checking environment...')
    s.set_bar(15); time.sleep(0.3)
    p_ok, p_ver = check_python()
    if p_ok:
        s.log(0, '#16a34a', f'[Python ] Python {p_ver}  \u2713')
    else:
        s.log(0, '#dc2626', f'[Python ] Requires \u2265 3.10, current {p_ver}')
        s.set_bar(100); time.sleep(1)
        s.destroy(); sys.exit(1)

    # 2. pip 依赖
    s.log(1, '#555', '[Pip    ] Checking...')
    s.set_bar(30); time.sleep(0.2)
    dep_ok, missing = check_pip_deps()

    if dep_ok:
        s.log(1, '#16a34a', '[Pip    ] \u2713')
        s.set_bar(100); s.root.update()
        s._fade_out(); s.root.withdraw()
    else:
        # 缺依赖：每行最多放够
        per = 5
        for i in range(0, len(missing), per):
            chunk = ', '.join(missing[i:i+per])
            s.log(1 + i, '#ea580c', f'[Missing] {chunk}')
        s.set_bar(50)

        def do_install():
            s.disable_btns()
            s.btn_install.config(text='...')
            s.log(1, '#ea580c', f'[Pip    ] Installing {len(missing)} packages...')
            s.set_bar(60); s.root.update()
            if install_deps():
                s.log(1, '#16a34a', '[Pip    ] \u2713')
                s.set_bar(100); s.root.update(); time.sleep(0.6)
                s._fade_out(); s.root.withdraw()
                start_gui()
                try: s.destroy()
                except: pass
            else:
                s.log(1, '#dc2626', '[Pip    ] \u2717 安装失败，请检查网络后重试')
                s.btn_install.config(text='重试')
                s.enable_btns()

        def do_exit():
            s._fade_out(); s.destroy(); sys.exit(0)

        s.show_buttons(do_install, do_exit)
        s.root.mainloop()
        # 如果点了安装且成功，launch_gui 已在 do_install 中调用
        sys.exit(0)

    # 全部通过 → 启动 GUI
    start_gui()
    try: s.destroy()
    except: pass
