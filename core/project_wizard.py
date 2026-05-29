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

def inject_keil_xml(project_path):
    """通过 XML 将 HIL/RTT 文件注入 Keil 工程。返回 (ok, msg)"""
    import shutil, xml.etree.ElementTree as ET
    try:
        proj_files = glob.glob(os.path.join(project_path, "*.uvprojx"))
        if not proj_files:
            return False, "未找到 .uvprojx 工程文件"
        proj_file = proj_files[0]

        # 备份
        bak = proj_file + ".mcupilot.bak"
        if not os.path.exists(bak):
            shutil.copy2(proj_file, bak)

        tree = ET.parse(proj_file)
        root = tree.getroot()

        # 找到 <Targets>/<Target>/<Groups>
        groups = root.find("Targets/Target/Groups")
        if groups is None:
            # 兼容 Keil v4/v5 不同结构
            groups = root.find(".//Groups")
        if groups is None:
            return False, "XML 结构异常：找不到 Groups 节点"

        # 检查已存在的组名，防重复
        existing = {g.findtext("GroupName", "") for g in groups.findall("Group")}
        proj_dir = project_path

        # HIL 组
        if "HIL" not in existing:
            g_hil = ET.SubElement(groups, "Group")
            ET.SubElement(g_hil, "GroupName").text = "HIL"
            f_hil = ET.SubElement(g_hil, "Files")
            for fc in glob.glob(os.path.join(proj_dir, "HIL", "*.c")):
                if os.path.basename(fc) == "example_main.c":
                    continue
                fe = ET.SubElement(f_hil, "File")
                ET.SubElement(fe, "FileName").text = os.path.basename(fc)
                ET.SubElement(fe, "FileType").text = "1"
                ET.SubElement(fe, "FilePath").text = "./HIL/" + os.path.basename(fc)
            # 只注入用户配置头文件（其他 .h 通过 include 路径找到）
            hcfg = os.path.join(proj_dir, "HIL", "hil_config_user.h")
            if os.path.exists(hcfg):
                fe = ET.SubElement(f_hil, "File")
                ET.SubElement(fe, "FileName").text = "hil_config_user.h"
                ET.SubElement(fe, "FileType").text = "5"
                ET.SubElement(fe, "FilePath").text = "./HIL/hil_config_user.h"

        # RTT 组
        if "RTT" not in existing:
            g_rtt = ET.SubElement(groups, "Group")
            ET.SubElement(g_rtt, "GroupName").text = "RTT"
            f_rtt = ET.SubElement(g_rtt, "Files")
            for fc in glob.glob(os.path.join(proj_dir, "RTT", "*.c")):
                fe = ET.SubElement(f_rtt, "File")
                ET.SubElement(fe, "FileName").text = os.path.basename(fc)
                ET.SubElement(fe, "FileType").text = "1"
                ET.SubElement(fe, "FilePath").text = "./RTT/" + os.path.basename(fc)
            for fh in glob.glob(os.path.join(proj_dir, "RTT", "*.h")):
                fe = ET.SubElement(f_rtt, "File")
                ET.SubElement(fe, "FileName").text = os.path.basename(fh)
                ET.SubElement(fe, "FileType").text = "5"
                ET.SubElement(fe, "FilePath").text = "./RTT/" + os.path.basename(fh)

        # 追加 include 路径（只改 C 编译器第一个非空 IncludePath，防重复）
        for inc in root.iter("IncludePath"):
            if inc.text and inc.text.strip():
                txt = inc.text.strip().rstrip(";")
                parts = [p.strip() for p in txt.split(";")]
                for d in ["./HIL", "./RTT"]:
                    if d not in parts:
                        txt += ";" + d
                        parts.append(d)
                inc.text = txt
                break

        tree.write(proj_file, encoding="utf-8", xml_declaration=True)
        added = []
        if "HIL" not in existing: added.append("HIL")
        if "RTT" not in existing: added.append("RTT")
        return (True, f"已注入 {'+'.join(added)} 到 Keil 工程") if added else (True, "HIL/RTT 已存在，跳过")
    except Exception as e:
        return False, f"XML 注入失败: {str(e)[:60]}"

def _type_size(t):
    m = {"uint8_t":1,"int8_t":1,"uint16_t":2,"int16_t":2,"uint32_t":4,"int32_t":4,"float":4}
    return m.get(t, 4)

# ---- main.c 自动注入 ----

RTOS_KEYWORDS = ['vTaskStartScheduler', 'xTaskCreate', 'OSStart', 'OSTaskCreate',
                 'rt_thread_startup', 'rt_system_scheduler_start', 'schedule']

HIL_INIT_SNIPPET = '''    HIL_InjectConfig_t hil_cfg = {
        .buf_a        = HIL_CFG_A,
        .buf_b        = HIL_CFG_B,
        .buf_size     = HIL_CFG_SIZE,
        .p_version    = HIL_P_VER,
        .p_active_idx = HIL_P_IDX,
    };
    HIL_Inject_Init(&hil_cfg);
'''

HIL_TASK_SNIPPET = '        HIL_Inject_Task();'

def inject_main_c(project_path):
    """自动修改 main.c：加入 HIL 初始化代码。返回 (ok, msg)"""
    import re, shutil
    # 1. 找 main 函数所在的 .c 文件
    main_file = None
    search_root = os.path.join(project_path, "..")
    for cfile in glob.glob(os.path.join(search_root, "**", "*.c"), recursive=True):
        # 跳过 HIL/RTT 目录
        if 'HIL' in cfile.replace(os.sep, '/').split('/') or \
           'RTT' in cfile.replace(os.sep, '/').split('/'):
            continue
        try:
            with open(cfile, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            continue
        # 找 main 函数签名（不在注释、不在字符串内的）
        if re.search(r'\bmain\s*\(', content):
            main_file = cfile
            break
    if not main_file:
        return False, "未找到 main.c，请手动添加 HIL 代码"

    with open(main_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # 2. 幂等性检查
    if 'HIL_Inject_Init' in content:
        return True, "HIL 代码已存在，跳过"

    # 3. RTOS 检测
    for kw in RTOS_KEYWORDS:
        if kw in content:
            return False, f"检测到 RTOS ({kw})，请手动将 HIL 代码加入主任务"

    # 4. 轻量括号栈：定位 main 函数体范围
    m = re.search(r'\bmain\s*\(', content)
    if not m:
        return False, "无法定位 main 函数签名"
    main_start = m.start()
    # 从签名的 { 开始计括号层级
    brace_start = content.find('{', m.end())
    if brace_start == -1:
        return False, "main 函数体缺失 {"

    depth = 0
    main_body_end = -1
    for i in range(brace_start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                main_body_end = i
                break
    if main_body_end == -1:
        return False, "括号不匹配，无法定位 main 函数体结束位置"

    # 5. 在 main 一层（depth=1）中找 while(1) 或 for(;;)
    main_body = content[brace_start:main_body_end + 1]
    depth = 0
    loop_anchor = -1
    loop_open_brace = -1
    i = 0
    while i < len(main_body):
        ch = main_body[i]
        if ch == '{':
            depth += 1
            i += 1
            continue
        elif ch == '}':
            depth -= 1
            i += 1
            continue
        if depth == 1:
            rest = main_body[i:i + 100]
            mw = re.match(r'(while\s*\(.+?\)|for\s*\(.*?\))', rest)
            if mw:
                loop_anchor = brace_start + i + mw.end()
                j = i + mw.end()
                while j < len(main_body):
                    if main_body[j] == '{':
                        loop_open_brace = brace_start + j
                        break
                    elif main_body[j] not in ' \t\n\r':
                        break
                    j += 1
                if loop_open_brace > 0:
                    break
        i += 1

    if loop_anchor == -1 or loop_open_brace == -1:
        return False, "未找到裸机主循环，请手动添加 HIL_Inject_Task()"

    # 6. 执行插入
    bak = main_file + ".mcupilot.bak"
    if not os.path.exists(bak):
        shutil.copy2(main_file, bak)

    globals_block = (
        'volatile HIL_Global_Params_t HIL_WHITELIST g_hil_buf[2] HIL_ALIGNED(4);\n'
        'volatile uint8_t HIL_WHITELIST g_config_version;\n'
        'volatile uint8_t HIL_WHITELIST g_active_idx;\n'
    )
    include_block = '#include "hil_config_user.h"\n#include "hil_inject.h"\n\n'

    # 避免 #ifdef 陷阱：直接以 main 函数所在行为锚点，插在它上方
    main_line_start = content.rfind('\n', 0, main_start)
    if main_line_start == -1:
        main_line_start = 0
    else:
        main_line_start += 1
    content = content[:main_line_start] + include_block + globals_block + content[main_line_start:]

    # 重建位置信息（因为 content 已被修改）
    m2 = re.search(r'\bmain\s*\(', content)
    if not m2:
        return False, "插入后无法定位 main"
    brace_start2 = content.find('{', m2.end())
    main_body2 = content[brace_start2:]
    depth = 0
    loop_anchor2 = -1
    loop_open_brace2 = -1
    i = 0
    while i < len(main_body2):
        ch = main_body2[i]
        if ch == '{':
            depth += 1
            i += 1
            continue
        elif ch == '}':
            depth -= 1
            i += 1
            continue
        if depth == 1:
            rest = main_body2[i:i + 100]
            mw = re.match(r'(while\s*\(.+?\)|for\s*\(.*?\))', rest)
            if mw:
                loop_anchor2 = brace_start2 + i + mw.end()
                j = i + mw.end()
                while j < len(main_body2):
                    if main_body2[j] == '{':
                        loop_open_brace2 = brace_start2 + j
                        break
                    elif main_body2[j] not in ' \t\n\r':
                        break
                    j += 1
                if loop_open_brace2 > 0:
                    break
        i += 1

    # 插入 HIL_Init 在循环上方
    if loop_anchor2 > 0:
        line_start = content.rfind('\n', 0, loop_anchor2) + 1
        content = (content[:line_start] + HIL_INIT_SNIPPET + '\n' +
                   content[line_start:])
        loop_open_brace2 += len(HIL_INIT_SNIPPET) + 1

    # 插入 HIL_Inject_Task 在循环体第一个 { 后
    if loop_open_brace2 > 0:
        content = (content[:loop_open_brace2 + 1] + '\n' +
                   HIL_TASK_SNIPPET +
                   content[loop_open_brace2 + 1:])

    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return True, "已自动注入 HIL 代码到 " + os.path.basename(main_file)

# ---- 编译 & 解析 ----

def _run_py_module(module, cwd, tools_root, args=None, python_path=None):
    """启动 Python 子进程运行模块"""
    py = python_path or sys.executable or 'python'
    cmd = [py, "-u", "-m", module]
    if args: cmd.extend(args)
    env = os.environ.copy()
    env["PYTHONPATH"] = tools_root
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
            encoding='utf-8', errors='replace', text=True, timeout=150,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0, (r.stdout or r.stderr)[:500]
    except subprocess.TimeoutExpired:
        return False, "超时 (150s)"
    except Exception as e:
        return False, str(e)[:100]

def _ensure_hex_output(project_path):
    """确保 Keil 工程启用 CreateHexFile，若未启用则自动开启"""
    import xml.etree.ElementTree as ET
    for uv in glob.glob(os.path.join(project_path, "*.uvprojx")):
        try:
            tree = ET.parse(uv)
            changed = False
            for e in tree.iter('CreateHexFile'):
                if e.text and e.text.strip() == '0':
                    e.text = '1'
                    changed = True
            if changed:
                tree.write(uv, encoding="utf-8", xml_declaration=True)
                return True
        except Exception:
            pass
    return False

def compile_project(project_path, tools_root, python_path=None):
    """先跑 auto_config_builder 生成 yaml，再编译。返回 (ok, msg)"""
    ok1, msg1 = _run_py_module("core.auto_config_builder", project_path, tools_root, python_path=python_path)
    if not ok1:
        return False, f"配置生成失败: {msg1[:100]}"
    hex_fixed = _ensure_hex_output(project_path)
    ok2, msg2 = _run_py_module("skills.build.compile_auto", project_path, tools_root, python_path=python_path)
    if not ok2:
        return False, f"编译失败: {msg2[:200]}"
    # 从 stdout 中提取 JSON（stderr 可能混入了编码乱码）
    import re
    match = re.search(r'\{.*"status".*\}', msg2, re.DOTALL)
    try:
        data = json.loads(match.group()) if match else {}
    except: data = {}
    errors = data.get("errors", 0)
    warnings = data.get("warnings", 0)
    if errors > 0:
        return False, f"编译有 {errors} 个错误 ({warnings} warnings)"
    msg = f"编译通过 ({errors} errors, {warnings} warnings)"
    if hex_fixed:
        msg += "；已自动启用 Hex 输出"
    # 编译后更新 YAML 补上 hex 路径
    try:
        import yaml as _yaml
        hex_files = glob.glob(os.path.join(project_path, "output", "**", "*.hex"), recursive=True)
        if not hex_files:
            hex_files = glob.glob(os.path.join(project_path, "build", "**", "*.hex"), recursive=True)
        if not hex_files:
            hex_files = glob.glob(os.path.join(project_path, "Objects", "*.hex"))
        if hex_files:
            hex_path = f"./{os.path.relpath(max(hex_files, key=os.path.getmtime), project_path).replace(os.sep, '/')}"
            yaml_path = os.path.join(project_path, "project_config.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, encoding="utf-8") as f:
                    cfg = _yaml.safe_load(f) or {}
                cfg.setdefault("paths", {})["hex_output"] = hex_path
                with open(yaml_path, "w", encoding="utf-8") as f:
                    _yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except Exception:
        pass
    return True, msg

def parse_symbols(project_path, tools_root, python_path=None):
    """运行 hil_parser 生成 .hil_symbols.json。返回 (ok, msg)"""
    ok, msg = _run_py_module("core.hil_parser", project_path, tools_root, python_path=python_path)
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

def register_mcp(project_path, clients, tools_root, python_path=None):
    """注册 MCP Server 到所选 AI 客户端"""
    if getattr(sys, 'frozen', False):
        mcp_path = os.path.join(os.path.dirname(sys.executable), '_internal', 'mcp_server.py')
    else:
        mcp_path = os.path.join(tools_root, "mcp_server.py")
    mcp_cmd = python_path or sys.executable or "python"
    mcp_config = {
        "mcpServers": {
            "mcupilot": {
                "command": mcp_cmd,
                "args": [mcp_path, "--project", os.path.abspath(project_path)],
            }
        }
    }
    results = []
    for client in clients:
        if client == "Claude Code":
            path = os.path.expandvars(r"%USERPROFILE%\.claude\claude.json")
            results.append(_write_json(path, mcp_config))
        elif client == "Cline":
            path = os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json")
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

def deploy(project_path, params, clients, tools_root, progress, python_path=None):
    """完整部署流程，逐步回调 progress"""
    # ① 生成 hil_config_user.h（写入 tools_root/HIL，随下一步复制到工程）
    progress(0, "busy", "")
    try:
        gen_hil_header(tools_root, params)
        progress(0, "done", "已生成 hil_config_user.h 结构体头文件")
    except Exception as e:
        progress(0, "err", str(e)[:80])

    # ② 复制 HIL/RTT 到工程
    progress(1, "busy", "")
    try:
        copy_hil_rtt(tools_root, project_path)
        progress(1, "done", "已复制 HIL/RTT 文件夹到目标工程")
    except Exception as e:
        progress(1, "err", str(e)[:80])

    # ③ COM 注入 + main.c 自动适配
    progress(2, "busy", "")
    ok_xml, msg_xml = inject_keil_xml(project_path)
    ok_main, msg_main = inject_main_c(project_path)
    if ok_xml and ok_main:
        progress(2, "done", "已注入 Keil 工程并自动适配 main.c")
    elif ok_xml:
        progress(2, "done", f"已注入 Keil 工程；main.c: {msg_main}")
    elif ok_main:
        progress(2, "err", f"XML 注入失败: {msg_xml}")
    else:
        progress(2, "warn", f"XML: {msg_xml}；main.c: {msg_main}")

    # ④ 编译
    if ok_xml or True:  # COM 失败也继续编译（用户可能手动加了文件）
        progress(3, "busy", "")
        ok3, msg3 = compile_project(project_path, tools_root, python_path=python_path)
        progress(3, "done" if ok3 else "err", msg3)
    else:
        progress(3, "skip", "注入失败，编译跳过")

    # ⑤ 解析
    if ok3:
        progress(4, "busy", "")
        ok4, msg4 = parse_symbols(project_path, tools_root, python_path=python_path)
        progress(4, "done" if ok4 else "err", msg4)
    else:
        progress(4, "skip", "无编译产物，解析跳过")

    # ⑥ 注册 MCP
    progress(5, "busy", "")
    ok5, msg5 = register_mcp(project_path, clients, tools_root, python_path=python_path)
    progress(5, "done" if ok5 else "err", msg5)
