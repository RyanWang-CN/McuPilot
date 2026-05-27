"""McuPilot Setup — Splash + 环境检测 + PyWebView GUI"""
import os, sys, json, threading, subprocess, time, math, tkinter as tk
from PIL import Image, ImageDraw, ImageTk

if getattr(sys, 'frozen', False):
    TOOLS_ROOT = sys._MEIPASS
else:
    TOOLS_ROOT = os.path.dirname(os.path.abspath(__file__))
_RAW = os.path.join(TOOLS_ROOT, 'assets', 'setup_ui_v2_working.html')
HTML_PATH = 'file:///' + _RAW.replace('\\', '/')
REQ_PATH = os.path.join(TOOLS_ROOT, 'requirements.txt')
G_SCREEN_W, G_SCREEN_H = 1920, 1080
G_HOST_PYTHON = None  # 宿主机真实 Python 路径

# ── Splash ───────────────────────────────────────────
class Splash:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.update_idletasks()

        global G_SCREEN_W, G_SCREEN_H
        G_SCREEN_W = self.root.winfo_screenwidth()
        G_SCREEN_H = self.root.winfo_screenheight()

        self.W, self.H = 490, 260
        self.root.geometry(f'{self.W}x{self.H}+'
            f'{(G_SCREEN_W-self.W)//2}+{(G_SCREEN_H-self.H)//2}')
        self.root.attributes('-alpha', 0.0)
        self.root.deiconify()

        c = tk.Canvas(self.root, width=self.W, height=self.H, bg='#fafafc', highlightthickness=0, bd=0)
        c.pack()

        # 渐变
        for i in range(self.H):
            t = i/self.H; r=int(250-8*t); g=int(250-5*t); b=int(252-2*t)
            c.create_line(0, i, self.W, i, fill=f'#{r:02x}{g:02x}{b:02x}')
        # 正弦底纹
        for y0, amp, freq, ph in [(140,30,0.018,0),(190,20,0.025,1.2)]:
            pts = []
            for x in range(-10, self.W+10, 2):
                pts.extend([x, y0+math.sin(x*freq+ph)*amp])
            c.create_line(*pts, fill='#eaeaf0', width=1, smooth=True)
        # 衬线
        c.create_rectangle(3,3,self.W-4,self.H-4, fill='', outline='#d8d8e0', width=1)

        # 图标
        png = os.path.join(TOOLS_ROOT, 'assets', 'mcupilot_iconsp.png')
        if os.path.exists(png):
            img = Image.open(png).resize((108,108), Image.LANCZOS)
            self._icon_img = ImageTk.PhotoImage(img)
            c.create_image(84, 89, image=self._icon_img, anchor='center')

        # 标题
        c.create_text(170, 42, text='McuPilot', font=('Segoe UI', 20, 'bold'),
                      fill='#1a1a24', anchor='w')
        c.create_text(170, 66, text='项目配置向导 \u00b7 系统环境审计',
                      font=('Microsoft YaHei', 8), fill='#7a7a88', anchor='w')
        c.create_line(170, 84, self.W-38, 84, fill='#e8e8ee')
        c.create_text(170, 98, text='RyanWang  \u00b7  MIT License  \u00a9 2026',
                      font=('Segoe UI', 7), fill='#b0b0ba', anchor='w')

        # 日志行
        self.logs = []; log_y = 118
        for _ in range(4):
            self.logs.append(c.create_text(170, log_y, text='', font=('Consolas', 8), fill='#888', anchor='w'))
            log_y += 14

        # 进度条
        bar_y = log_y+10; bar_h = 4
        self._bar_y = bar_y; self._bar_w = self.W-76
        track = Image.new('RGBA', (self._bar_w, bar_h), (0,0,0,0))
        tdraw = ImageDraw.Draw(track)
        tdraw.rounded_rectangle([0,0,self._bar_w-1,bar_h-1], radius=2, fill=(0xe8,0xe8,0xee,255))
        self._track_img = ImageTk.PhotoImage(track)
        c.create_image(38+self._bar_w//2, bar_y+bar_h//2, image=self._track_img)
        self._bar_img = None
        self.pct = c.create_text(self.W-40, bar_y+14, text='', font=('Consolas', 8), fill='#a0a0b0', anchor='e')

        # 按钮区
        btn_y = bar_y+30; btns_bg = '#f3f6f9'
        self.btn_frame = tk.Frame(self.root, bg=btns_bg)
        self.btn_install = tk.Label(self.btn_frame, text='安装', font=('Microsoft YaHei', 10), fg='#ea580c', bg=btns_bg, cursor='hand2')
        self.btn_exit = tk.Label(self.btn_frame, text='退出', font=('Microsoft YaHei', 10), fg='#999', bg=btns_bg, cursor='hand2')
        self.btn_download = tk.Label(self.btn_frame, text='下载Python', font=('Microsoft YaHei', 10), fg='#2563eb', bg=btns_bg, cursor='hand2')
        self.btn_browse = tk.Label(self.btn_frame, text='手动定位...', font=('Microsoft YaHei', 10), fg='#16a34a', bg=btns_bg, cursor='hand2')
        for b, hover_color in [(self.btn_install, '#d04a0a'), (self.btn_exit, '#666'),
                                (self.btn_download, '#1d4ed8'), (self.btn_browse, '#0d7a30')]:
            b._hover = hover_color
            b.bind('<Enter>', lambda e,w=b: w.config(fg=w._hover))
            b.bind('<Leave>', lambda e,w=b: w.config(fg=w._base_fg or '#999'))
        self.btn_install._base_fg = '#ea580c'; self.btn_exit._base_fg = '#999'
        self.btn_download._base_fg = '#2563eb'; self.btn_browse._base_fg = '#16a34a'
        self._btn_y = btn_y

        self.c = c
        self.root.after(10, self._fade_in)

    def _fade_in(self):
        for a in range(1,12):
            self.root.attributes('-alpha', a/11); self.root.update(); time.sleep(0.01)
        threading.Thread(target=self._check, daemon=True).start()

    def _fade_out(self):
        for a in range(11,-1,-1):
            self.root.attributes('-alpha', a/11); self.root.update(); time.sleep(0.012)

    def log(self, i, color, text):
        if self.root.winfo_exists():
            self.root.after(0, lambda: self.c.itemconfig(self.logs[i], text=text[:60], fill=color))

    def set_bar(self, pct):
        if not self.root.winfo_exists(): return
        def _do():
            fw = max(4, int(self._bar_w*pct/100))
            fill = Image.new('RGBA', (fw,4), (0,0,0,0))
            fdraw = ImageDraw.Draw(fill)
            fdraw.rounded_rectangle([0,0,fw-1,3], radius=2, fill=(0xea,0x58,0x0c,255))
            if self._bar_img: self.c.delete('bar_fill')
            self._bar_img = ImageTk.PhotoImage(fill)
            self.c.create_image(38+fw//2, self._bar_y+2, image=self._bar_img, anchor='center', tags='bar_fill')
            self.c.itemconfig(self.pct, text=f'{int(pct)}%')
        self.root.after(0, _do)

    def show_buttons(self, icb, ecb, show_install=True):
        def _do():
            self._icb=icb; self._ecb=ecb
            self.btn_exit.bind('<Button-1>', lambda e: ecb())
            self.btn_exit.pack(side='left')
            if show_install:
                self.btn_install.bind('<Button-1>', lambda e: icb())
                self.btn_install.pack(side='left', padx=(0,16))
            else:
                self.btn_install.pack_forget()
            self.c.create_window(self.W//2, self._btn_y, window=self.btn_frame)
        self.root.after(0, _do)

    def disable_btns(self):
        self.root.after(0, lambda: [self.btn_install.unbind('<Button-1>'), self.btn_exit.unbind('<Button-1>'),
            self.btn_install.config(fg='#ddd'), self.btn_exit.config(fg='#ddd')])

    def enable_btns(self):
        self.root.after(0, lambda: [self.btn_install.bind('<Button-1>', lambda e: self._icb()),
            self.btn_exit.bind('<Button-1>', lambda e: self._ecb()),
            self.btn_install.config(fg='#ea580c'), self.btn_exit.config(fg='#aaa')])

    def _check(self):
        global G_HOST_PYTHON
        self.log(0, '#555', '[System ] Auditing host environment...'); self.set_bar(15)

        # 1. 宿主机 Python 审计
        p_ok, p_ver, p_path = check_host_python()
        if p_ok:
            G_HOST_PYTHON = p_path
            self.log(0, '#16a34a', f'[Python ] System Python {p_ver}  \u2713')
        else:
            self.log(0, '#dc2626', '[Notice ] 未检测到 Python \u2265 3.10')
            self.log(1, '#ea580c', '请安装 Python 3.10+ 或手动指定 python.exe 路径')
            self.set_bar(50)
            self._show_python_actions()
            return

        # 2. 宿主机依赖审计
        self._audit_deps()

    def _audit_deps(self):
        self.log(1, '#555', '[Pip    ] Scanning host packages...'); self.set_bar(40)
        dep_ok, missing = check_host_pip_deps(G_HOST_PYTHON)
        if dep_ok:
            self.log(1, '#16a34a', '[Pip    ] \u2713')
            self.set_bar(100); time.sleep(0.3)
            self.root.after(0, self._done)
        else:
            per = 3
            for i in range(0, min(len(missing), per*4), per):
                chunk = ', '.join(missing[i:i+per])
                self.log(1+(i//per), '#ea580c', f'[Missing] {chunk}')
            self.set_bar(60)
            self.show_buttons(self._do_install, self._do_exit, show_install=True)

    # ── Python 未找到时的引导 ──────────────────────────
    def _show_python_actions(self):
        def _do():
            self.btn_install.pack_forget()
            self.btn_download.bind('<Button-1>', lambda e: self._do_download_python())
            self.btn_browse.bind('<Button-1>', lambda e: self._do_browse_python())
            self.btn_exit.bind('<Button-1>', lambda e: self._do_exit())
            self.btn_download.pack(side='left', padx=(0, 12))
            self.btn_browse.pack(side='left', padx=(0, 12))
            self.btn_exit.pack(side='left')
            self.c.create_window(self.W//2, self._btn_y, window=self.btn_frame)
        self.root.after(0, _do)

    def _do_download_python(self):
        import webbrowser
        webbrowser.open('https://www.python.org/downloads/')
        self.log(1, '#555', '安装完成后请重启 McuPilot')

    def _do_browse_python(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title='选择 Python 可执行文件 (python.exe)',
            filetypes=[('Python', 'python.exe'), ('All', '*.*')])
        if not path: return
        # 验证版本
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        try:
            r = subprocess.run([path, '-c',
                'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
                capture_output=True, text=True, timeout=5, creationflags=cflags)
            if r.returncode == 0:
                major, minor = map(int, r.stdout.strip().split('.'))
                if major == 3 and minor >= 10 or major > 3:
                    global G_HOST_PYTHON
                    G_HOST_PYTHON = path
                    self.log(0, '#16a34a', f'[Python ] User Python {major}.{minor}  \u2713')
                    self.btn_frame.pack_forget()
                    threading.Thread(target=self._audit_deps, daemon=True).start()
                    return
        except Exception: pass
        self.log(1, '#dc2626', '所选程序不是 Python \u2265 3.10，请重新选择')

    def _do_install(self):
        self.disable_btns(); self.root.after(0, lambda: self.btn_install.config(text='...'))
        self.log(1, '#ea580c', '[Pip    ] Injecting to host...'); self.set_bar(65)
        def _run():
            try:
                # 确保 pip 存在
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
                subprocess.run([G_HOST_PYTHON, '-m', 'ensurepip'],
                    capture_output=True, timeout=30, creationflags=cflags)
                r = subprocess.run([G_HOST_PYTHON, '-m', 'pip', 'install', '-r', REQ_PATH, '-q'],
                    capture_output=True, text=True, timeout=180,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
                if r.returncode == 0:
                    self.log(1, '#16a34a', '[Pip    ] Dependency install OK')
                    self.set_bar(80)
                    # 复验依赖是否真正可 import
                    dep_ok2, missing2 = check_host_pip_deps(G_HOST_PYTHON)
                    if dep_ok2:
                        self.log(2, '#16a34a', '[Verify ] All imports confirmed \u2713')
                        self.set_bar(100); time.sleep(0.4)
                        self.root.after(0, self._done)
                    else:
                        chunk = ', '.join(missing2[:6])
                        self.log(2, '#dc2626', f'[Verify ] Still missing: {chunk}')
                        self.root.after(0, lambda: self.btn_install.config(text='重试'))
                        self.enable_btns()
                else:
                    self.log(1, '#dc2626', '[Pip    ] \u2717 写入失败')
                    self.root.after(0, lambda: self.btn_install.config(text='重试'))
                    self.enable_btns()
            except Exception:
                self.log(1, '#dc2626', '[Pip    ] \u2717 网络错误')
                self.root.after(0, lambda: self.btn_install.config(text='重试'))
                self.enable_btns()
        threading.Thread(target=_run, daemon=True).start()

    def _do_exit(self):
        self._fade_out(); self.root.after(0, self.root.destroy); sys.exit(0)

    def _done(self):
        self._fade_out(); self.root.withdraw()
        self.root.quit()

# ── 宿主机逆向探测 ───────────────────────────────────
def check_host_python():
    import shlex
    cflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    for cmd_str in ['python', 'python3', 'py -3']:
        try:
            cmd_parts = shlex.split(cmd_str)
            r = subprocess.run([*cmd_parts, '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
                capture_output=True, text=True, timeout=3, creationflags=cflags)
            if r.returncode == 0:
                major, minor = map(int, r.stdout.strip().split('.'))
                if major == 3 and minor >= 10 or major > 3:
                    pr = subprocess.run([*cmd_parts, '-c', 'import sys; print(sys.executable)'],
                        capture_output=True, text=True, timeout=2, creationflags=cflags)
                    if pr.returncode == 0:
                        return True, f'{major}.{minor}', pr.stdout.strip()
        except Exception: continue
    return False, '0.0', ''

def check_host_pip_deps(host_py):
    import_map = {
        'pylink-square':'pylink','python-dotenv':'dotenv','pyyaml':'yaml',
        'pywin32':'win32com','llama-cloud':'llama_cloud','pyelftools':'elftools',
        'mcp':'mcp','filelock':'filelock','customtkinter':'customtkinter',
    }
    try:
        with open(REQ_PATH, encoding='utf-8') as f:
            reqs = [l.split('#')[0].strip().split('>=')[0].split('==')[0].strip().split('[')[0]
                    for l in f if l.strip() and not l.startswith('#')]
    except Exception:
        return True, []
    if not reqs: return True, []

    # 单次进程批量内省，避免 N 次进程创建的串行开销
    script = '\n'.join([
        'import json',
        f'import_map = {repr(import_map)}',
        f'reqs = {repr(reqs)}',
        'missing = []',
        'for pkg in reqs:',
        ' if not pkg: continue',
        ' mod = import_map.get(pkg, pkg.replace("-", "_"))',
        ' try: __import__(mod)',
        ' except ImportError: missing.append(pkg)',
        'print(json.dumps(missing))',
    ])
    cflags = subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
    try:
        r = subprocess.run([host_py, '-c', script], capture_output=True, text=True, timeout=15, creationflags=cflags)
        if r.returncode == 0:
            missing = json.loads(r.stdout.strip())
            return len(missing)==0, missing
    except Exception: pass
    return False, reqs

# ── GUI 启动 ─────────────────────────────────────────
def start_gui():
    import webview

    class Api:
        def __init__(self):
            self._steps = []
            self._done = False
            self._lock = threading.Lock()

        def browse_folder(self):
            result = window.create_file_dialog(webview.FileDialog.FOLDER)
            return result[0] if result else ""
        def check_env(self, project_path):
            from core.project_wizard import check_env
            return json.dumps(check_env(project_path), ensure_ascii=False)
        def deploy(self, project_path, params_json, clients_json):
            from core.project_wizard import deploy
            params = json.loads(params_json); clients = json.loads(clients_json)
            with self._lock:
                self._steps = []
                self._done = False

            def progress(i, s, m):
                with self._lock:
                    self._steps.append((i, s, m))

            def _run():
                deploy(project_path, params, clients, TOOLS_ROOT, progress, python_path=G_HOST_PYTHON)
                time.sleep(0.05)
                with self._lock:
                    self._done = True

            threading.Thread(target=_run, daemon=True).start()

        def poll(self):
            with self._lock:
                items = self._steps
                self._steps = []
                done_status = self._done
            return json.dumps({"steps": items, "done": done_status})

    window = webview.create_window(
        title='McuPilot — 项目配置向导',
        url=HTML_PATH,
        js_api=Api(),
        width=780, height=760,
        x=(G_SCREEN_W-780)//2, y=(G_SCREEN_H-760)//2,
        resizable=False,
    )

    webview.start(debug=False)

# ── 主入口 ───────────────────────────────────────────
if __name__ == '__main__':
    s = Splash()
    s.root.mainloop()
    start_gui()
    try: s.destroy()
    except Exception: pass
