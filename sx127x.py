import time
from enum import IntEnum
from radio import LoRa, Meshtastic

class SX127x:
    GPIO_RST = 1<<4

    Fxosc = 32e6
    Fclk = 10e6

    REG_FIFO = 0x00
    REG_OPMODE = 0x01
    REG_FRF = 0x06
    REG_PACONFIG = 0x09
    REG_FIFOADDRPTR = 0x0D
    REG_FIFOTXBASEADDR = 0x0E
    REG_FIFORXBASEADDR = 0x0F
    REG_FIFORXCURRENTADDR = 0x10
    REG_IRQFLAGS = 0x12
    REG_RXNBBYTES = 0x13
    REG_MODEMCONFIG1 = 0x1D
    REG_MODEMCONFIG2 = 0x1E
    REG_PREAMBLE = 0x20
    REG_PAYLOADLENGTH = 0x22
    REG_SYNCVALUE = 0x39
    REG_VERSION = 0x42

    OPMODE_LONGRANGE = 0x80

    class IRQ(IntEnum):
        RX_TIMEOUT = 1 << 7
        RX_DONE = 1 << 6
        PAYLOAD_CRC_ERROR = 1 << 5
        VALID_HEADER = 1 << 4
        TX_DONE = 1 << 3
        CAD_DONE = 1 << 2
        FHSS_CHANGE_CHANNEL = 1 << 1
        CAD_DETECTED = 1 << 0

    class DeviceMode(IntEnum):
        LORA_SLEEP = 0
        LORA_STANDBY = 1
        LORA_FS_TX = 2
        LORA_TX = 3
        LORA_FS_RX = 4
        LORA_RX_CONTINUOUS = 5
        LORA_RX_SINGLE = 6
        LORA_CAD = 7

    def __init__(self, device=None):
        from pyftdi.usbtools import UsbTools
        from pyftdi.ftdi import Ftdi
        from pyftdi.spi import SpiController

        if device is None:
            device = 'ftdi://::/1'
        elif type(device) == int:
            devs = [f'ftdi://{d[0].vid}:{d[0].pid}:{d[0].bus}:{d[0].address}/1' for d in Ftdi.list_devices()]
            print(devs)
            device = devs[device]

        self.spi = SpiController()
        self.spi.configure(device)
        self.slave = self.spi.get_port(cs=0, freq=SX127x.Fclk, mode=0)
        self.gpio = self.spi.get_gpio()

        self.gpio.set_direction(SX127x.GPIO_RST, SX127x.GPIO_RST)
        self.gpio.write(0)
        time.sleep(0.001)
        self.gpio.write(SX127x.GPIO_RST)
        time.sleep(0.005)

        version = self.read_version()
        if version != 0x12:
            raise Exception(f"SX127x: Invalid version {version}")

        self.bw = LoRa.BandWidth.BW_125K
        self.cr = LoRa.CodingRate.CR_4_5
        self.implicitHeader = False
        self.sf = LoRa.SpreadingFactor.SF_128
        self.txCont = False
        self.crc = True
        self.sync = 0x12
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_SLEEP])

    def wait_rx(self, timeout=3):
        """
        Return:
            True if RX_DONE
            False if CRC_ERROR
            None if RX_TIMEOUT
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            irq = None
            while not irq:
                irq = self.slave.exchange([SX127x.REG_IRQFLAGS], 1)
            irq = irq[0]
            # print(f"IRQ: {irq:08b}")
            if irq & SX127x.IRQ.RX_TIMEOUT:
                self.slave.write([0x80 | SX127x.REG_IRQFLAGS, SX127x.IRQ.RX_TIMEOUT])
                return None
            if irq & SX127x.IRQ.PAYLOAD_CRC_ERROR:
                self.slave.write([0x80 | SX127x.REG_IRQFLAGS, SX127x.IRQ.PAYLOAD_CRC_ERROR])
                return False
            if irq & SX127x.IRQ.RX_DONE:
                self.slave.write([0x80 | SX127x.REG_IRQFLAGS, SX127x.IRQ.RX_DONE])
                return True
            # time.sleep(0.1)

    def setFrequency(self, freq):
        frf = int(freq * (2**19) / SX127x.Fxosc)
        frf = ((frf >> 16) & 0xFF), ((frf >> 8) & 0xFF), (frf & 0xFF)
        # print("FRF", freq, frf)
        self.slave.write([0x80 | SX127x.REG_FRF, frf[0]])
        self.slave.write([0x80 | SX127x.REG_FRF+1, frf[1]])
        self.slave.write([0x80 | SX127x.REG_FRF+2, frf[2]])

    def setSync(self, value = 0x12):
        self.sync = value & 0xFF
        self.slave.write([0x80 | SX127x.REG_SYNCVALUE, self.sync])

    def setBandwidth(self, bw: LoRa.BandWidth):
        self.bw = bw

    def setCodingRate(self, cr: LoRa.CodingRate):
        self.cr = cr

    def setImplicitHeader(self, implicitHeader: bool):
        self.implicitHeader = implicitHeader

    def setSpreadingFactor(self, sf: LoRa.SpreadingFactor):
        if sf < 6:
            raise Exception(f"SX127x: Invalid spreading factor {sf}")
        self.sf = sf

    def setTxContinuous(self, txCont: bool):
        self.txCont = txCont

    def setCrc(self, crc: bool):
        self.crc = crc

    def setTxPower(self, boost: bool, level):
        if boost:
            level = min(max(level, 2), 17)
            self.slave.write([0x80 | SX127x.REG_PACONFIG, 0x80 | (level - 2)])
        else:
            level = min(max(level, 0), 14)
            self.slave.write([0x80 | SX127x.REG_PACONFIG, 0x70 | level])

    def setPreambleLength(self, length: int):
        self.slave.write([0x80 | SX127x.REG_PREAMBLE, (length >> 8) & 0xFF, length & 0xFF])

    def setModemConfig1(self):
        self.slave.write([0x80 | SX127x.REG_MODEMCONFIG1, (self.bw << 4) | (self.cr << 1) | [0,1][bool(self.implicitHeader)] ])

    def setModemConfig2(self):
        self.slave.write([0x80 | SX127x.REG_MODEMCONFIG2, (self.sf << 4) | ([0,1][bool(self.txCont)] << 3) | ([0,1][bool(self.crc)] << 2) ])

    def standby(self):
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_STANDBY])

    def receive(self):
        self.setModemConfig1()
        self.setModemConfig2()
        while True:
            target = SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_RX_CONTINUOUS
            self.slave.write([0x80 | SX127x.REG_OPMODE, target])
            r = None
            while not r:
                r = self.slave.exchange([SX127x.REG_OPMODE], 1)
            if r[0] == target:
                break
            time.sleep(0.001)

    def read_version(self):
        return self.slave.exchange([SX127x.REG_VERSION], 1)[0]

    def read_payload(self):
        fifoRxCurrentAddr = self.slave.exchange([SX127x.REG_FIFORXCURRENTADDR], 1)[0]

        # print("fifoRxCurrentAddr", fifoRxCurrentAddr)
        self.slave.write([0x80 | SX127x.REG_FIFOADDRPTR, fifoRxCurrentAddr])

        # print("implicitHeader", self.implicitHeader)
        # print("Payload length", self.slave.exchange([SX127x.REG_PAYLOADLENGTH], 1)[0])
        # print("Rx nb bytes", self.slave.exchange([SX127x.REG_RXNBBYTES], 1)[0])

        if self.implicitHeader:
            packetLength = self.slave.exchange([SX127x.REG_PAYLOADLENGTH], 1)[0]
        else:
            packetLength = self.slave.exchange([SX127x.REG_RXNBBYTES], 1)[0]

        # print("packetLength", packetLength)

        payload = bytearray()
        for i in range(packetLength):
            payload.append(self.slave.exchange([SX127x.REG_FIFO], 1)[0])

        payload = bytes(payload)
        return payload

    def send(self, data):
        # print("Send", data, len(data))
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_STANDBY])
        fifoTxBaseAddr = self.slave.exchange([SX127x.REG_FIFOTXBASEADDR], 1)[0]
        # print("fifoTxBaseAddr", fifoTxBaseAddr)
        self.slave.write([0x80 | SX127x.REG_FIFOADDRPTR, fifoTxBaseAddr])
        for i in range(len(data)):
            self.slave.write([0x80 | SX127x.REG_FIFO, data[i]])
        self.slave.write([0x80 | SX127x.REG_PAYLOADLENGTH, len(data)])
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_TX])

        while True:
            irq = None
            while not irq:
                irq = self.slave.exchange([SX127x.REG_IRQFLAGS], 1)
            irq = irq[0]
            # print(f"IRQ: {irq:08b}")
            if irq & SX127x.IRQ.TX_DONE:
                self.slave.write([0x80 | SX127x.REG_IRQFLAGS, SX127x.IRQ.TX_DONE])
                print("TX Done")
                break

    def setMeshtastic(self, region="TW", preset="LONG_FAST"):
        regionCfg = Meshtastic.REGION.get(region, "TW")
        presetCfg = Meshtastic.PRESETS.get(preset, "LONG_FAST")

        print("regionCfg", regionCfg)
        print("presetCfg", presetCfg)

        bw = LoRa.BandWidthMap[presetCfg["bw"]]
        defaultFreq = regionCfg["startFreq"] + bw/2 + bw*(regionCfg["defaultSlot"]-1)

        self.setFrequency(defaultFreq)

        self.setBandwidth(presetCfg["bw"])
        self.setSpreadingFactor(presetCfg["sf"])
        self.setCodingRate(presetCfg["cr"])

        self.setImplicitHeader(False)
        self.setTxContinuous(False)
        self.setCrc(True)
        self.setSync(0x2B)
        self.setTxPower(True, 0)
        self.setPreambleLength(16)

if __name__ == "__main__":
    import sys
    from datetime import datetime

    if len(sys.argv) < 3:
        print("Usage: sx127x.py deviceIdx rx")
        print("Usage: sx127x.py deviceIdx tx")
        sys.exit(1)

    device = sys.argv[1]
    action = sys.argv[2]

    try:
        device = int(device)
    except:
        pass

    sx = SX127x(device)
    sx.standby()

    sx.setMeshtastic("TW", "LONG_FAST")

    if action == "tx":
        sx.send(b'\xff\xff\xff\xffp\x87\xa8\xbb\xe0\xa5/^c\x08\x00\x00\x01\x8ey=\x87\xfc4\xdc\xbd#')

    if action == "rx":
        sx.receive()
        while True:
            crcError = sx.wait_rx()
            if crcError is None:
                print("Timeout")
                continue

            data = sx.read_payload()
            print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), "NG" if crcError else "OK", data)
