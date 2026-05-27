#ifndef HIL_CONFIG_USER_H
#define HIL_CONFIG_USER_H

#include <stdint.h>

#if defined(__GNUC__) || defined(__ARMCC_VERSION) || defined(__CC_ARM)
    #define HIL_ALIGNED(x)  __attribute__((aligned(x)))
#else
    #define HIL_ALIGNED(x)
#endif

typedef struct HIL_ALIGNED(4) {
    float        kp_gain_motor;
    uint16_t     temp_upper_bound;
    uint16_t  _pad;
} User_Params_t;

typedef struct {
    User_Params_t user;
} HIL_Global_Params_t;

#ifdef __cplusplus
extern "C" {
#endif

extern volatile HIL_Global_Params_t g_hil_buf[2];
extern volatile uint8_t        g_config_version;
extern volatile uint8_t        g_active_idx;

#ifdef __cplusplus
}
#endif

#define HIL_GET_ACTIVE_CFG()    ((volatile HIL_Global_Params_t*)&g_hil_buf[g_active_idx])
#define HIL_CFG_A               ((volatile void*)&g_hil_buf[0])
#define HIL_CFG_B               ((volatile void*)&g_hil_buf[1])
#define HIL_CFG_SIZE            ((uint16_t)sizeof(HIL_Global_Params_t))
#define HIL_P_VER               (&g_config_version)
#define HIL_P_IDX               (&g_active_idx)

#define HIL_WHITELIST __attribute__((used, section(".hil_expose")))

#endif /* HIL_CONFIG_USER_H */
