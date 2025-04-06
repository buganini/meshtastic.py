import sys
import radio
import time
from node import *
from packet import DEFAULT_KEY, MeshPacket
import threading
from common import *

RETRY_INTERVAL = 1
PACKET_LOOKBACK_TTL = 30
class PendingTX():
    def __init__(self, packetID, payload, retry):
        self.packetID = packetID
        self.payload = payload
        self.retry = retry
        self.last = 0
        self.acked = 0

class MeshtasticNode():
    def __init__(self, device):
        self.device = device
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

                packet = MeshPacket(payload, DEFAULT_KEY)
                packet.print()

                prev = [p for p in self.txPool if p.packetID == packet.packetID]
                if prev:
                    for p in prev:
                        p.acked = now
                else:
                    Node.handle(packet)
                    rebroadcast = packet.rebroadcast()
                    if rebroadcast:
                        self.txPool.append(PendingTX(packet.packetID, rebroadcast, 5))

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

class App(Application):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.state = State()
        self.state.focus = None

    def content(self):
        with Window(size=(640, 480)):
            with HBox():
                with Scroll():
                    with VBox():
                        for node in Node.all.values():
                            Label(f"{node.state.id} {node.state.short_name}").click(self.selectNode, node)
                        Spacer()

                if self.state.focus:
                    with VBox():
                        Label(f"ID: {self.state.focus.state.id}")
                        Label(f"Short Name: {self.state.focus.state.short_name}")
                        Label(f"Long Name: {self.state.focus.state.long_name}")
                        Label(f"MAC Address: {self.state.focus.state.macaddr}")
                        Label(f"Hardware Model: {self.state.focus.state.hw_model}")
                        Label(f"Latitude: {self.state.focus.state.lat}")
                        Label(f"Longitude: {self.state.focus.state.lng}")
                        Label(f"Altitude: {self.state.focus.state.alt}")
                        Spacer()

    def selectNode(self, e, node):
        self.state.focus = node

def main():
    from sx127x import SX127x

    sx = SX127x(0)
    sx.standby()
    sx.setMeshtastic("TW", "LONG_FAST")

    node = MeshtasticNode(sx)

    app = App(node)
    app.run()

if __name__ == "__main__":
    main()
