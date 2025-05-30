/*
 * SPDX-FileCopyrightText: 2022-2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "esp_private/sleep_clock.h"
#include "soc/hp_sys_clkrst_reg.h"
#include "soc/pmu_reg.h"
#include "soc/lpperi_reg.h"
#include "pmu_bit_defs.h"

static __attribute__((unused)) const char *TAG = "sleep_clock";

esp_err_t sleep_clock_system_retention_init(void *arg)
{
    #define N_REGS_PCR()    (((HP_SYS_CLKRST_HPCORE_WDT_RESET_SOURCE0_REG - DR_REG_HP_SYS_CLKRST_BASE) / 4) + 1)

    const static sleep_retention_entries_config_t pcr_regs_retention[] = {
        /* Enable i2c master clock */
        [0] = { .config = REGDMA_LINK_WRITE_INIT (REGDMA_PCR_LINK(0),     LPPERI_CLK_EN_REG,                 LPPERI_CK_EN_LP_I2CMST,                        LPPERI_CK_EN_LP_I2CMST_M,                        1, 1), .owner = ENTRY(0) },
        /* Start SYSPLL self-calibration */
        [1] = { .config = REGDMA_LINK_WRITE_INIT (REGDMA_PCR_LINK(1),     HP_SYS_CLKRST_ANA_PLL_CTRL0_REG,   0,                                             HP_SYS_CLKRST_REG_SYS_PLL_CAL_STOP_M,            1, 1), .owner = ENTRY(0) },
        /* Wait calibration done */
        [2] = { .config = REGDMA_LINK_WAIT_INIT  (REGDMA_PCR_LINK(2),     HP_SYS_CLKRST_ANA_PLL_CTRL0_REG,   HP_SYS_CLKRST_REG_SYS_PLL_CAL_END,             HP_SYS_CLKRST_REG_SYS_PLL_CAL_END_M,             1, 0), .owner = ENTRY(0) },
        /* Stop SYSPLL self-calibration */
        [3] = { .config = REGDMA_LINK_WRITE_INIT (REGDMA_PCR_LINK(3),     HP_SYS_CLKRST_ANA_PLL_CTRL0_REG,   HP_SYS_CLKRST_REG_SYS_PLL_CAL_STOP,            HP_SYS_CLKRST_REG_SYS_PLL_CAL_STOP_M,            1, 0), .owner = ENTRY(0) },
        /* Clock configuration retention */
        [4] = { .config = REGDMA_LINK_CONTINUOUS_INIT(REGDMA_PCR_LINK(4), DR_REG_HP_SYS_CLKRST_BASE,         DR_REG_HP_SYS_CLKRST_BASE,                     N_REGS_PCR(),                                    0, 0), .owner = ENTRY(0) },  /* pcr */
        [5] = { .config = REGDMA_LINK_WRITE_INIT     (REGDMA_PCR_LINK(5), HP_SYS_CLKRST_ROOT_CLK_CTRL0_REG,  HP_SYS_CLKRST_REG_SOC_CLK_DIV_UPDATE,          HP_SYS_CLKRST_REG_SOC_CLK_DIV_UPDATE_M,          1, 0), .owner = ENTRY(0) },
        [6] = { .config = REGDMA_LINK_WAIT_INIT      (REGDMA_PCR_LINK(6), HP_SYS_CLKRST_ROOT_CLK_CTRL0_REG,  0x0,                                           HP_SYS_CLKRST_REG_SOC_CLK_DIV_UPDATE_M,          1, 0), .owner = ENTRY(0) },
        [7] = { .config = REGDMA_LINK_WRITE_INIT     (REGDMA_PCR_LINK(7), HP_SYS_CLKRST_PERI_CLK_CTRL02_REG, HP_SYS_CLKRST_REG_SDIO_LS_CLK_EDGE_CFG_UPDATE, HP_SYS_CLKRST_REG_SDIO_LS_CLK_EDGE_CFG_UPDATE_M, 1, 0), .owner = ENTRY(0) },
        [8] = { .config = REGDMA_LINK_WAIT_INIT      (REGDMA_PCR_LINK(8), HP_SYS_CLKRST_PERI_CLK_CTRL02_REG, 0x0,                                           HP_SYS_CLKRST_REG_SDIO_LS_CLK_EDGE_CFG_UPDATE_M, 1, 0), .owner = ENTRY(0) },
    };

    esp_err_t err = sleep_retention_entries_create(pcr_regs_retention, ARRAY_SIZE(pcr_regs_retention), REGDMA_LINK_PRI_SYS_CLK, SLEEP_RETENTION_MODULE_CLOCK_SYSTEM);
    ESP_RETURN_ON_ERROR(err, TAG, "failed to allocate memory for system (PCR) retention");
    ESP_LOGI(TAG, "System Power, Clock and Reset sleep retention initialization");
    return ESP_OK;
}
