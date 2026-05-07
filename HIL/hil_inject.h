#ifndef HIL_INJECT_H
#define HIL_INJECT_H

#include <stdint.h>

/* HIL 注入配置结构体（用户填充） */
typedef struct {
    volatile void*       buf_a;           /* buffer[0] 地址 */
    volatile void*       buf_b;           /* buffer[1] 地址 */
    uint16_t             buf_size;        /* 结构体大小（用于校验） */
    volatile uint8_t*    p_version;       /* 版本号变量地址（8位） */
    volatile uint8_t*    p_active_idx;    /* 活动索引变量地址 */
} HIL_InjectConfig_t;

/* 初始化 HIL 注入系统（强制初始状态为 0，确保一致性） */
void HIL_Inject_Init(const HIL_InjectConfig_t* config);

/* 后台轮询任务（放入主循环，建议 5-10ms 调用一次） */
void HIL_Inject_Task(void);

/* 获取当前活动配置指针（有函数调用开销，ISR 建议用用户宏） */
volatile void* HIL_GetActiveConfig(void);

/* 通用零开销宏（用户可自定义类型强转） */
#define HIL_GET_ACTIVE_CFG_GENERIC(buf_array, idx_var) \
    ((volatile void*)&(buf_array)[(idx_var)])

/* ========== HIL 安全白名单通行证宏 ========== */
// 强制将变量放入 .hil_expose 特区，并防止被编译器优化裁剪
#define HIL_WHITELIST __attribute__((used, section(".hil_expose")))

#endif /* HIL_INJECT_H */
