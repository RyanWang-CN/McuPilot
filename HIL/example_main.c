/**
 * @file    example_main.c
 * @brief   HIL + RTT 集成示例 —— 最小可跑固件骨架
 *
 * 本文件示范如何将 HIL 注入底座和 SEGGER RTT 集成到你的华大 HC32 工程中。
 * 你可以直接复制关键片段到自己的 main.c，不需要照搬整个文件。
 *
 * 集成清单：
 *   1. 包含头文件: hil_inject.h / hil_config_user.h / SEGGER_RTT.h
 *   2. 定义全局变量: 双缓冲参数池 + 版本号 + 活动索引
 *   3. main() 中依次初始化 RTT → HIL → 外设 → 进入主循环
 *   4. 主循环中调用 HIL_Inject_Task() 轮询版本号变化
 *   5. 业务代码通过 HIL_GET_ACTIVE_CFG() 读取当前参数（零开销）
 *
 * 感谢 SEGGER Microcontroller GmbH 开源的 RTT 协议栈。
 */

#include "hil_inject.h"
#include "hil_config_user.h"
#include "SEGGER_RTT.h"

/* ========== 全局变量定义（HIL 底座依赖，必须在某 .c 中定义）========== */

/* 双缓冲参数池：读写双方通过版本号握手，避免竞争 */
volatile HIL_Global_Params_t g_hil_buf[2] HIL_ALIGNED(4);

/* 版本号：PC 端递增写入，MCU 端轮询检测变化后切换 buffer */
volatile uint8_t g_config_version = 0;

/* 活动索引：ISR / 业务代码根据此值选择当前有效 buffer */
volatile uint8_t g_active_idx = 0;


/* ========== 用户业务代码 ========== */

/**
 * 业务逻辑示例：使用当前激活的雷达参数做处理
 * 参数已被 HIL 热注入替换，无需重启即可生效
 */
static void App_Process(void)
{
    /* 零开销获取当前活动参数指针 */
    volatile Radar_Params_t *radar = &HIL_GET_ACTIVE_CFG()->radar;

    SEGGER_RTT_printf(0,
        "[App] Radar: thr=%u, gain=%u, vel=[%d, %d]\n",
        radar->threshold,
        radar->gain,
        radar->velocity_min,
        radar->velocity_max);
}


/* ========== 主函数 ========== */

int main(void)
{
    /* ---- 1. 初始化 RTT（建议波特率匹配 J-Link 配置）---- */
    SEGGER_RTT_ConfigUpBuffer(0, NULL, NULL, 0, SEGGER_RTT_MODE_NO_BLOCK_SKIP);
    SEGGER_RTT_WriteString(0, "[Init] RTT up channel ready.\n");

    /* ---- 2. 初始化 HIL 注入底座 ---- */
    HIL_InjectConfig_t hil_cfg = {
        .buf_a        = HIL_CFG_A,
        .buf_b        = HIL_CFG_B,
        .buf_size     = HIL_CFG_SIZE,
        .p_version    = HIL_P_VER,
        .p_active_idx = HIL_P_IDX,
    };
    HIL_Inject_Init(&hil_cfg);

    SEGGER_RTT_printf(0,
        "[Init] HIL ready. buf_size=%u, buf_a=0x%08X, buf_b=0x%08X\n",
        hil_cfg.buf_size,
        (unsigned int)(uintptr_t)hil_cfg.buf_a,
        (unsigned int)(uintptr_t)hil_cfg.buf_b);

    /* ---- 3. 初始化你的外设（时钟/GPIO/串口等）---- */
    // SystemClock_Init();
    // GPIO_Init();
    // ...

    /* ---- 4. 主循环 ---- */
    for (;;) {

        /* 4a. HIL 轮询：检测版本号变化并原子切换 buffer（建议 5-10ms 间隔） */
        HIL_Inject_Task();

        /* 4b. 你的业务逻辑 */
        App_Process();

        /* 4c. 简单延时（实际项目中用定时器触发） */
        for (volatile uint32_t i = 0; i < 100000; i++) {
            __NOP();
        }
    }

    return 0; /* unreachable */
}
