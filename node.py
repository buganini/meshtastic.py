from meshtastic.protobuf import portnums_pb2
from common import *

class Node():
    all = StateDict()

    def __init__(self, id):
        self.id = id
        self.state = State()
        self.state.id = None
        self.state.lat = None
        self.state.lng = None
        self.state.alt = None
        self.state.long_name = None
        self.state.short_name = None
        self.state.macaddr = None
        self.state.hw_model = None
        self.state.public_key = None
        self.state.messages = []
    @classmethod
    def get(cls, id):
        node = cls.all.get(id)
        if node is None:
            node = cls(id)
            cls.all[id] = node
        return node

    @classmethod
    def handle(cls, packet):
        if not packet.packetData:
            return
        if packet.packetData.portnum == portnums_pb2.PortNum.POSITION_APP:
            if not packet.protocolData:
                return
            node = cls.get(packet.sender)
            node.state.lat = packet.protocolData.latitude_i
            node.state.lng = packet.protocolData.longitude_i
            node.state.alt = packet.protocolData.altitude
        elif packet.packetData.portnum == portnums_pb2.PortNum.NODEINFO_APP:
            if not packet.protocolData:
                return
            node = cls.get(packet.sender)
            node.state.id = packet.protocolData.id
            node.state.long_name = packet.protocolData.long_name
            node.state.short_name = packet.protocolData.short_name
            node.state.macaddr = packet.protocolData.macaddr.hex()
            node.state.hw_model = packet.protocolData.hw_model
            node.state.public_key = packet.protocolData.public_key.hex()
        elif packet.packetData.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            node = cls.get(packet.sender)
            node.state.messages.append(packet.packetData.payload.decode("utf-8"))
