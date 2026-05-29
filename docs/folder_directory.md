.\                            <-- 【工具链根目录】McuPilot 单片机 AI 协同开发工具链
│
├── run_setup.py                 <-- [配置向导入口] 双击启动，Splash + 环境检测 + GUI 部署
├── mcp_server.py                <-- [AI 交互大脑] MCP 服务端，将下方 skills 暴露给 AI 调用
│
├── core\                        <-- [基建引擎层]
│   ├── auto_config_builder.py   # 自动构建 project_config.yaml
│   ├── hil_parser.py            # DWARF/.map 解析器，生成 .hil_symbols.json
│   ├── keil_parser.py           # Keil .uvprojx 工程解析
│   ├── mcu_mem_ctrl.py          # J-Link 物理内存读写驱动
│   ├── project_wizard.py        # Setup 向导后端（环境检测 / 代码生成 / XML 注入 / 编译 / 部署）
│   └── doc_parser.py            # PDF 文档清洗（LlamaCloud）
│
├── skills\                      <-- [业务技能层]
│   ├── build\                   # compile_auto / flash_auto / reset
│   ├── injection\               # mcp_hil_bridge（HIL 热注入核心）
│   └── perception\              # monitor_rtt_auto / rtt_exchange_auto / rtt_capture
│
├── HIL\                         <-- [MCU 固件底座] 热更新注入代码
│   ├── hil_inject.c / hil_inject.h    # 注入逻辑实现
│   ├── hil_config_user.h              # 用户参数结构体模板
│   └── example_main.c                 # 集成示例
│
├── RTT\                         <-- [SEGGER RTT 协议栈] 官方开源代码
│   ├── SEGGER_RTT.c / SEGGER_RTT.h / SEGGER_RTT_printf.c / SEGGER_RTT_Conf.h
│
├── assets\                      <-- [GUI 前端资源]
│   ├── setup_ui_v2_working.html # 当前 GUI 页面（Vue + Tailwind）
│   ├── tailwind.js / vue.js     # 前端框架（本地化，离线可用）
│   ├── mcupilot_iconsp.png      # Splash/GUI 图标
│   └── mcupilot_icon.ico        # exe 窗口图标
│
├── tests\                       <-- [单元测试]
├── knowledge_base\              <-- [MCU 参考手册 SVD]
├── docs\                        <-- [文档]
├── mcupilot_icon.svg            # GitHub 展示图标（深色版）
├── mcupilot_iconsp.svg          # 软件内用图标（浅色版）
├── setup.bat / setup.ps1        # Python 环境一键安装
├── build_kb.py                  # 知识库构建器
├── requirements.txt             # pip 依赖
└── LICENSE                      # MIT


===================================================================================

.\your_mcu_project\            <-- 【目标工程目录】部署后自动生成以下结构
    │
    ├── .hil_symbols.json       # 物理内存字典
    ├── project_config.yaml     # 硬件配置
    │
    ├── HIL\                    # HIL 固件底座（自动复制）
    │   ├── hil_config_user.h   # 用户自定义参数结构体（自动生成）
    │   ├── hil_inject.h / hil_inject.c
    │   └── example_main.c      # 集成参考
    │
    ├── RTT\                    # SEGGER RTT 库（自动复制）
    │   └── SEGGER_RTT.c / .h / _printf.c / _Conf.h
    │
    ├── output\                 # Keil 编译产物 (.map / .axf / .hex)
    └── src\                    # 业务逻辑源码
