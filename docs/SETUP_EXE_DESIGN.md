# McuPilot 桌面配置向导 — 设计文档

> **注意：本文档为早期设计草稿，实际实现已偏离文档描述。**
> 当前实现见源码 `run_setup.py` + `core/project_wizard.py`。
> 主要差异：GUI 采用 PyWebView 而非 CustomTkinter；COM 注入改为 XML 注入；
> 部署流程增加了 main.c 自动注入步骤；exe 打包策略不同。

## 概述

打包为单个 `McuPilot.exe`，用户双击即可完成从环境检测到项目部署的全部配置。

**exe 定位规则**：exe 必须放在 `McuPilot` 根目录，通过 `sys.executable` 父目录找到同目录下的 `core/`、`skills/`、`HIL/`、`RTT/`、`requirements.txt`。这些源文件保留在磁盘上——exe 只打包 GUI 框架依赖，不打包项目模块。原因是部署阶段的子进程（编译、解析等）需要系统 Python 通过 `python -m core.xxx` 调用磁盘上的模块。

## 一、用户视角的完整流程

```
下载项目包（GitHub Release 或本地文件夹）

双击 McuPilot_Setup.exe
    │
    ├─ 启动检测
    │   ├─ 检查系统 Python 3.10+
    │   │   ├─ 已安装 → 继续
    │   │   └─ 未安装 → "是否自动安装 Python 3.10+？"
    │   │       ├─ 是 → 从 python.org 下载 → 静默安装 → 继续
    │   │       └─ 否 → 提示手动安装后退出
    │   │
    │   └─ 检查 pip 依赖（pylink, pyelftools, customtkinter 等）
    │       ├─ 齐全 → 继续
    │       └─ 缺了 → "正在安装依赖..." → pip install → 继续
    │
    └─ 进入 GUI 配置向导
        │
        ├─ 【页面一：工程设置】
        │   ├─ 输入/浏览 Keil 工程目录
        │   ├─ 选择后自动检测并显示：
        │   │   ├─ 芯片型号   → 从 .uvprojx 解析
        │   │   ├─ Keil 路径   → 从注册表/路径扫描
        │   │   └─ J-Link 状态 → 从 pylink 扫 USB
        │   ├─ 填写可热修参数表
        │   │   ├─ 列：变量名 | 类型(下拉) | 默认值 | 删除按钮
        │   │   └─ [+ 添加参数] 按钮
        │   ├─ 勾选 AI 客户端
        │   │   ☐ Claude Code    ☐ Roo Code    ☐ Codex CLI
        │   └─ [下一步] 按钮
        │
        ├─ 【页面二：确认部署】
        │   ├─ 显示部署摘要
        │   ├─ [开始部署] 按钮
        │   ├─ 实时进度日志
        │   │   ├─ ① 生成 hil_config_user.h     → ✓ / ✗
        │   │   ├─ ② 复制 HIL/RTT 到工程         → ✓ / ✗
        │   │   ├─ ③ COM 注入 Keil 工程          → ✓ / ✗
        │   │   ├─ ④ 编译工程                    → ✓ / ✗
        │   │   ├─ ⑤ 解析内存字典                → ✓ / ✗
        │   │   └─ ⑥ 注册 MCP 到所选客户端        → ✓ / ✗
        │   └─ 完成 → 提示如何开始使用
        │
        └─ [关闭]
```

---

## 二、启动检测（GUI 出现前）

此阶段在 GUI 窗口弹出之前执行。exe 启动后会显示一个**控制台进度窗口**：

```
┌──────────────────────────────────────────┐
│  McuPilot Setup                       │
│                                          │
│  ● 检测 Python 环境...                ✓   │
│  ● 安装 pip 依赖...                 ⏳   │
│  ○ 启动配置向导...                        │
│                                          │
└──────────────────────────────────────────┘
```

每步完成后自动进入下一步。仅当需要用户确认（如是否安装 Python）时弹系统对话框。全部通过后关闭控制台窗口，启动 GUI。

### 2.1 Python 版本检测

- 调用 `python --version`，解析版本号
- 要求 `≥ 3.10`
- 未安装或版本过低时弹系统对话框（`ctypes` 调 `MessageBoxW`），选项：
  - **自动安装** → 从 `https://www.python.org/ftp/python/` 下载对应版本的安装包 →
    静默运行（`/quiet InstallAllUsers=1 PrependPath=1`）→ 等待完成 → 重新检测
  - **手动安装** → 退出，提示用户自行到 python.org 下载
- 下载失败（无网络） → 提示手动安装

### 2.2 pip 依赖检测

- 调 `python -m pip list` 获取已安装列表
- 与 `requirements.txt` 对比，找出缺失项
- 缺了就调 `python -m pip install -r requirements.txt`
- pip 本身缺失 → 调 `python -m ensurepip`

### 2.3 requirements.txt 需新增的依赖

```
customtkinter>=5.2
pywin32>=305
```

---

## 三、GUI 向导（CustomTkinter）

### 3.1 技术选型

| 框架 | 理由 |
|------|------|
| CustomTkinter | 现代外观、纯 Python、可 PyInstaller 打包 |
| pywin32 | Keil COM 自动化注册文件到工程 |
| ctypes | 系统对话框（环境检测阶段） |

### 3.2 窗口结构

```
┌──────────────────────────────────────────────────┐
│  McuPilot — 项目配置向导                       │
├──────────────────────────────────────────────────┤
│                                                    │
│  [页面一：工程设置]          ← 默认显示              │
│  [页面二：确认部署]          ← 上一步完成后显示       │
│                                                    │
│  [上一步]  [下一步/开始部署]                         │
└──────────────────────────────────────────────────┘
```

### 3.3 页面一详情：工程设置

```
┌──────────────────────────────────────────────────────┐
│  ◉ 工程路径                                          │
│  ┌───────────────────────────┬──────────┐            │
│  │ C:\Projects\hc32_radar    │ 浏览...   │            │
│  └───────────────────────────┴──────────┘            │
│                                                      │
│  ◉ 环境检测（路径输入后自动刷新）                       │
│  ┌──────────────────────────────────────────────┐    │
│  │ 芯片型号     HC32F460           ✓           │    │
│  │ Keil MDK    C:\Keil_v5\UV4      ✓           │    │
│  │ J-Link      SN 12345678, 3.3V   ✓           │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  ◉ 可热修参数                                         │
│  ┌──────────────┬──────────────┬───────────────┐    │
│  │ 变量名 ▼      │ 类型 ▼        │ 默认值         │    │
│  ├──────────────┼──────────────┼───────────────┤    │
│  │ threshold    │ uint32_t  ▾  │ 8000          │ X  │
│  │ gain         │ uint32_t  ▾  │ 45            │ X  │
│  │ velocity_min │ int16_t   ▾  │ -100          │ X  │
│  └──────────────┴──────────────┴───────────────┘    │
│  [+ 添加参数]                                         │
│                                                      │
│  ◉ AI 客户端                                         │
│  ☑ Claude Code    ☑ Roo Code    ☐ Codex CLI          │
│                                                      │
│                              [上一步]  [下一步 ▸]      │
└──────────────────────────────────────────────────────┘
```

#### 交互细节

- **浏览按钮**：调 Windows 原生文件夹选择对话框
- **环境检测**：路径变化时自动触发，每次重新检测。三项全部通过才能点下一步
- **类型下拉**：提供 uint8_t / uint16_t / uint32_t / int8_t / int16_t / int32_t / float
- **默认值**：建议给 0，用户可改
- **添加/删除**：最少保留 0 行（允许没有热修参数），可以无限添加
- **AI 客户端**：至少勾选一个才能下一步

### 3.4 页面二详情：确认部署

```
┌──────────────────────────────────────────────────────┐
│  ◉ 部署摘要                                           │
│  ┌──────────────────────────────────────────────┐    │
│  │ 工程路径:     C:\Projects\hc32_radar           │    │
│  │ 芯片型号:     HC32F460                        │    │
│  │ 热修参数:     3 个 (threshold, gain, ...)      │    │
│  │ AI 客户端:    Claude Code, Roo Code            │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [开始部署]                                           │
│                                                      │
│  ◉ 进度                                              │
│  ┌──────────────────────────────────────────────┐    │
│  │ ████████░░░░░░░░░  50%                        │    │
│  │                                              │    │
│  │ ① 生成 hil_config_user.h              ✓      │    │
│  │ ② 复制 HIL/RTT 到工程                 ✓      │    │
│  │ ③ COM 注入 Keil 工程                  ✓      │    │
│  │ ④ 编译工程                         ⏳ 进行中 │    │
│  │ ⑤ 解析内存字典                              │    │
│  │ ⑥ 注册 MCP                                 │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│                              [上一步]  [关闭]          │
└──────────────────────────────────────────────────────┘
```

#### 交互细节

- 点"开始部署"后按钮变为禁用，进度条开始走
- 后台线程**顺序执行**各步骤（不可并行，步骤间有依赖链）
- **某步失败**：标记 ✗，展开显示错误原因，提供 [重试此步] 按钮。依赖该步骤的后续步骤自动跳过（不会执行也不报错）
- 全部完成后，显示结果统计
  - **全成功**：提示"部署完成，打开 AI 客户端即可开始使用"
  - **COM 步骤失败**：单独提示"请手动将 HIL/ 和 RTT/ 文件夹中的 .c 文件拖入 Keil 工程树"，其余步骤不受影响
  - **编译/解析失败**：显示错误日志让用户排查

---

## 四、部署步骤详解

### ① 生成 hil_config_user.h

- 输入：用户在 GUI 参数表中填写的变量名、类型列表
- 输出：**覆盖写入用户工程目录下的** `HIL/hil_config_user.h`（基于 `McuPilot/HIL/` 中的模板改造）
- 逻辑：
  1. 读取 `McuPilot/HIL/hil_config_user.h` 模板
  2. 遍历用户参数，按类型大小降序排列（uint32 在前，减少对齐填充）
  3. 生成 `User_Params_t` 结构体，自动计算并插入 `_pad` 字段
  4. 替换模板中的 `HIL_Global_Params_t`，用 `User_Params_t user` 替代原有的 `Radar_Params_t radar` / `Motor_Params_t motor`
  5. 保留 ISR 零开销宏、白名单宏、extern 声明不变
- 注意：此步骤在复制文件之前执行，生成结果暂存在 `McuPilot/HIL/` 工作副本中，随下一步一同复制到用户工程

### ② 复制 HIL/RTT 到工程

- 源：`McuPilot/HIL/` 和 `McuPilot/RTT/`
- 目标：`<工程目录>/HIL/` 和 `<工程目录>/RTT/`
- 如果目标已存在，提示是否覆盖（或自动备份）

### ③ COM 注入 Keil 工程

- 通过 `win32com.client.Dispatch("uVision5.Application")` 连接 Keil
- 打开目标 `.uvprojx`
- 创建 "HIL" 和 "RTT" 两个 Group
- 将 .c 文件添加到对应 Group
- 保存并关闭 Keil
- 如果 COM 不可用 → 提示用户手动添加文件到 Keil 工程树

**COM 备选方案（防 Keil COM 不可用）：**
- 尝试 `uVision5.Application`
- 失败则尝试 `uVision4.Application`
- 都失败则尝试 `Uv5.Application`
- 都失败则提供文字提示告诉用户手动操作

### ④ 编译工程

- 调 `UV4.exe -b <project.uvprojx> -o build.log -j0`
- 等待编译完成，返回错误/警告数
- 如果工程配置文件尚不存在，先用 auto_config_builder 生成

**依赖链及子进程环境：**

所有部署步骤通过系统 Python 子进程执行。关键环境变量：

| 参数 | 值 | 原因 |
|------|----|------|
| `cwd` | 用户工程路径 | auto_config_builder / hil_parser 需要在工程目录下找到 .uvprojx、.map、.axf |
| `PYTHONPATH` | McuPilot 根目录 | 子进程要 `from core.xxx import ...` |

Python 命令示例：
```python
subprocess.run(
    ["python", "-m", "core.auto_config_builder"],
    cwd=user_project_path,              # 用户工程目录
    env={**os.environ, "PYTHONPATH": tools_root},  # McuPilot 根
)
```

步骤顺序：
1. auto_config_builder → 在工程目录下生成 `project_config.yaml`
2. compile_auto → 读 `project_config.yaml`，调 UV4.exe 编译，生成 .map/.axf
3. hil_parser → 读 `project_config.yaml` + .map/.axf，生成 `.hil_symbols.json`

### ⑤ 解析内存字典

- 调 hil_parser 扫描 .map 和 .axf
- 生成 .hil_symbols.json
- 提取白名单变量（带 .hil_expose 标记的）及其物理地址和结构体偏移
- hil_inject.c 已解耦——不再包含任何 MCU 型号相关的头文件，兼容所有 Cortex-M 芯片

### ⑥ 注册 MCP

- 根据用户勾选的客户端，分别写入对应配置文件：

| 客户端 | 配置文件路径 | 写入内容 |
|--------|-------------|---------|
| Claude Code | `%USERPROFILE%\.claude\claude.json` | JSON: `{"mcpServers": {"mcupilot": {...}}}` |
| Roo Code | `<工程目录>\.vscode\mcp.json` | 标准 MCP JSON 配置 |
| Codex CLI | `%USERPROFILE%\.codex\config.toml` | TOML: `[[mcp_servers]]` |

- 如果配置文件已存在包含其他 MCP Server，做增量合并而非覆盖

---

## 五、状态管理

### 页面一 → 页面二 的校验规则

- 工程路径不能为空且目录存在
- 路径下必须能找到 .uvprojx 文件
- 芯片型号必须识别成功
- Keil 路径必须存在
- J-Link 必须连接
- 至少勾选一个 AI 客户端
- 参数表允许为空

### 页面二 的按钮状态

| 条件 | 开始部署 | 关闭 |
|------|:--:|:--:|
| 未开始部署 | 启用 | 启用 |
| 部署进行中 | 禁用 | 禁用 |
| 部署完成（全成功）| 禁用 | 启用 |
| 部署完成（有失败）| 启用（重新部署）| 启用 |

---

## 六、部署失败 × 部署成功的详细UI

部署失败时，页面二的关键细节：

```
◉ 进度
┌──────────────────────────────────────────────────┐
│  ① 生成 hil_config_user.h              ✓        │
│  ② 复制 HIL/RTT 到工程                 ✓        │
│  ③ COM 注入 Keil 工程                  ✗        │
│     ┌──────────────────────────────────────┐    │
│     │ ✗ COM 连接失败                        │    │
│     │ 请手动将 HIL/ 和 RTT/ 的 .c 文件     │  ← 错误详情展开
│     │ 拖入 Keil 工程树：[重试]               │    │
│     └──────────────────────────────────────┘    │
│  ④ 编译工程                             ✓      │
│  ⑤ 解析内存字典                         ✓      │
│  ⑥ 注册 MCP                            ✓      │
│                                               │
│  5/6 步骤成功，1 步需要手动处理                    │  ← 结果统计
└──────────────────────────────────────────────────┘
```

部署完全成功时——没有错误、没有"需要手动处理"：

```
◉ 进度
┌──────────────────────────────────────────────────┐
│  ① 生成 hil_config_user.h              ✓        │
│  ② 复制 HIL/RTT 到工程                 ✓        │
│  ③ COM 注入 Keil 工程                  ✓        │
│  ④ 编译工程 (0 errors, 2 warn)          ✓        │
│  ⑤ 解析内存字典 (5 符号)                ✓        │
│  ⑥ 注册 MCP                           ✓        │
│                                               │
│  全部完成！                                      │
└──────────────────────────────────────────────────┘
```

---

## 七、部署完成后的手动集成指引

COM 注入和编译完成后，用户的 main.c 还需要手动加入 HIL 初始化调用。部署完成后弹出以下提示窗口：

```
┌──────────────────────────────────────────────┐
│  ✓ 部署完成！还需最后一步                       │
├──────────────────────────────────────────────┤
│                                              │
│  请在你的 main.c 中添加以下代码：                │
│                                              │
│  #include "HIL/hil_inject.h"                 │
│  #include "HIL/hil_config_user.h"            │
│                                              │
│  int main(void) {                            │
│      // ... 你的初始化代码 ...                 │
│                                              │
│      HIL_InjectConfig_t cfg = {              │
│          .buf_a = HIL_CFG_A,                 │
│          .buf_b = HIL_CFG_B,                 │
│          .buf_size = HIL_CFG_SIZE,           │
│          .p_version = HIL_P_VER,             │
│          .p_active_idx = HIL_P_IDX,          │
│      };                                      │
│      HIL_Inject_Init(&cfg);                  │
│                                              │
│      for (;;) {                              │
│          HIL_Inject_Task();  // 主循环轮询     │
│          // ... 你的业务代码 ...               │
│      }                                       │
│  }                                           │
│                                              │
│  完整范例见工程目录下的 HIL/example_main.c      │
│                                              │
│                              [复制代码] [关闭] │
└──────────────────────────────────────────────┘
```

### 模板文件

`example_main.c` 随 HIL/ 文件夹一同复制到用户工程目录，供用户直接参考或改名为 `main.c` 使用。

---

## 八、异常场景与边缘情况

| 场景 | 处理 |
|------|------|
| 用户电脑无网络 | Python 和 pip 下载失败 → 提示手动安装 |
| 工程路径选了空目录 | 环境检测全红，下一步禁用 |
| 工程有多个 .uvprojx | 取第一个，显示在界面让用户确认 |
| 编译有错误 | 显示错误数 + 最后几条关键错误信息，允许重试 |
| J-Link 中途拔出 | 不影响部署（部署阶段不需要 J-Link），只在检测页报警 |
| COM 注册了 Keil 但 uVision COM 不可用 | COM 注入步骤失败 → 显示手动操作指南 |
| 用户之前已经配置过 | YAML 和 .hil_symbols.json 已存在 → 覆盖还是跳过？建议覆盖 |
| .claude/claude.json 已有其他 MCP | 增量合并，不删除已有配置 |
| Keil 工程已经有 HIL/RTT 文件 | 检测冲突，提示用户确认覆盖 |

---

## 九、PyInstaller 打包规格

```
打包命令:
pyinstaller --onefile --windowed \
    --name "McuPilot_Setup" \
    --add-data "requirements.txt;." \
    --hidden-import customtkinter \
    --hidden-import win32com \
    --hidden-import pywintypes \
    setup_gui.py

输出: dist/McuPilot_Setup.exe（约 25-40 MB）

压缩建议: 用 UPX 压缩（-9级），可降至 15-25 MB
```

- `--windowed`：不弹命令行黑窗
- `--hidden-import`：确保动态导入的库不丢失
- **不打包 `core/`、`skills/`、`HIL/`、`RTT/`**：这些模块留在磁盘上供系统 Python 子进程调用。exe 通过自身位置（`sys.executable` 父目录）找到它们

---

## 十、文件清单

```
需新建:
  setup_gui.py                               ← GUI 主程序
  core/project_wizard.py                     ← 后端逻辑

需修改:
  requirements.txt                            ← 加 customtkinter, pywin32
  HIL/hil_inject.c                           ← 去掉 #include "hc32l021.h"，已解耦

exe 运行时从磁盘读取（不打包进 exe，通过 sys.executable 父目录定位）:
  core/               (auto_config_builder, hil_parser, keil_parser, mcu_mem_ctrl)
  skills/             (build/, injection/, perception/)
  HIL/                (hil_inject.c, hil_inject.h, hil_config_user.h, example_main.c)
  RTT/                (SEGGER_RTT.c/h, SEGGER_RTT_printf.c, SEGGER_RTT_Conf.h)
  requirements.txt
```
