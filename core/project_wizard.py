#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""McuPilot Setup — 后端逻辑（环境检测 + 部署编排）"""
import os, sys, subprocess, json, shutil, glob, winreg, xml.etree.ElementTree as ET

# ---- 环境检测 ----

def detect_keil():
    """返回 (found: bool, path: str)"""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Keil\Products\MDK")
        d, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)
        p = os.path.join(d, "UV4", "UV4.exe")
        if os.path.exists(p): return True, p
    except: pass
    for p in [
        os.path.expandvars(r"%LOCALAPPDATA%\Keil_v5\UV4\UV4.exe"),
        r"C:\Keil_v5\UV4\UV4.exe", r"D:\Keil_v5\UV4\UV4.exe"
    ]:
        if os.path.exists(p): return True, p
    return False, ""

def detect_jlink():
    """返回 (found: bool, sn: str, voltage: str)"""
    try:
        from pylink import JLink
        jlk = JLink()
        emulators = jlk.connected_emulators()
        if emulators:
            info = emulators[0]
            sn = getattr(info, 'SerialNumber', str(info))
            try:
                jlk.open()
                hw = jlk.hardware_status
                v = getattr(hw, 'VTarget', 0)
                jlk.close()
                vt = f"{v/1000:.2f}V" if v else ""
                return True, str(sn), vt
            except:
                return True, str(sn), ""
    except: pass
    return False, "", ""

def detect_mcu(project_path):
    """从 .uvprojx 解析芯片型号。返回 device_name 或 None"""
    try:
        for f in glob.glob(os.path.join(project_path, "*.uvprojx")):
            tree = ET.parse(f)
            for e in tree.iter('Device'):
                if e.text: return e.text.strip()
    except: pass
    return None

def check_env(project_path):
    """一次性检测全部环境"""
    mcu = detect_mcu(project_path)
    keil_ok, keil_path = detect_keil()
    jl_ok, jl_sn, jl_v = detect_jlink()
    return {
        "chip": ("ok" if mcu else "err"), "chip_val": mcu or "",
        "keil": ("ok" if keil_ok else "err"), "keil_val": keil_path,
        "jlink": ("ok" if jl_ok else "err"), "jlink_val": f"SN {jl_sn}\u2002\u2002{jl_v}" if jl_ok else "",
    }

# ---- 文件操作 ----

def gen_hil_header(project_path, params):
    """根据参数表生成 hil_config_user.h"""
    # params = [{name, type, value}, ...]
    types_ordered = sorted(params, key=lambda x: _type_size(x["type"]), reverse=True)
    fields = []
    offset = 0
    for p in types_ordered:
        sz = _type_size(p["type"])
        fields.append(f"    {p['type']:12s} {p['name']};")
        offset += sz
    # 自动加 _pad 填充到 4 字节对齐
    if offset % 4:
        pad_bytes = 4 - (offset % 4)
        if pad_bytes == 1: fields.append("    uint8_t   _pad;")
        elif pad_bytes == 2: fields.append("    uint16_t  _pad;")
        elif pad_bytes == 3: fields.append("    uint8_t   _pad[3];")
    fields_str = "\n".join(fields)

    content = f'''#ifndef HIL_CONFIG_USER_H
#define HIL_CONFIG_USER_H

#include <stdint.h>

#if defined(__GNUC__) || defined(__ARMCC_VERSION) || defined(__CC_ARM)
    #define HIL_ALIGNED(x)  __attribute__((aligned(x)))
#else
    #define HIL_ALIGNED(x)
#endif

typedef struct HIL_ALIGNED(4) {{
{fields_str}
}} User_Params_t;

typedef struct {{
    User_Params_t user;
}} HIL_Global_Params_t;

#ifdef __cplusplus
extern "C" {{
#endif

extern volatile HIL_Global_Params_t g_hil_buf[2];
extern volatile uint8_t        g_config_version;
extern volatile uint8_t        g_active_idx;

#ifdef __cplusplus
}}
#endif

#define HIL_GET_ACTIVE_CFG()    ((volatile HIL_Global_Params_t*)&g_hil_buf[g_active_idx])
#define HIL_CFG_A               ((volatile void*)&g_hil_buf[0])
#define HIL_CFG_B               ((volatile void*)&g_hil_buf[1])
#define HIL_CFG_SIZE            ((uint16_t)sizeof(HIL_Global_Params_t))
#define HIL_P_VER               (&g_config_version)
#define HIL_P_IDX               (&g_active_idx)

#define HIL_WHITELIST __attribute__((used, section(".hil_expose")))

#endif /* HIL_CONFIG_USER_H */
'''
    dst = os.path.join(project_path, "HIL", "hil_config_user.h")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)

def copy_hil_rtt(tools_root, project_path):
    """复制 HIL/ 和 RTT/ 到工程目录"""
    for folder in ["HIL", "RTT"]:
        src = os.path.join(tools_root, folder)
        dst = os.path.join(project_path, folder)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

def inject_keil_com(project_path):
    """通过 COM 将 HIL/RTT 文件注入 Keil 工程。返回 (ok, msg)"""
    try:
        import win32com.client
        proj_file = glob.glob(os.path.join(project_path, "*.uvprojx"))[0]
        proj_name = os.path.basename(proj_file)
        # 尝试多种 COM ProgID
        uv = None
        for progid in ["uVision5.Application", "uVision4.Application", "Uv5.Application"]:
            try:
                uv = win32com.client.Dispatch(progid)
                break
            except: continue
        if not uv:
            return False, "Keil COM 不可用，请手动将 HIL/RTT 文件拖入 Keil 工程树"

        uv.Visible = False
        uv.OpenProject(proj_file)
        proj = uv.ActiveProject

        hil_files = glob.glob(os.path.join(project_path, "HIL", "*.c"))
        rtt_files = glob.glob(os.path.join(project_path, "RTT", "*.c"))
        for f in hil_files:
            try: proj.AddFile(f, "HIL")
            except: pass
        for f in rtt_files:
            try: proj.AddFile(f, "RTT")
            except: pass

        proj.Save()
        uv.Quit()
        return True, "OK"
    except Exception as e:
        return False, f"COM 注入失败: {str(e)[:60]}"

def _type_size(t):
    m = {"uint8_t":1,"int8_t":1,"uint16_t":2,"int16_t":2,"uint32_t":4,"int32_t":4,"float":4}
    return m.get(t, 4)

# ---- 编译 & 解析 ----

def _run_py_module(module, cwd, tools_root, args=None):
    """启动 Python 子进程运行模块"""
    cmd = [sys.executable or "python", "-u", "-m", module]
    if args: cmd.extend(args)
    env = os.environ.copy()
    env["PYTHONPATH"] = tools_root
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
            text=True, timeout=150, creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0, (r.stdout or r.stderr)[:500]
    except subprocess.TimeoutExpired:
        return False, "超时 (150s)"
    except Exception as e:
        return False, str(e)[:100]

def compile_project(project_path, tools_root):
    """先跑 auto_config_builder 生成 yaml，再编译。返回 (ok, msg)"""
    ok1, msg1 = _run_py_module("core.auto_config_builder", project_path, tools_root)
    if not ok1:
        return False, f"配置生成失败: {msg1[:100]}"
    ok2, msg2 = _run_py_module("skills.build.compile_auto", project_path, tools_root)
    if not ok2:
        return False, f"编译失败: {msg2[:200]}"
    # 从输出中提取错误/警告数
    import re
    try:
        data = json.loads(msg2) if msg2.strip().startswith("{") else {}
    except: data = {}
    errors = data.get("errors", 0)
    warnings = data.get("warnings", 0)
    return True, f"编译通过 ({errors} errors, {warnings} warnings)"

def parse_symbols(project_path, tools_root):
    """运行 hil_parser 生成 .hil_symbols.json。返回 (ok, msg)"""
    ok, msg = _run_py_module("core.hil_parser", project_path, tools_root)
    if not ok: return False, f"解析失败: {msg[:100]}"
    # 统计符号数
    sym_file = os.path.join(project_path, ".hil_symbols.json")
    count = 0
    if os.path.exists(sym_file):
        try:
            with open(sym_file, encoding="utf-8") as f:
                data = json.load(f)
                count = len([k for k in data if not k.startswith("__")])
        except: pass
    return True, f"解析出 {count} 个符号"

# ---- MCP 注册 ----

def register_mcp(project_path, clients, tools_root):
    """注册 MCP Server 到所选 AI 客户端"""
    mcp_path = os.path.join(tools_root, "mcp_server.py")
    mcp_config = {
        "mcpServers": {
            "mcupilot": {
                "command": sys.executable or "python",
                "args": [mcp_path],
            }
        }
    }
    results = []
    for client in clients:
        if client == "Claude Code":
            path = os.path.expandvars(r"%USERPROFILE%\.claude\claude.json")
            results.append(_write_json(path, mcp_config))
        elif client == "Roo Code":
            path = os.path.join(project_path, ".vscode", "mcp.json")
            results.append(_write_json(path, mcp_config))
        elif client == "Codex CLI":
            path = os.path.expandvars(r"%USERPROFILE%\.codex\config.toml")
            results.append(_write_codex_toml(path, mcp_path))
    ok = all(r[0] for r in results)
    msg = ", ".join(r[1] for r in results)
    return ok, msg

def _write_json(path, new_cfg):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        if "mcpServers" in existing:
            existing["mcpServers"].update(new_cfg["mcpServers"])
        else:
            existing.update(new_cfg)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        return True, os.path.basename(os.path.dirname(path))
    except Exception as e:
        return False, str(e)[:40]

def _write_codex_toml(path, mcp_path):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = f.read()
        entry = f'\n[[mcp_servers]]\nname = "mcupilot"\ncommand = "{sys.executable}"\nargs = ["{mcp_path}"]\n'
        with open(path, "w", encoding="utf-8") as f:
            f.write(existing + entry)
        return True, "codex"
    except Exception as e:
        return False, str(e)[:40]

# ---- 部署编排 ----
# progress_callback(step_idx, status, msg)  # step_idx: 0-5, status: "busy"|"done"|"err"|"skip"

def deploy(project_path, params, clients, tools_root, progress):
    """完整部署流程，逐步回调 progress"""
    # ① 生成 hil_config_user.h
    progress(0, "busy", "")
    try:
        gen_hil_header(project_path, params)
        progress(0, "done", "已生成 hil_config_user.h 结构体头文件")
    except Exception as e:
        progress(0, "err", str(e)[:80])

    # ② 复制 HIL/RTT
    progress(1, "busy", "")
    try:
        copy_hil_rtt(tools_root, project_path)
        progress(1, "done", "已复制 HIL/RTT 文件夹到目标工程")
    except Exception as e:
        progress(1, "err", str(e)[:80])

    # ③ COM 注入
    progress(2, "busy", "")
    ok, msg = inject_keil_com(project_path)
    progress(2, "done" if ok else "err", msg)

    # ④ 编译
    if ok or True:  # COM 失败也继续编译（用户可能手动加了文件）
        progress(3, "busy", "")
        ok3, msg3 = compile_project(project_path, tools_root)
        progress(3, "done" if ok3 else "err", msg3)
    else:
        progress(3, "skip", "注入失败，编译跳过")

    # ⑤ 解析
    if ok3:
        progress(4, "busy", "")
        ok4, msg4 = parse_symbols(project_path, tools_root)
        progress(4, "done" if ok4 else "err", msg4)
    else:
        progress(4, "skip", "无编译产物，解析跳过")

    # ⑥ 注册 MCP
    progress(5, "busy", "")
    ok5, msg5 = register_mcp(project_path, clients, tools_root)
    progress(5, "done" if ok5 else "err", msg5)
