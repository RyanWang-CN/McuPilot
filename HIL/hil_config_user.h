#ifndef HIL_CONFIG_USER_H
#define HIL_CONFIG_USER_H

#include <stdint.h>

/* ========== 编译器特性适配 ========== */
#if defined(__GNUC__) || defined(__ARMCC_VERSION) || defined(__CC_ARM)
    #define HIL_ALIGNED(x)  __attribute__((aligned(x)))
#else
    #define HIL_ALIGNED(x)
#endif




/* ========== 工程特定结构体（示例：雷达配置）========== */
// 1. 各个模块保持自己的业务解耦，干净清爽
/* 用户根据实际项目修改此结构体，必须 4 字节对齐 */
typedef struct HIL_ALIGNED(4) {
    uint32_t  threshold;      /* 偏移 0 */
    uint32_t  gain;           /* 偏移 4 */
    uint16_t  filter_coef;    /* 偏移 8 */
    uint16_t  _pad;           /* 偏移 10，填充对齐 */
    int16_t   velocity_min;   /* 偏移 12 */
    int16_t   velocity_max;   /* 偏移 14 */
} Radar_Params_t;              /* 总大小 16 字节 */

typedef struct HIL_ALIGNED(4) {
    uint16_t max_rpm;         /* 偏移 0 */
    uint16_t current_limit;   /* 偏移 2 */
} Motor_Params_t;



// 2. 物理层：强行打死包，建立大一统的“参数池”
typedef struct {
    Radar_Params_t radar;
    Motor_Params_t motor;
    // 未来哪怕再加 100 个模块，也全往这里面塞
} HIL_Global_Params_t;


/* ========== 全局变量声明（实际定义在 main.c）========== */
#ifdef __cplusplus
extern "C" {
#endif


extern volatile HIL_Global_Params_t g_hil_buf[2];
//extern volatile Radar_Params_t  g_radar_buf[2];
extern volatile uint8_t        g_config_version;
extern volatile uint8_t        g_active_idx;

#ifdef __cplusplus
}
#endif

/* ========== ISR 零开销宏（关键！volatile 不可丢）========== */
#define HIL_GET_ACTIVE_CFG()    ((volatile HIL_Global_Params_t*)&g_hil_buf[g_active_idx])

/* ========== HIL 初始化配置宏（方便填充 HIL_InjectConfig_t）========== */
#define HIL_CFG_A               ((volatile void*)&g_hil_buf[0])
#define HIL_CFG_B               ((volatile void*)&g_hil_buf[1])
#define HIL_CFG_SIZE            ((uint16_t)sizeof(HIL_Global_Params_t))
#define HIL_P_VER               (&g_config_version)
#define HIL_P_IDX               (&g_active_idx)

#endif /* HIL_CONFIG_USER_H */
