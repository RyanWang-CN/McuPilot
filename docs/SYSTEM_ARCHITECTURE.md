# McuPilot — 系统架构

## 三层架构

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: 配置向导 (Setup Wizard)                         │
│  run_setup.py + assets/setup_ui_v2_working.html           │
│  一次性项目初始化：环境检测 → 参数定义 → 一键部署           │
│  PyWebView (WebView2) + Vue 3 + Tailwind                  │
├──────────────────────────────────────────────────────────┤
│  Layer 2: MCP 协同网关 (MCP Server)                       │
│  mcp_server.py → skills/build/ injection/ perception/     │
│  AI ↔ MCU 协议桥梁：编译 / 烧录 / HIL 热注入 / RTT 通信    │
│  FastMCP + subprocess                                     │
├──────────────────────────────────────────────────────────┤
│  Layer 3: MCU 固件底座 (Firmware Base)                    │
│  HIL/ + RTT/                                              │
│  双缓冲热注入 + SEGGER RTT 实时日志                        │
│  C (CMSIS)                                                │
└──────────────────────────────────────────────────────────┘
```

## 数据流

```
用户双击 run_setup.py
    │
    ├─ Splash (tkinter) → 检测 Python + pip
    │
    ├─ GUI (PyWebView) → 选工程 / 填参数 / 一键部署
    │   │
    │   ├─ gen_hil_header()      → HIL/hil_config_user.h
    │   ├─ copy_hil_rtt()        → 复制固件底座到工程
    │   ├─ inject_keil_xml()     → 注册 .c 文件 + include 路径
    │   ├─ compile_project()     → UV4.exe 命令行编译
    │   ├─ parse_symbols()       → 生成 .hil_symbols.json
    │   └─ register_mcp()        → 写入 .claude/claude.json 等
    │
    └─ 完成 → 用户打开 AI 客户端即可操控单片机
```

## 日常使用流

```
AI 客户端 (Claude Code / Roo Code / Codex)
    │
    │ MCP 协议
    ▼
mcp_server.py
    │
    ├── build_project      → UV4.exe -b
    ├── flash_project      → UV4.exe -f
    ├── inject_hil_params  → J-Link 热注入
    ├── read_hil_variable  → J-Link 读内存
    ├── rtt_print / rtt_ask → RTT 通信
    └── check_mcu_status   → CPU 状态
    │
    ▼
HC32 MCU (J-Link SWD)
```
