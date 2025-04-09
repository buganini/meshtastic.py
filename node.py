from meshtastic.protobuf import mesh_pb2, portnums_pb2
from common import *
from message import Message
import time

class Node():
    def __init__(self, id):
        self.id = id
        self.state = State()

        self.state.long_name = None
        self.state.short_name = None
        self.state.macaddr = None
        self.state.hw_model = None
        self.state.public_key = None

        self.state.lat = None
        self.state.lng = None
        self.state.alt = None

        self.state.messages = []

    @property
    def node_id(self):
        return "!"+bytes.fromhex(self.id)[::-1].hex()

    @classmethod
    def get(cls, pool, id):
        node = pool.get(id)
        if node is None:
            node = cls(id.hex())
            pool[id] = node
        return node

    @classmethod
    def handle(cls, master, packet, timestamp):
        if not packet.packetData:
            return
        if packet.packetData.portnum == portnums_pb2.PortNum.POSITION_APP:
            if not packet.protocolData:
                return
            node = cls.get(master.state.nodes, packet.sender)
            node.state.lat = packet.protocolData.latitude_i
            node.state.lng = packet.protocolData.longitude_i
            node.state.alt = packet.protocolData.altitude
            master.updateNode(node)
        elif packet.packetData.portnum == portnums_pb2.PortNum.NODEINFO_APP:
            if not packet.protocolData:
                return
            node = cls.get(master.state.nodes, packet.sender)
            node.state.long_name = packet.protocolData.long_name
            node.state.short_name = packet.protocolData.short_name
            node.state.macaddr = packet.protocolData.macaddr.hex()
            node.state.hw_model = packet.protocolData.hw_model
            node.state.public_key = packet.protocolData.public_key.hex()
            master.updateNode(node)
        elif packet.packetData.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            node = cls.get(master.state.nodes, packet.sender)
            msg = Message(packet.dest, packet.sender, packet.packetData.payload.decode("utf-8"), timestamp)
            node.state.messages.append(msg)