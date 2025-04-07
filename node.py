from meshtastic.protobuf import mesh_pb2, portnums_pb2
from common import *
import os
import json

DEVICE_HARDWARE = json.load(open(os.path.join(os.path.dirname(__file__), "Meshtastic-Android/app/src/main/assets/device_hardware.json")))

class Node():
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
    def get(cls, pool, id):
        node = pool.get(id)
        if node is None:
            node = cls(id)
            pool[id] = node
        return node

    @classmethod
    def handle(cls, pool, packet):
        if not packet.packetData:
            return
        if packet.packetData.portnum == portnums_pb2.PortNum.POSITION_APP:
            if not packet.protocolData:
                return
            node = cls.get(pool, packet.sender)
            node.state.lat = packet.protocolData.latitude_i
            node.state.lng = packet.protocolData.longitude_i
            node.state.alt = packet.protocolData.altitude
        elif packet.packetData.portnum == portnums_pb2.PortNum.NODEINFO_APP:
            if not packet.protocolData:
                return
            node = cls.get(pool, packet.sender)
            node.state.id = packet.protocolData.id
            node.state.long_name = packet.protocolData.long_name
            node.state.short_name = packet.protocolData.short_name
            node.state.macaddr = packet.protocolData.macaddr.hex()
            # node.state.hw_model = mesh_pb2.HardwareModel.Name(packet.protocolData.hw_model)
            models = [m for m in DEVICE_HARDWARE if m["hwModel"] == packet.protocolData.hw_model]
            if len(models) > 0:
                model = models[0]
                node.state.hw_model = model["displayName"]
            else:
                node.state.hw_model = f"Unknown ({packet.protocolData.hw_model})"
            node.state.public_key = packet.protocolData.public_key.hex()
        elif packet.packetData.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            node = cls.get(pool, packet.sender)
            node.state.messages.append(packet.packetData.payload.decode("utf-8"))