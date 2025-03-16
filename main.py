import sys
import base64
import meshtastic
from meshtastic.protobuf import mesh_pb2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

DEFAULT_KEY = "1PG7OiApB1nwvP+rz05pAQ=="

class MeshPacket:
    def __init__(self, data, aesKey):
        self.dest = data[0:4]
        self.sender = data[4:8]
        self.packetID = data[8:12]
        self.flags = data[12:13]
        self.channelHash = data[13:14]
        self.nextHop = data[14:15]
        self.relayNode = data[15:16]
        self.encryptedPayload = data[16:len(data)]

        # Decrypt the data
        nonce = self.packetID + b'\x00\x00\x00\x00' + self.sender + b'\x00\x00\x00\x00'
        cipher = Cipher(algorithms.AES(base64.b64decode(aesKey.encode("ascii"))), modes.CTR(nonce), backend=default_backend())
        decryptor = cipher.decryptor()
        self.packetPayload = decryptor.update(self.encryptedPayload) + decryptor.finalize()

        self.packetData = mesh_pb2.Data()
        try:
            self.packetData.ParseFromString(self.packetPayload)
        except:
            self.packetData = None

        print(self.packetData, dir(self.packetData))

        self.protocolData = None
        if self.packetData is not None:
            handler = meshtastic.protocols.get(self.packetData.portnum)
            pb = None
            if handler and handler.protobufFactory:
                pb = handler.protobufFactory()
            else:
                pb = None

            if pb is not None:
                try:
                    pb.ParseFromString(self.packetData.payload)
                    self.protocolData = pb
                except:
                    self.protocolData = None
                    import traceback
                    traceback.print_exc()

    def print(self):
        print("Dest:", self.dest)
        print("Sender:", self.sender)
        print("Packet ID:", self.packetID)
        print("Flags:", self.flags)
        print("Channel Hash:", self.channelHash)
        print("Next Hop:", self.nextHop)
        print("Relay Node:", self.relayNode)
        print("Encrypted Payload:", self.encryptedPayload)
        print("Packet Payload:", self.packetPayload)
        print("Packet Data:", self.packetData)
        print("Protocol Payload:", self.packetData.payload)
        print("Protocol Data:", self.protocolData)


def main():
    from sx127x import SX127x
    from datetime import datetime

    sx = SX127x(1)
    sx.standby()

    # TW
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

    while True:
        sx.receive()
        crcError = sx.wait_data()
        if crcError is None:
            print("Timeout")
            continue

        data = sx.read_payload()
        print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), "NG" if crcError else "OK", data)
        data = MeshPacket(data, DEFAULT_KEY)
        data.print()

if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        # nodeinfo_app
        # data = b"\xff\xff\xff\xffp\x87\xa8\xbba\x1a\xb7\xd9c\x08\x00\x00\x18]\xc9\xbe\xc7\xe3q\xf5\xbf8$\xe8-\xcf\xb6\x8f\x96sz\x02W\x12\x11\x15\xffs\x16\xb7\xd3o\x84\xf3\xc4\x074=Y\xafu\xa9a\x90\x07&\x94\xa1\x1b\xe5oxb^j'S\x03\xb5\x04\xd7\xe9\xf6\x8e\x16\xed\xaf\x9e\x86\xe5@Z\xf1\x90\r\x90\xac\xc5\x83\xb5\x10hC\xef\xfd\xe3\xea\xce"

        # text message
        data = b'\xff\xff\xff\xffp\x87\xa8\xbb\xe0\xa5/^c\x08\x00\x00\x01\x8ey=\x87\xfc4\xdc\xbd#'
        data = MeshPacket(data, DEFAULT_KEY)
        data.print()
    else:
        main()
