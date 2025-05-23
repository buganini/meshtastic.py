import base64
import meshtastic
from meshtastic.protobuf import mesh_pb2, portnums_pb2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import random

DEFAULT_KEY = "1PG7OiApB1nwvP+rz05pAQ=="

class MeshPacket:
    @classmethod
    def new(cls, dest, sender, packet, aesKey):
        self = cls()
        self.aesKey = aesKey
        self.dest = dest
        self.sender = sender
        self.packetID = bytes(random.randint(0, 255) for _ in range(4))
        self.packetData = packet
        self.hopLimit = 3
        self.wantAck = 0
        self.viaMQTT = 0
        self.hopStart = 3
        self.channelHash = b"\x08"
        self.nextHop = b"\x00"
        self.relayNode = b"\x00"
        self.rssi = None
        self.snr = None
        return self

    @property
    def bytes(self):
        self.packetPayload = self.packetData.SerializeToString()
        nonce = self.packetID + b'\x00\x00\x00\x00' + self.sender + b'\x00\x00\x00\x00'
        cipher = Cipher(algorithms.AES(base64.b64decode(self.aesKey.encode("ascii"))), modes.CTR(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        self.encryptedPayload = encryptor.update(self.packetPayload) + encryptor.finalize()
        self.flags = ((self.hopLimit & 0b111) << 5) | ((self.viaMQTT & 0b1) << 4) | ((self.wantAck & 0b1) << 3) | (self.hopLimit & 0b111)
        return self.dest + self.sender + self.packetID + bytes([self.flags]) + self.channelHash + self.nextHop + self.relayNode + self.encryptedPayload

    @classmethod
    def parse(cls, data, aesKey):
        self = cls()
        self.aesKey = aesKey
        self.dest = data[0:4]
        self.sender = data[4:8]
        self.packetID = data[8:12]
        self.flags = data[12:13][0]
        self.hopLimit = self.flags & 0b111
        self.wantAck = (self.flags >> 3) & 0b1
        self.viaMQTT = (self.flags >> 4) & 0b1
        self.hopStart = (self.flags >> 5) & 0b111
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

        return self

    def rebroadcast(self):
        if self.hopLimit == 0:
            return None
        else:
            flags = self.hopLimit << 5
            flags |= self.viaMQTT << 4
            flags |= self.wantAck << 3
            flags |= (self.hopLimit - 1)
            return self.dest + self.sender + self.packetID + bytes([flags]) + self.channelHash + self.nextHop + self.relayNode + self.encryptedPayload

    def print(self):
        print("Dest:", self.dest.hex())
        print("Sender:", self.sender.hex())
        print("Packet ID:", self.packetID.hex())
        # print("Flags:", self.flags)
        print("Hop Limit:", self.hopLimit)
        print("Want Ack:", self.wantAck)
        print("Via MQTT:", self.viaMQTT)
        print("Hop Start:", self.hopStart)
        print("Channel Hash:", self.channelHash)
        print("Next Hop:", self.nextHop)
        print("Relay Node:", self.relayNode)
        print("Encrypted Payload:", self.encryptedPayload)
        print("Packet Payload:", self.packetPayload)

        if self.packetData:
            print(f"Packet Data: {type(self.packetData)} {{")
            for descriptor in self.packetData.DESCRIPTOR.fields:
                value = getattr(self.packetData, descriptor.name)
                if descriptor.type == descriptor.TYPE_ENUM:
                    try:
                        value = descriptor.enum_type.values[value].name
                    except:
                        value = f"Unknown ({value})"
                print(f"    {descriptor.name}: {value}")
            print("}")

        if self.packetData:
            print("Protocol Payload:", self.packetData.payload)

        if self.protocolData:
            print(f"Protocol Data: {type(self.protocolData)} {{")
            for descriptor in self.protocolData.DESCRIPTOR.fields:
                value = getattr(self.protocolData, descriptor.name)
                if descriptor.type == descriptor.TYPE_ENUM:
                    try:
                        value = descriptor.enum_type.values[value].name
                    except:
                        value = f"Unknown ({value})"
                print(f"    {descriptor.name}: {value}")
            print("}")

if __name__ == "__main__":
    # nodeinfo_app
    # data = b"\xff\xff\xff\xffp\x87\xa8\xbba\x1a\xb7\xd9c\x08\x00\x00\x18]\xc9\xbe\xc7\xe3q\xf5\xbf8$\xe8-\xcf\xb6\x8f\x96sz\x02W\x12\x11\x15\xffs\x16\xb7\xd3o\x84\xf3\xc4\x074=Y\xafu\xa9a\x90\x07&\x94\xa1\x1b\xe5oxb^j'S\x03\xb5\x04\xd7\xe9\xf6\x8e\x16\xed\xaf\x9e\x86\xe5@Z\xf1\x90\r\x90\xac\xc5\x83\xb5\x10hC\xef\xfd\xe3\xea\xce"

    # text message
    data = b'\xff\xff\xff\xffp\x87\xa8\xbb\xe0\xa5/^c\x08\x00\x00\x01\x8ey=\x87\xfc4\xdc\xbd#'
    data = MeshPacket.parse(data, DEFAULT_KEY)
    data.print()

    packet = mesh_pb2.Data()
    packet.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
    packet.payload = b"roundtrip"
    packet.want_response = False
    packet.dest = 0
    packet.source = 0
    packet.request_id = 0
    packet.reply_id = 0
    packet.emoji = 0
    packet.bitfield = 0
    packet = MeshPacket.new(b"\xff\xff\xff\xff", b"\x66\x55\x66\x55", packet, DEFAULT_KEY)
    data = packet.bytes
    print(data)

    parsed = MeshPacket.parse(data, DEFAULT_KEY)
    parsed.print()