import time
from enum import IntEnum
from radio import LoRa, Meshtastic

class SX126x:
    GPIO_RST = 1<<4

    Fxosc = 32e6
    Fclk = 10e6

    class IRQ(IntEnum):
        TX_DONE = 1 << 0
        RX_DONE = 1 << 1
        PREAMBLE_DETECTED = 1 << 2
        SYNCWORD_VALID = 1 << 3
        HEADER_VALID = 1 << 4
        HEADER_ERROR = 1 << 5
        CRC_ERROR = 1 << 6
        CAD_DONE = 1 << 7
        CAD_DETECTED = 1 << 8
        TIMEOUT = 1 << 9

    class StdbyConfig(IntEnum):
        RC = 0
        XOSC = 1

    class DeviceMode(IntEnum):
        LORA_SLEEP = 0
        LORA_STANDBY = 1
        LORA_FS_TX = 2
        LORA_TX = 3
        LORA_FS_RX = 4
        LORA_RX_CONTINUOUS = 5
        LORA_RX_SINGLE = 6
        LORA_CAD = 7

    CMD_GET_DEVICE_ERRORS = 0x17
    CMD_SET_STANDBY = 0x80
    CMD_SET_RX = 0x82
    CMD_SET_TX = 0x83
    CMD_SET_SLEEP = 0x84
    CMD_SET_RF_FREQUENCY = 0x86
    CMD_SET_PACKET_TYPE = 0x8A
    CMD_SET_TX_PARAMS = 0x8E
    CMD_SET_DIO_IRQ_PARAMS = 0x08
    CMD_SET_MODULATION_PARAMS = 0x8B
    CMD_SET_PACKET_PARAMS = 0x8C
    CMD_GET_PACKET_STATUS = 0x14
    CMD_CLEAR_IRQ_STATUS = 0x02
    CMD_WRITE_REGISTER = 0x0D
    CMD_READ_REGISTER = 0x1D
    CMD_WRITE_BUFFER = 0x0E
    CMD_GET_IRQ_STATUS = 0x12
    CMD_GET_RX_BUFFER_STATUS = 0x13
    CMD_READ_BUFFER = 0x1E
    CMD_SET_BUFFER_BASE_ADDR = 0x8F
    CMD_SET_DIO3_AS_TXCO_CTRL = 0x97
    CMD_SET_DIO2_AS_RF_SWITCH_CTRL = 0x9D
    CMD_STOP_TIMER_ON_PREAMBLE = 0x9F
    CMD_SET_PA_CONFIG = 0x95
    CMD_SET_REGULATOR_MODE = 0x96
    CMD_GET_STATUS = 0xC0

    PACKET_TYPE_LORA = 0x01

    def __init__(self, device=None):
        from pyftdi.usbtools import UsbTools
        from pyftdi.ftdi import Ftdi
        from pyftdi.spi import SpiController

        if device is None or device == "-":
            device = 'ftdi://::/1'
        elif type(device) == int:
            devs = [f'ftdi://{d[0].vid}:{d[0].pid}:{d[0].bus}:{d[0].address}/1' for d in Ftdi.list_devices()]
            print(devs)
            device = devs[device]

        self.spi = SpiController()
        self.spi.configure(device)
        self.slave = self.spi.get_port(cs=0, freq=SX126x.Fclk, mode=0)
        self.gpio = self.spi.get_gpio()

        self.gpio.set_direction(SX126x.GPIO_RST, SX126x.GPIO_RST)
        self.gpio.write(0)
        time.sleep(0.1)
        self.gpio.write(SX126x.GPIO_RST)
        time.sleep(0.2)

        version = self.readRegister(0x0320, 16)
        print("version", version)
        self.bw = LoRa.BandWidth.BW_125K
        self.cr = LoRa.CodingRate.CR_4_5
        self.implicitHeader = False
        self.sf = LoRa.SpreadingFactor.SF_128
        self.txCont = False
        self.crc = True
        self.sync = 0x12
        self.preambleLength = 1

        self.standby()

        # Ra-01S / Ra-01SH use DIO2 to control RF switch
        self.setCommand(SX126x.CMD_SET_DIO2_AS_RF_SWITCH_CTRL, 0x01)

        # Ra-01S / Ra-01SH use only LDO in all modes.
        self.setCommand(SX126x.CMD_SET_REGULATOR_MODE, 0x00)

        # Enable all IRQs
        self.setCommand(SX126x.CMD_SET_DIO_IRQ_PARAMS, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)

        self.setCommand(SX126x.CMD_STOP_TIMER_ON_PREAMBLE, 0x0)
        self.setCommand(SX126x.CMD_SET_PA_CONFIG, 0x04, 0x07, 0x00, 0x01)

    def getCommand(self, op, readlen):
        cmd = [op] + [0x0] * (readlen + 1)
        # print(f"Get command", [f"{x:02X}" for x in cmd])
        ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        # print(f"Get 0x{op:02X} <<", [f"{x:02X}" for x in ret[1:]])
        time.sleep(0.001)
        return ret[2:] # skip 0:RFU, 1:Status

    def setCommand(self, op, *args):
        cmd = [op, *args]
        print(f"Set command", [f"{x:02X}" for x in cmd])
        # ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        ret = self.slave.write(cmd)
        time.sleep(0.001)

    def readRegister(self, addr, readlen):
        addrh = (addr >> 8) & 0xFF
        addrl = addr & 0xFF
        cmd = [SX126x.CMD_READ_REGISTER, addrh, addrl] + [0x0] * (readlen+1)
        # print(f"Read register", [f"{x:02X}" for x in cmd])
        ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        # print(f"Read register <<", [f"{x:02X}" for x in ret])
        time.sleep(0.001)
        return ret[4:]

    def writeRegister(self, addr, *data):
        addrh = (addr >> 8) & 0xFF
        addrl = addr & 0xFF
        cmd = [SX126x.CMD_WRITE_REGISTER, addrh, addrl, *data]
        print(f"Write register", [f"{x:02X}" for x in cmd])
        # ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        ret = self.slave.write(cmd)
        time.sleep(0.001)

    def readBuffer(self, addr, readlen):
        cmd = [SX126x.CMD_READ_BUFFER, addr] + [0x0] * (readlen + 1)
        print(f"Read buffer", [f"{x:02X}" for x in cmd])
        ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        print(f"Read buffer <<", [f"{x:02X}" for x in ret])
        return ret[3:]

    def getStatus(self):
        cmd = [0xC0, 0x00]
        # print(f"Get status", [f"{x:02X}" for x in cmd])
        ret = self.slave.exchange(cmd, len(cmd), duplex=True)
        # print("Status", f"{ret[1]:08b}")
        time.sleep(0.001)
        return ret[1]

    def wait_rx(self):
        """
        Return:
            True if RX_DONE
            False if CRC_ERROR
            None if RX_TIMEOUT
        """
        while True:
            irq_status = self.getCommand(SX126x.CMD_GET_IRQ_STATUS, 2)
            irq = (irq_status[0] << 8) | irq_status[1]
            # if irq != 0:
            #     print("irq_flags", f"{irq:016b}")

            if irq & SX126x.IRQ.TIMEOUT:
                self.setCommand(SX126x.CMD_CLEAR_IRQ_STATUS, 0xFF, 0xFF)
                return  None
            if irq & SX126x.IRQ.CRC_ERROR:
                self.setCommand(SX126x.CMD_CLEAR_IRQ_STATUS, 0xFF, 0xFF)
                return  False
            if irq & SX126x.IRQ.RX_DONE:
                self.setCommand(SX126x.CMD_CLEAR_IRQ_STATUS, 0xFF, 0xFF)
                return  True

            time.sleep(0.1)

    def setFrequency(self, freq):
        frf = int(freq * (2**25) / SX126x.Fxosc)
        frf = ((frf >> 24) & 0xFF), ((frf >> 16) & 0xFF), ((frf >> 8) & 0xFF), (frf & 0xFF)
        print("FRF", freq, frf)
        self.setCommand(SX126x.CMD_SET_RF_FREQUENCY, frf[0], frf[1], frf[2], frf[3])

    def setSync(self, value = 0x12):
        self.sync = value & 0xFF
        msb = (self.sync & 0xF0) | 4
        lsb = ((self.sync << 4) & 0xF0) | 4
        self.writeRegister(0x0740, msb, lsb)

        sync = self.readRegister(0x0740, 2)
        if sync != bytes([msb, lsb]):
            raise Exception("Sync word mismatch")

    def setBandwidth(self, bw: LoRa.BandWidth):
        self.bw = bw

    def setCodingRate(self, cr: LoRa.CodingRate):
        self.cr = cr

    def setImplicitHeader(self, implicitHeader: bool):
        self.implicitHeader = implicitHeader

    def setSpreadingFactor(self, sf: LoRa.SpreadingFactor):
        self.sf = sf

    def setPacketParams(self):
        self.setCommand(SX126x.CMD_SET_PACKET_PARAMS,
                          (self.preambleLength >> 8) & 0xFF,
                          self.preambleLength & 0xFF,
                          [0, 1][self.implicitHeader],
                          0xFF,
                          [0, 1][self.crc],
                          0x00 # Standard IQ
                        )

    def setTxContinuous(self, txCont: bool):
        self.txCont = txCont

    def setCrc(self, crc: bool):
        self.crc = crc

    def setTxPower(self, boost: bool, level):
        return

    def setPreambleLength(self, length: int):
        self.preambleLength = length

    def setModulationParams(self):
        bw_khz = LoRa.BandWidthMap[self.bw] / 1000
        symbolLength = (1 << self.sf) / bw_khz
        lowDataRateOpt = 1 if symbolLength > 16 else 0
        bw = {
            LoRa.BandWidth.BW_7_8K: 0x0,
            LoRa.BandWidth.BW_10_4K: 0x8,
            LoRa.BandWidth.BW_15_6K: 0x1,
            LoRa.BandWidth.BW_20_8K: 0x9,
            LoRa.BandWidth.BW_31_25K: 0x2,
            LoRa.BandWidth.BW_41_7K: 0xA,
            LoRa.BandWidth.BW_62_5K: 0x3,
            LoRa.BandWidth.BW_125K: 0x4,
            LoRa.BandWidth.BW_250K: 0x5,
            LoRa.BandWidth.BW_500K: 0x6,
        }.get(self.bw)
        self.setCommand(SX126x.CMD_SET_MODULATION_PARAMS, self.sf, bw, self.cr, lowDataRateOpt)

    def standby(self):
        self.setCommand(SX126x.CMD_SET_STANDBY, SX126x.StdbyConfig.RC)

    def receive(self):
        self.setModulationParams()
        self.setPacketParams()

        # Clear IRQ status
        self.setCommand(SX126x.CMD_CLEAR_IRQ_STATUS, 0xFF, 0xFF)

        # Start receive mode with no timeout, continuous mode
        self.setCommand(SX126x.CMD_SET_RX, 0xFF, 0xFF, 0xFF)

    def read_payload(self):
        # Get packet status
        pkt_len, rx_buf_addr = self.getCommand(SX126x.CMD_GET_RX_BUFFER_STATUS, 2)
        print("pkt_len", pkt_len, "rx_buf_addr", rx_buf_addr)

        # Read the received packet
        rx_data = self.readBuffer(rx_buf_addr, pkt_len)
        return rx_data

    def send(self, data):
        print("Send not implemented")
        return

    def setMeshtastic(self, region="TW", preset="LONG_FAST", slot=None):
        regionCfg = Meshtastic.REGION.get(region, "TW")
        presetCfg = Meshtastic.PRESETS.get(preset, "LONG_FAST")

        print("regionCfg", regionCfg)
        print("presetCfg", presetCfg)

        if not slot:
            slot = regionCfg["defaultSlot"]

        bw = LoRa.BandWidthMap[presetCfg["bw"]]
        freq = regionCfg["startFreq"] + bw/2 + bw*(slot-1)

        if freq > regionCfg["endFreq"]:
            raise Exception(f"Frequency {freq} out of range {regionCfg['startFreq']} - {regionCfg['endFreq']}")

        self.standby()
        self.setCommand(SX126x.CMD_SET_PACKET_TYPE, SX126x.PACKET_TYPE_LORA)

        self.setBandwidth(presetCfg["bw"])
        self.setSpreadingFactor(presetCfg["sf"])
        self.setCodingRate(presetCfg["cr"])

        self.setImplicitHeader(False)
        self.setTxContinuous(False)
        self.setCrc(True)
        self.setSync(0x2B)
        self.setTxPower(True, 0)
        self.setPreambleLength(16)

        self.setFrequency(freq)

if __name__ == "__main__":
    import sys
    from datetime import datetime

    if len(sys.argv) < 3:
        print("Usage: sx126x.py deviceIdx rx")
        print("Usage: sx126x.py deviceIdx tx")
        sys.exit(1)

    device = sys.argv[1]
    action = sys.argv[2]

    try:
        device = int(device)
    except:
        pass

    sx = SX126x(device)
    sx.standby()

    sx.setMeshtastic("TW", "LONG_FAST")

    if action == "tx":
        sx.send(b'\xff\xff\xff\xffp\x87\xa8\xbb\xe0\xa5/^c\x08\x00\x00\x01\x8ey=\x87\xfc4\xdc\xbd#')

    if action == "rx":
        sx.receive()
        while True:
            ok = sx.wait_rx()
            if ok is None:
                print("Timeout")
                continue

            data = sx.read_payload()
            print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), "OK" if ok else "NG", data)
