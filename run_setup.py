"""McuPilot Setup — 启动检测 + PyWebView GUI"""
import os, sys, json, threading, subprocess, time, tkinter as tk

TOOLS_ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(TOOLS_ROOT, 'assets', 'setup_ui_v2_working.html')
REQ_PATH = os.path.join(TOOLS_ROOT, 'requirements.txt')

# ── Splash 窗口 ──────────────────────────────────────
def show_splash():
    root = tk.Tk()
    root.overrideredirect(True)
    W, H = 400, 220
    cx, cy = (root.winfo_screenwidth()-W)//2, (root.winfo_screenheight()-H)//2
    root.geometry(f"{W}x{H}+{cx}+{cy}")
    root.attributes('-alpha', 0.0)

    c = tk.Canvas(root, width=W, height=H, bg="#0e0e14", highlightthickness=0, bd=0)
    c.pack()

    # 背景渐变
    for i in range(H):
        t = i / H
        r = int(14 + 8 * t)
        g = int(14 + 6 * t)
        b = int(20 + 10 * t)
        c.create_line(0, i, W, i, fill=f'#{r:02x}{g:02x}{b:02x}')

    # 顶部细线
    c.create_line(0, 0, W, 0, fill="#6366f1", width=1)

    # 标题 — 中文
    c.create_text(W/2, 58, text="McuPilot", font=("Segoe UI", 20, "bold"),
                  fill="#f0f0f5")
    c.create_text(W/2, 84, text="单片机 AI 自动化配置向导", font=("Microsoft YaHei", 9),
                  fill="#9b9bb0")

    # 英文副标题
    c.create_text(W/2, 108, text="by RyanWang", font=("Segoe UI", 8, "italic"),
                  fill="#5c5c78")

    # 分割线
    c.create_line(60, 136, W-60, 136, fill="#2a2a3e", width=1)

    # 加载状态
    status = c.create_text(W/2, 165, text="正在启动...", font=("Microsoft YaHei", 9),
                           fill="#70708a")

    # 底部加载提示
    sub = c.create_text(W/2, 186, text="Starting up...", font=("Segoe UI", 7),
                        fill="#4a4a68")

    for a in range(1, 11):
        root.attributes('-alpha', a/10); root.update(); time.sleep(0.012)

    return root, c, status, sub

def _up(c, item, sub, text, color):
    c.itemconfig(item, text=text, fill=color)
    c.itemconfig(sub, text="")
    c.update()

# ── 检测逻辑 ─────────────────────────────────────────
def check_python():
    """检查 Python >= 3.10。返回 (ok, version_str)"""
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 10
    return ok, f"{v.major}.{v.minor}.{v.micro}"

def check_pip_deps():
    """检查 requirements.txt 中的依赖是否都已安装。返回 (ok, missing_list)"""
    missing = []
    try:
        with open(REQ_PATH, encoding='utf-8') as f:
            reqs = [line.split('#')[0].strip().split('>=')[0].split('==')[0].strip()
                    for line in f if line.strip() and not line.startswith('#')]
    except:
        return True, []  # 找不到 requirements.txt 就不检查

    for pkg in reqs:
        if not pkg: continue
        try:
            __import__(pkg.replace('-', '_').split('[')[0])
        except ImportError:
            missing.append(pkg)
    return len(missing) == 0, missing

def install_deps():
    """pip install -r requirements.txt"""
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQ_PATH, "-q"],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except: return False

# ── 主入口 ───────────────────────────────────────────
if __name__ == '__main__':
    root, c, status, sub = show_splash()
    passed = True

    time.sleep(0.3)
    p_ok, p_ver = check_python()
    if not p_ok:
        _up(c, status, sub, f"需要 Python ≥ 3.10（当前 {p_ver}）", "#f87171")
        passed = False

    dep_ok, missing = check_pip_deps()
    if not dep_ok:
        _up(c, status, sub, f"安装缺失依赖...", "#9090b0")
        if install_deps():
            _up(c, status, sub, "依赖就绪", "#34c759")
        else:
            _up(c, status, sub, "依赖安装失败", "#f87171")
            passed = False

    if passed:
        _up(c, status, sub, "启动完成", "#34c759")
        time.sleep(0.5)
        for a in range(10, -1, -1):
            root.attributes('-alpha', a/10); root.update(); time.sleep(0.012)
        root.destroy()

        import webview
        from core import project_wizard as _pw  # noqa: already imported

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
                params = json.loads(params_json)
                clients = json.loads(clients_json)

                def progress(step_idx, status, msg):
                    js = f"onStepUpdate({step_idx}, '{status}', {json.dumps(msg, ensure_ascii=False)})"
                    webview.windows[0].evaluate_js(js)

                threading.Thread(target=deploy,
                    args=(project_path, params, clients, TOOLS_ROOT, progress), daemon=True).start()

        window = webview.create_window(
            title='McuPilot — 项目配置向导',
            url='file://' + HTML_PATH,
            js_api=Api(),
            width=780, height=760,
            resizable=False,
        )
        webview.start(debug=False)
    else:
        _up(c, status, sub, "请修复上述问题后重试", "#f87171")
        c.create_window(200, 200, window=tk.Button(root, text="关闭",
            command=root.destroy, font=("Microsoft YaHei", 8),
            bg="#2a2a3e", fg="#a0a0c0", border=0, padx=14, pady=2))
        root.mainloop()
