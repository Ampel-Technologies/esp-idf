/*
 * SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>
#include "esp_log.h"
#include "esp_check.h"
#include "esp_eth.h"
#include "esp_eth_phy_802_3.h"

static const char *TAG = "eth_phy_generic";

esp_eth_phy_t *esp_eth_phy_new_generic(const eth_phy_config_t *config)
{
    esp_eth_phy_t *ret = NULL;
    phy_802_3_t *phy_802_3 = calloc(1, sizeof(phy_802_3_t));
    eth_phy_config_t phy_802_3_config = *config;
    // default chip specific configuration if not defined by user
    ESP_GOTO_ON_FALSE(esp_eth_phy_802_3_obj_config_init(phy_802_3, &phy_802_3_config) == ESP_OK,
                        NULL, err, TAG, "configuration initialization of PHY 802.3 failed");

    return &phy_802_3->parent;
err:
    return ret;
}

