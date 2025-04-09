from meshtastic.protobuf import mesh_pb2, portnums_pb2
from common import *

class Message():
    def __init__(self, dest, sender, text, timestamp):
        self.dest = dest
        self.sender = sender
        self.text = text
        self.timestamp = timestamp

    def __str__(self):
        return f"{self.sender} -> {self.dest}: {self.text} ({self.timestamp})"
