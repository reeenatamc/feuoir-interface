// TinyUSB configuration for tono_usb. Only seen by this target: verificar_reloj uses SDK's USB stdio with
// its own configuration and does not include this file.
#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CFG_TUSB_MCU
#error CFG_TUSB_MCU must be defined
#endif

#ifndef BOARD_TUD_RHPORT
#define BOARD_TUD_RHPORT 0
#endif

#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS OPT_OS_NONE
#endif

#ifndef CFG_TUSB_DEBUG
#define CFG_TUSB_DEBUG 0
#endif

#define CFG_TUD_ENABLED 1
#define CFG_TUD_MAX_SPEED OPT_MODE_DEFAULT_SPEED

#ifndef CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_SECTION
#endif

#ifndef CFG_TUSB_MEM_ALIGN
#define CFG_TUSB_MEM_ALIGN __attribute__((aligned(4)))
#endif

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE 64
#endif

// Classes: audio only.
#define CFG_TUD_AUDIO 1
#define CFG_TUD_CDC 0
#define CFG_TUD_MSC 0
#define CFG_TUD_HID 0
#define CFG_TUD_MIDI 0
#define CFG_TUD_VENDOR 0

// UAC2, two-channel input at fixed 48 kHz, 24 bits in 4-byte subslot.
#define CFG_TUD_AUDIO_FUNC_1_SAMPLE_RATE 48000
#define CFG_TUD_AUDIO_FUNC_1_N_BYTES_PER_SAMPLE_TX 4
#define CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX 2

// Audio function descriptor length: stereo input with two-channel feature unit,
// not the single-channel example from SDK (TUD_AUDIO_MIC_ONE_CH_DESCRIPTOR in usbd.h).
#define CFG_TUD_AUDIO_FUNC_1_DESC_LEN (TUD_AUDIO_DESC_IAD_LEN            \
                                        + TUD_AUDIO_DESC_STD_AC_LEN      \
                                        + TUD_AUDIO_DESC_CS_AC_LEN       \
                                        + TUD_AUDIO_DESC_CLK_SRC_LEN     \
                                        + TUD_AUDIO_DESC_INPUT_TERM_LEN  \
                                        + TUD_AUDIO_DESC_OUTPUT_TERM_LEN \
                                        + TUD_AUDIO_DESC_FEATURE_UNIT_TWO_CHANNEL_LEN \
                                        + TUD_AUDIO_DESC_STD_AS_INT_LEN  \
                                        + TUD_AUDIO_DESC_STD_AS_INT_LEN  \
                                        + TUD_AUDIO_DESC_CS_AS_INT_LEN   \
                                        + TUD_AUDIO_DESC_TYPE_I_FORMAT_LEN \
                                        + TUD_AUDIO_DESC_STD_AS_ISO_EP_LEN \
                                        + TUD_AUDIO_DESC_CS_AS_ISO_EP_LEN)

#define CFG_TUD_AUDIO_FUNC_1_N_AS_INT 1
#define CFG_TUD_AUDIO_FUNC_1_CTRL_BUF_SZ 64

#define CFG_TUD_AUDIO_ENABLE_EP_IN 1
#define CFG_TUD_AUDIO_EP_SZ_IN TUD_AUDIO_EP_SIZE(CFG_TUD_AUDIO_FUNC_1_SAMPLE_RATE, CFG_TUD_AUDIO_FUNC_1_N_BYTES_PER_SAMPLE_TX, CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX)
#define CFG_TUD_AUDIO_FUNC_1_EP_IN_SZ_MAX CFG_TUD_AUDIO_EP_SZ_IN
#define CFG_TUD_AUDIO_FUNC_1_EP_IN_SW_BUF_SZ CFG_TUD_AUDIO_EP_SZ_IN

#ifdef __cplusplus
}
#endif

#endif
