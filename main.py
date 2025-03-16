import sys
import base64
from meshtastic.protobuf import mesh_pb2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class MeshPacket:
    def __init__(self, data, aesKey):
        self.dest = data[0:4]
        self.sender = data[4:8]
        self.packetID = data[8:12]
        self.flags = data[12:13]
        self.channelHash = data[13:14]
        self.nextHop = data[14:15]
        self.relayNode = data[15:16]
        self.data = data[16:len(data)]

        print("Dest:", self.dest)
        print("Sender:", self.sender)
        print("Packet ID:", self.packetID)
        print("Flags:", self.flags)
        print("Channel Hash:", self.channelHash)
        print("Next Hop:", self.nextHop)
        print("Relay Node:", self.relayNode)
        print("Data:", self.data)

        nonce = self.packetID + b'\x00\x00\x00\x00' + self.sender + b'\x00\x00\x00\x00'
        cipher = Cipher(algorithms.AES(base64.b64decode(aesKey.encode("ascii"))), modes.CTR(nonce), backend=default_backend())
        decryptor = cipher.decryptor()
        self.decrypted_data = decryptor.update(self.data) + decryptor.finalize()

        print("Decoded Data:", self.decrypted_data)
        self.pbdata = mesh_pb2.Data()
        try:
            self.pbdata.ParseFromString(self.decrypted_data)
        except:
            self.pbdata = None

        print("Protobuf Data:", self.pbdata)


def main():
    from sx127x import SX127x

    sx = SX127x(device)
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

if __name__ == "__main__":
    key = "1PG7OiApB1nwvP+rz05pAQ=="
    data = b"\xff\xff\xff\xffp\x87\xa8\xbba\x1a\xb7\xd9c\x08\x00\x00\x18]\xc9\xbe\xc7\xe3q\xf5\xbf8$\xe8-\xcf\xb6\x8f\x96sz\x02W\x12\x11\x15\xffs\x16\xb7\xd3o\x84\xf3\xc4\x074=Y\xafu\xa9a\x90\x07&\x94\xa1\x1b\xe5oxb^j'S\x03\xb5\x04\xd7\xe9\xf6\x8e\x16\xed\xaf\x9e\x86\xe5@Z\xf1\x90\r\x90\xac\xc5\x83\xb5\x10hC\xef\xfd\xe3\xea\xce"
    data = MeshPacket(data, key)
    print(data.pbdata)