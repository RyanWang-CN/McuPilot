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
│  AI ↔ MCU 协议桥梁：编译 / 烧录 / HIL 热注入 / RTT 采集    │
│  FastMCP + subprocess                                     │
├──────────────────────────────────────────────────────────┤
│  Layer 3: MCU 固件底座 (Firmware Base)                    │
│  HIL/ + RTT/                                              │
│  双缓冲热注入 + SEGGER RTT 实时日志                        │
│  C (CMSIS)                                                │
└──────────────────────────────────────────────────────────┘
```

## 部署数据流

```
用户双击 McuPilot.exe (或 run_setup.py)
    │
    ├─ Splash (tkinter) → 检测 Python + pip
    │
    ├─ GUI (PyWebView) → 选工程 / 填参数 / 一键部署
    │   │
    │   ├─ gen_hil_header()      → HIL/hil_config_user.h
    │   ├─ copy_hil_rtt()        → 复制固件底座到工程
    │   ├─ inject_keil_xml()     → 注册 .c/.h 到 Keil + include 路径
    │   ├─ inject_main_c()       → 自动注入 HIL 代码到 main.c
    │   ├─ compile_project()     → UV4.exe 命令行编译
    │   ├─ parse_symbols()       → 生成 .hil_symbols.json
    │   └─ register_mcp()        → 写入 AI 客户端 MCP 配置
    │
    └─ 完成 → 用户打开 AI 客户端即可操控单片机
```

## 日常使用流

```
AI 客户端 (Claude Code / Cline / Codex)
    │
    │ MCP 协议 (22 个工具)
    ▼
mcp_server.py
    │
    ├── init_project_config        → 嗅探工程生成 YAML
    ├── update_hil_dictionary      → 解析 .map/.axf 生成字典
    ├── build_project              → UV4.exe -b 编译
    ├── flash_project              → UV4.exe -f 烧录
    ├── hard_reset_mcu             → 硬复位
    ├── rtt_print / rtt_ask        → RTT 文本通信
    ├── rtt_capture                → RTT 二进制采集 (三种模式)
    ├── inject_hil_parameters      → J-Link 热修参数
    ├── read_hil_variable          → J-Link 读内存
    ├── check_mcu_status           → CPU 状态诊断
    ├── get_hardware_probe_info    → 探针/电压诊断
    ├── scan_connected_probes      → 扫描 J-Link 串号
    ├── check_rtt_health           → RTT 通道检测
    ├── debug_halt / run / step    → 调试控制
    ├── debug_set_breakpoint       → 设断点 (符号名/地址)
    ├── debug_clear_breakpoint     → 清断点
    ├── debug_clear_all_breakpoints→ 清全部断点
    └── debug_run_to_breakpoint    → 断点狙击
    │
    ▼
HC32 MCU (J-Link SWD)
```
