from enum import IntEnum

class LoRa:
    class BandWidth(IntEnum):
        BW_7_8K = 0
        BW_10_4K = 1
        BW_15_6K = 2
        BW_20_8K = 3
        BW_31_25K = 4
        BW_41_7K = 5
        BW_62_5K = 6
        BW_125K = 7
        BW_250K = 8
        BW_500K = 9

    BandWidthMap = {
        BandWidth.BW_7_8K: 7.81e3,
        BandWidth.BW_10_4K: 10.42e3,
        BandWidth.BW_15_6K: 15.63e3,
        BandWidth.BW_20_8K: 20.83e3,
        BandWidth.BW_31_25K: 31.25e3,
        BandWidth.BW_41_7K: 41.67e3,
        BandWidth.BW_62_5K: 62.5e3,
        BandWidth.BW_125K: 125e3,
        BandWidth.BW_250K: 250e3,
        BandWidth.BW_500K: 500e3,
    }

    class CodingRate(IntEnum):
        CR_4_5 = 1
        CR_4_6 = 2
        CR_4_7 = 3
        CR_4_8 = 4

    class SpreadingFactor(IntEnum):
        SF_32 = 5
        SF_64 = 6
        SF_128 = 7
        SF_256 = 8
        SF_512 = 9
        SF_1024 = 10
        SF_2048 = 11
        SF_4096 = 12

class Meshtastic:
    BROADCAST_ADDR = b"\xff\xff\xff\xff"

    # https://meshtastic.org/docs/overview/radio-settings/#presets
    PRESETS = {
        "SHORT_FAST": {
            "bw": LoRa.BandWidth.BW_250K,
            "sf": LoRa.SpreadingFactor.SF_128,
            "cr": LoRa.CodingRate.CR_4_5,
        },
        "SHORT_SLOW": {
            "bw": LoRa.BandWidth.BW_250K,
            "sf": LoRa.SpreadingFactor.SF_256,
            "cr": LoRa.CodingRate.CR_4_5,
        },
        "MID_FAST": {
            "bw": LoRa.BandWidth.BW_250K,
            "sf": LoRa.SpreadingFactor.SF_512,
            "cr": LoRa.CodingRate.CR_4_5,
        },
        "MID_SLOW": {
            "bw": LoRa.BandWidth.BW_250K,
            "sf": LoRa.SpreadingFactor.SF_1024,
            "cr": LoRa.CodingRate.CR_4_5,
        },
        "LONG_FAST": {
            "bw": LoRa.BandWidth.BW_250K,
            "sf": LoRa.SpreadingFactor.SF_2048,
            "cr": LoRa.CodingRate.CR_4_5,
        },
        "LONG_MODERATE": {
            "bw": LoRa.BandWidth.BW_125K,
            "sf": LoRa.SpreadingFactor.SF_2048,
            "cr": LoRa.CodingRate.CR_4_8,
        },
        "LONG_SLOW": {
            "bw": LoRa.BandWidth.BW_125K,
            "sf": LoRa.SpreadingFactor.SF_4096,
            "cr": LoRa.CodingRate.CR_4_8,
        },
        "VERY_LONG_SLOW": {
            "bw": LoRa.BandWidth.BW_62_5K,
            "sf": LoRa.SpreadingFactor.SF_4096,
            "cr": LoRa.CodingRate.CR_4_8,
        },
    }

    # https://meshtastic.org/docs/configuration/radio/lora/#region
    # https://meshtastic.org/docs/configuration/tips/#default-primary-frequency-slots-by-region
    REGION = {
        "TW": {
            "startFreq": 920e6,
            "endFreq": 925e6,
            "spacing": 0,
            "defaultSlot": 16,
        }
    }