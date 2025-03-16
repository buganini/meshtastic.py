import time
from enum import IntEnum

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
    REG_SYNCCONFIG = 0x27
    REG_SYNCVALUE = 0x28
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

    class CodingRate(IntEnum):
        CR_4_5 = 1
        CR_4_6 = 2
        CR_4_7 = 3
        CR_4_8 = 4

    class SpreadingFactor(IntEnum):
        SF_64 = 6
        SF_128 = 7
        SF_256 = 8
        SF_512 = 9
        SF_1024 = 10
        SF_2048 = 11
        SF_4096 = 12

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
        from pyftdi.spi import SpiController

        if device is None:
            device = 'ftdi://::/1'
        elif type(device) == int:
            device = f'ftdi://::/{device}'

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

        self.bw = SX127x.BandWidth.BW_125K
        self.cr = SX127x.CodingRate.CR_4_5
        self.implicitHeader = False
        self.sf = SX127x.SpreadingFactor.SF_128
        self.txCont = False
        self.crc = True
        self.sync = b""
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_SLEEP])


    def wait_irq(self):
        while True:
            irq = self.slave.exchange([SX127x.REG_IRQFLAGS], 1)[0]
            # print(f"IRQ: {irq:08b}")
            if irq & SX127x.IRQ.RX_DONE:
                self.slave.write([0x80 | SX127x.REG_IRQFLAGS, SX127x.IRQ.RX_DONE])
                break

    def setFrequency(self, freq):
        frf = int(freq * (2**19) / SX127x.Fxosc)
        frf = ((frf >> 16) & 0xFF), ((frf >> 8) & 0xFF), (frf & 0xFF)
        print("FRF", freq, frf)
        self.slave.write([0x80 | SX127x.REG_FRF, frf[0]])
        self.slave.write([0x80 | SX127x.REG_FRF+1, frf[1]])
        self.slave.write([0x80 | SX127x.REG_FRF+2, frf[2]])

    def setSync(self, value = None):
        self.sync = value
        self.slave.write(bytes([0x80 | SX127x.REG_SYNCVALUE]) + value)
        syncOn = 0 if value is None else 1
        self.slave.write([0x80 | SX127x.REG_SYNCCONFIG, (syncOn << 4) | (len(value) - 1)])

    def setBandwidth(self, bw: BandWidth):
        self.bw = bw
        self.setModemConfig1()

    def setCodingRate(self, cr: CodingRate):
        self.cr = cr
        self.setModemConfig1()

    def setImplicitHeader(self, implicitHeader: bool):
        self.implicitHeader = implicitHeader
        self.setModemConfig1()

    def setSpreadingFactor(self, sf: SpreadingFactor):
        self.sf = sf
        self.setModemConfig2()

    def setTxContinuous(self, txCont: bool):
        self.txCont = txCont
        self.setModemConfig2()

    def setCrc(self, crc: bool):
        self.crc = crc
        self.setModemConfig2()

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
        self.slave.write([0x80 | SX127x.REG_OPMODE, SX127x.OPMODE_LONGRANGE | SX127x.DeviceMode.LORA_RX_CONTINUOUS])

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
        payload = payload.strip(b"\x00")

        return payload

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

    # TW
    # sx.setFrequency(920.125e6) # slot1
    sx.setFrequency(923.875e6) # slot16

    # Long-Fast
    sx.setBandwidth(SX127x.BandWidth.BW_250K)
    sx.setSpreadingFactor(SX127x.SpreadingFactor.SF_2048)
    sx.setCodingRate(SX127x.CodingRate.CR_4_5)

    sx.setImplicitHeader(False)
    sx.setTxContinuous(False)
    sx.setCrc(True)
    sx.setSync(b"\x2b")
    sx.setTxPower(True, 0)
    sx.setPreambleLength(16)

    if action == "tx":
        pass

    if action == "rx":
        while True:
            sx.receive()
            sx.wait_irq()
            data = sx.read_payload()
            if data:
                print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), data)
