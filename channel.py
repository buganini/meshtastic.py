from meshtastic.protobuf import mesh_pb2, portnums_pb2
from common import *

class Channel():
    def __init__(self, id, name):
        self.id = id
        self.state = State()
        self.state.name = name

        self.state.messages = []
