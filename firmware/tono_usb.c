// Phase 5 step 1: Mac sees a UAC2 microphone called feuoir, no ADC yet. Pico generates samples itself,
// a 1 kHz sine in the left channel at -6 dBFS peak and digital silence in the right. USB sets the pace:
// each 1 ms packet requests 48 stereo frames. Since 48 kHz / 1 kHz gives exactly 48 samples per cycle,
// each packet starts at the same point in the table and phase stays continuous without carrying an index
// across packets.
// Full specification: docs/audio-usb.md.

#include <math.h>
#include <stdint.h>
#include <string.h>

#include "bsp/board_api.h"
#include "hardware/structs/usb.h"
#include "pico/stdlib.h"
#include "tusb.h"

#include "reloj_maestro.h"

#define TABLE_SAMPLES 48 // 48 kHz / 1 kHz tone
#define CHANNELS 2
#define BYTES_PER_SAMPLE 4 // 4-byte subslot, 24 bits left-aligned
#define PACKET_BYTES (TABLE_SAMPLES * CHANNELS * BYTES_PER_SAMPLE)

static_assert(PACKET_BYTES <= CFG_TUD_AUDIO_EP_SZ_IN, "packet does not fit in declared endpoint");

// Right is exact silence, so the entire packet is the same each ms: built once.
static uint8_t g_packet[PACKET_BYTES];

static void build_packet(void) {
    // -6 dBFS peak with full scale 2^23 - 1, same convention as analyzer.tono().
    const double amplitude = pow(10.0, -6.0 / 20.0) * 8388607.0;
    const double two_pi = 6.283185307179586476925286766559;

    memset(g_packet, 0, sizeof(g_packet)); // right channel: exact zeros

    for (int i = 0; i < TABLE_SAMPLES; i++) {
        int32_t sample = (int32_t)lround(amplitude * sin(two_pi * i / TABLE_SAMPLES));
        int32_t aligned = sample << 8; // 24 bits left-aligned in 4-byte int, little endian
        memcpy(&g_packet[(size_t)i * CHANNELS * BYTES_PER_SAMPLE], &aligned, BYTES_PER_SAMPLE);
    }
}

// Audio controls
bool mute[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1];
uint16_t volume[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1];
uint32_t sampFreq;
uint8_t clkValid;

audio_control_range_2_n_t(1) volumeRng[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1];
audio_control_range_4_n_t(1) sampleFreqRng;

int main(void) {
    reloj_maestro_iniciar(); // first: changes clk_sys

    build_packet();

    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);

    tusb_rhport_init_t dev_init = {
        .role = TUSB_ROLE_DEVICE,
        .speed = TUSB_SPEED_AUTO,
    };
    tusb_init(BOARD_TUD_RHPORT, &dev_init);

    sampFreq = CFG_TUD_AUDIO_FUNC_1_SAMPLE_RATE;
    clkValid = 1;
    sampleFreqRng.wNumSubRanges = 1;
    sampleFreqRng.subrange[0].bMin = CFG_TUD_AUDIO_FUNC_1_SAMPLE_RATE;
    sampleFreqRng.subrange[0].bMax = CFG_TUD_AUDIO_FUNC_1_SAMPLE_RATE;
    sampleFreqRng.subrange[0].bRes = 0;

    uint32_t last_blink = board_millis();
    bool is_on = false;

    while (true) {
        tud_task();

        if (board_millis() - last_blink >= 500) {
            last_blink += 500;
            is_on = !is_on;
            gpio_put(PICO_DEFAULT_LED_PIN, is_on);
        }
    }
}

// Invoked when device is mounted / unmounted / suspended / resumed: nothing to do, the LED already
// blinks separately to show the firmware is running.
void tud_mount_cb(void) {}
void tud_umount_cb(void) {}
void tud_suspend_cb(bool remote_wakeup_en) { (void)remote_wakeup_en; }
void tud_resume_cb(void) {}

// When the host stops streaming, the last IN buffer stays marked available in DPRAM: the host no longer
// polls the endpoint, so it never completes. TinyUSB 0.18.0 does not close ISO endpoints on the RP2040
// and only resets its own state on the next transfer, so reopening the stream hits
// panic("ep 81 was already available") in rp2040_usb.c and the firmware hangs. Clearing the buffer
// control here lets the next open start clean.
#define AUDIO_EP_NUM 1 // EPNUM_AUDIO in tono_usb_descriptors.c
bool tud_audio_set_itf_close_EP_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
    (void)rhport;
    (void)p_request;
    usb_dpram->ep_buf_ctrl[AUDIO_EP_NUM].in = 0;
    return true;
}

//--------------------------------------------------------------------+
// Audio class: volume and mute controls for the feature unit. Firmware never scales the
// samples: what is sent is the table as-is, whether or not the Mac adjusts the controls.
//--------------------------------------------------------------------+

bool tud_audio_set_req_ep_cb(uint8_t rhport, tusb_control_request_t const *p_request, uint8_t *pBuff) {
    (void)rhport;
    (void)pBuff;
    (void)p_request;
    return false;
}

bool tud_audio_set_req_itf_cb(uint8_t rhport, tusb_control_request_t const *p_request, uint8_t *pBuff) {
    (void)rhport;
    (void)pBuff;
    (void)p_request;
    return false;
}

bool tud_audio_set_req_entity_cb(uint8_t rhport, tusb_control_request_t const *p_request, uint8_t *pBuff) {
    (void)rhport;

    TU_VERIFY(p_request->bRequest == AUDIO_CS_REQ_CUR);

    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t entityID = TU_U16_HIGH(p_request->wIndex);

    if (entityID == 2) {
        switch (ctrlSel) {
            case AUDIO_FU_CTRL_MUTE:
                TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_1_t));
                mute[channelNum] = ((audio_control_cur_1_t *)pBuff)->bCur;
                return true;

            case AUDIO_FU_CTRL_VOLUME:
                TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_2_t));
                volume[channelNum] = (uint16_t)((audio_control_cur_2_t *)pBuff)->bCur;
                return true;

            default:
                return false;
        }
    }
    return false;
}

bool tud_audio_get_req_ep_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
    (void)rhport;
    (void)p_request;
    return false;
}

bool tud_audio_get_req_itf_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
    (void)rhport;
    (void)p_request;
    return false;
}

bool tud_audio_get_req_entity_cb(uint8_t rhport, tusb_control_request_t const *p_request) {
    (void)rhport;

    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t entityID = TU_U16_HIGH(p_request->wIndex);

    // Input terminal (stereo input)
    if (entityID == 1) {
        if (ctrlSel == AUDIO_TE_CTRL_CONNECTOR) {
            audio_desc_channel_cluster_t ret;
            ret.bNrChannels = CHANNELS;
            ret.bmChannelConfig = (audio_channel_config_t)(AUDIO_CHANNEL_CONFIG_FRONT_LEFT | AUDIO_CHANNEL_CONFIG_FRONT_RIGHT);
            ret.iChannelNames = 0;
            return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, (void *)&ret, sizeof(ret));
        }
        return false;
    }

    // Feature unit
    if (entityID == 2) {
        switch (ctrlSel) {
            case AUDIO_FU_CTRL_MUTE:
                return tud_control_xfer(rhport, p_request, &mute[channelNum], 1);

            case AUDIO_FU_CTRL_VOLUME:
                switch (p_request->bRequest) {
                    case AUDIO_CS_REQ_CUR:
                        return tud_control_xfer(rhport, p_request, &volume[channelNum], sizeof(volume[channelNum]));

                    case AUDIO_CS_REQ_RANGE: {
                        audio_control_range_2_n_t(1) ret;
                        ret.wNumSubRanges = 1;
                        ret.subrange[0].bMin = -90;
                        ret.subrange[0].bMax = 90;
                        ret.subrange[0].bRes = 1;
                        return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, (void *)&ret, sizeof(ret));
                    }

                    default:
                        return false;
                }

            default:
                return false;
        }
    }

    // Clock source
    if (entityID == 4) {
        switch (ctrlSel) {
            case AUDIO_CS_CTRL_SAM_FREQ:
                switch (p_request->bRequest) {
                    case AUDIO_CS_REQ_CUR:
                        return tud_control_xfer(rhport, p_request, &sampFreq, sizeof(sampFreq));

                    case AUDIO_CS_REQ_RANGE:
                        return tud_control_xfer(rhport, p_request, &sampleFreqRng, sizeof(sampleFreqRng));

                    default:
                        return false;
                }

            case AUDIO_CS_CTRL_CLK_VALID:
                return tud_control_xfer(rhport, p_request, &clkValid, sizeof(clkValid));

            default:
                return false;
        }
    }

    return false;
}

//--------------------------------------------------------------------+
// USB requests a 384-byte packet every ms: always the same, calculated once.
//--------------------------------------------------------------------+

bool tud_audio_tx_done_pre_load_cb(uint8_t rhport, uint8_t itf, uint8_t ep_in, uint8_t cur_alt_setting) {
    (void)rhport;
    (void)itf;
    (void)ep_in;
    (void)cur_alt_setting;

    tud_audio_write(g_packet, PACKET_BYTES);
    return true;
}
