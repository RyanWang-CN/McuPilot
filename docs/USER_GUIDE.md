# MCU AI Tools 使用指南

> 从零跑通：编译烧录 → 读变量 → HIL 热注入

## 第一步：搞硬件

- 华大 HC32 开发板 + SEGGER J-Link 接好，上电
- 电脑装好 J-Link 驱动（v7.x+）和 Keil MDK v5

## 第二步：拉代码装环境

```bash
git clone https://github.com/RyanWang-CN/mcu-ai-tools.git
cd mcu-ai-tools
setup.bat          # Windows 一键搞定
```

## 第三步：固件集成 HIL + RTT

把仓库里的 `HIL/` 和 `RTT/` 复制到你的 Keil 工程，添加到编译列表。参照 `HIL/example_main.c` 初始化即可。

要点：
- 改 `hil_config_user.h`，把你的业务参数塞进 `HIL_Global_Params_t`
- `main()` 里 `HIL_Inject_Init()` → 主循环 `HIL_Inject_Task()`
- 编译烧录一次，让固件跑起来

## 第四步：启动 MCP Server

```bash
python mcp_server.py
```

## 第五步：接入 AI 客户端

以 Claude Code 为例，在 `.claude/claude.json` 里加：

```json
{
  "mcpServers": {
    "mcu-ai-tools": {
      "command": "python",
      "args": ["C:/Users/Administrator/Desktop/MCU_AI_Tools/mcp_server.py"]
    }
  }
}
```

Roo Code 用户在 VS Code 插件设置里添加 MCP Server，指向同样的脚本。

## 第六步：工程初始化（每次新对话必做）

AI 连接上 MCP Server 后，必须先对它说：

> "先帮我初始化工程配置，然后扫描 HIL 字典"

AI 会依次调用：
- `init_project_config` — 嗅探 Keil 工程，生成 `project_config.yaml`（锁定芯片型号、工程路径）
- `update_hil_dictionary` — 扫 `.map/.axf`，生成 `.hil_symbols.json`（告诉 AI 哪些变量可热修、地址在哪）

这一步跑完后，AI 才知道要操作的是哪颗芯片、能改哪些变量。换个新工程或新对话，需要重新跑一次。

## 第七步：开搞

AI 确认芯片型号和可用变量后，直接说人话：

- "帮我编译烧录" → `build_project` + `flash_project`
- "看看现在 CPU 跑着没" → `check_mcu_status`
- "读一下雷达阈值" → `read_hil_variable`
- "把阈值改成 80" → `inject_hil_parameters`（热注入，不停机）
- "抓一段 RTT 日志" → `rtt_print`

## 常见问题

| 现象 | 检查 |
|------|------|
| J-Link 连不上 | J-Link 驱动装了吗？`scan_connected_probes` 看看 |
| 编译报错 | Keil 命令行工具装了没？工程路径对不对 |
| HIL 注入没反应 | `hil_parser` 跑过没？固件里 `HIL_Inject_Task` 在主循环里吗 |
| RTT 抓不到 | 固件初始化了 `SEGGER_RTT_ConfigUpBuffer` 吗 |
