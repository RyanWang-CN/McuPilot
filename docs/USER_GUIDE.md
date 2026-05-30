# McuPilot 使用指南

> 双击 exe → 选工程 → 一键部署 → AI 操控单片机

## 第一步：硬件环境

- HC32/M0~M4 MCU 开发板 + SEGGER J-Link 连接上电
- 电脑装好 J-Link 驱动（v7.x+）和 Keil MDK v5

## 第二步：启动配置向导

双击 `run_setup.py`（或打包后的 `McuPilot.exe`），进入 splash 启动画面。

自动完成：
- 检测 Python 3.10+ 环境（支持手动指定路径）
- 检测并安装缺失的 pip 依赖

## 第三步：工程设置

1. 浏览或输入 Keil 工程目录（含 .uvprojx）
2. 自动检测：芯片型号 / Keil 路径 / J-Link 连接状态
3. 填写可热修参数表（变量名、类型、默认值）
4. 勾选要注册的 AI 客户端（Claude Code / Cline / Codex）

## 第四步：一键部署

点"开始部署"，自动执行：

| 步骤 | 内容 |
|------|------|
| ① 生成 hil_config_user.h | 根据参数表生成用户结构体 |
| ② 复制 HIL/RTT 到工程 | 将固件底座拷贝到目标目录 |
| ③ 注册文件到 Keil 工程 | XML 注入文件组 + include 路径 + 自动适配 main.c |
| ④ 编译工程 | UV4.exe 命令行编译 |
| ⑤ 解析内存字典 | 生成 .hil_symbols.json |
| ⑥ 注册 MCP | 写入 AI 客户端配置文件 |

HIL 初始化代码已自动注入 main.c，无需手动添加。

## 第五步：开始使用

部署完成后，打开 AI 客户端即可通过 MCP 操控单片机。

常用操作：
- `inject_hil_parameters({"kp_gain_motor": 3.5})` — 热修参数，不停机即刻生效
- `read_hil_variable("kp_gain_motor")` — 读取当前变量值
- `rtt_print` — 查看 MCU 日志输出
- `rtt_capture` — 高速采集传感器二进制波形
- `check_mcu_status` — 诊断 MCU 运行状态

## 常见问题

| 现象 | 检查 |
|------|------|
| J-Link 未检测到 | 驱动装了吗？J-Link USB 插好了吗？ |
| 芯片型号未识别 | 路径下有 .uvprojx 吗？ |
| 编译失败 | 工程配置正确吗？Keil Flash Download 算法配了吗？ |
| HIL 热注入无效 | 固件里调了 HIL_Inject_Task() 吗？ |
| .hil_symbols.json 无变量 | 是否用 ARMCC V5 编译？已自动兼容 |
