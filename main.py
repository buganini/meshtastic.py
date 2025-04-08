import sys
import radio
import time
from node import *
from packet import DEFAULT_KEY, MeshPacket
import threading
from common import *
from sqlalchemy import create_engine
import json

DEVICE_HARDWARE = json.load(open(os.path.join(os.path.dirname(__file__), "Meshtastic-Android/app/src/main/assets/device_hardware.json")))

RETRY_INTERVAL = 7
PACKET_LOOKBACK_TTL = 30
class PendingTX():
    def __init__(self, packetID, payload, retry):
        self.packetID = packetID
        self.payload = payload
        self.retry = retry
        self.last = 0
        self.acked = 0

class Client():
    def __init__(self, device, addr):
        self.device = device
        self.addr = addr
        self.state = State()
        self.state.nodes = {}
        self.txPool = []
        self.thread = threading.Thread(target=self.looper, daemon=True)
        self.thread.start()

    def looper(self):
        from datetime import datetime
        while True:
            self.device.receive()

            now = time.time()

            # print("Receive")
            crcError = self.device.wait_rx()
            # print("Wait rx")

            if crcError is not None:
                payload = self.device.read_payload()
                print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), "NG" if crcError else "OK", payload)
                if len(payload) < 16:
                    continue

                packet = MeshPacket.parse(payload, DEFAULT_KEY)
                packet.print()

                prev = [p for p in self.txPool if p.packetID == packet.packetID]
                if prev:
                    for p in prev:
                        p.acked = now
                else:
                    Node.handle(self.state.nodes, packet)
                    rebroadcast = packet.rebroadcast()
                    if rebroadcast:
                        self.txPool.append(PendingTX(packet.packetID, rebroadcast, 2))

            self.txPool = [p for p in self.txPool if p.acked==0 or now - p.acked < PACKET_LOOKBACK_TTL]

            todo = [p for p in self.txPool if p.acked==0 and p.retry>0]
            # print("Todo", len(todo))
            todo.sort(key=lambda x:x.last)
            if todo:
                p = todo[0]
                if now - p.last > RETRY_INTERVAL:
                    print(f"Send retry={p.retry} {p.payload}")
                    self.device.send(p.payload)
                    p.last = now
                    p.retry -= 1

    def send(self, dest, message):
        packetPayload = mesh_pb2.Data()
        packetPayload.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        packetPayload.payload = message.encode("utf-8")
        packetPayload.want_response = False
        packetPayload.dest = 0
        packetPayload.source = 0
        packetPayload.request_id = 0
        packetPayload.reply_id = 0
        packetPayload.emoji = 0
        packetPayload.bitfield = 0
        packet = MeshPacket.new(dest, self.addr, packetPayload, DEFAULT_KEY)
        self.txPool.append(PendingTX(packet.packetID, packet.bytes, 3))

class App(Application):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.state = State()
        self.state.edit = ""
        self.state.focus = None

    def content(self):
        with Window(size=(640, 480)):
            with HBox():
                with VBox().layout(weight=1):
                    with Scroll().layout(weight=1):
                        with VBox():
                            for node in self.client.state.nodes.values():
                                if node.state.id is None:
                                    continue
                                Label(f"{node.state.long_name}").click(self.selectNode, node)
                            Spacer()

                    if self.state.focus:
                        with VBox():
                            Label(f"ID: {self.state.focus.state.id}")
                            Label(f"Short Name: {self.state.focus.state.short_name}")
                            Label(f"Long Name: {self.state.focus.state.long_name}")
                            Label(f"MAC Address: {self.state.focus.state.macaddr}")
                            # hw_model = mesh_pb2.HardwareModel.Name(packet.protocolData.hw_model)
                            models = [m for m in DEVICE_HARDWARE if m["hwModel"] == self.state.focus.state.hw_model]
                            if len(models) > 0:
                                model = models[0]
                                hw_model = model["displayName"]
                            else:
                                hw_model = f"Unknown ({self.state.focus.state.hw_model})"
                            Label(f"Hardware Model: {hw_model}")
                            Label(f"Latitude: {self.state.focus.state.lat}")
                            Label(f"Longitude: {self.state.focus.state.lng}")
                            Label(f"Altitude: {self.state.focus.state.alt}")

                with VBox().layout(weight=3):
                    Spacer()
                    with HBox():
                        TextField(self.state("edit"), self.state("edit"))
                        Button("Send").click(self.sendMessage)

    def sendMessage(self, e):
        if self.state.edit == "":
            return
        self.client.send(radio.Meshtastic.BROADCAST_ADDR, self.state.edit)
        self.state.edit = ""

    def selectNode(self, e, node):
        self.state.focus = node

def main():
    from sx127x import SX127x

    sx = SX127x(0)
    sx.standby()
    sx.setMeshtastic("TW", "LONG_FAST")

    client = Client(sx, b"\x66\x55\x66\x55")

    app = App(client)
    app.run()

if __name__ == "__main__":
    main()
