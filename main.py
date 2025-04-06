import sys
import radio
import time
from packet import DEFAULT_KEY, MeshPacket

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

    def run(self):
        from datetime import datetime
        self.device.receive()
        while True:
            now = time.time()

            print("Receive")
            crcError = self.device.wait_rx()
            print("Wait rx")

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
                    rebroadcast = packet.rebroadcast()
                    if rebroadcast:
                        self.txPool.append(PendingTX(packet.packetID, rebroadcast, 5))

            self.txPool = [p for p in self.txPool if p.acked==0 or now - p.acked < PACKET_LOOKBACK_TTL]

            todo = [p for p in self.txPool if p.acked==0]
            print("Todo", len(todo))
            todo.sort(key=lambda x:x.last)
            if todo:
                p = todo[0]
                if now - p.last > RETRY_INTERVAL:
                    print(f"Send retry={p.retry} {p.payload}")
                    self.device.send(p.payload)
                    p.last = now
                    p.retry -= 1

def main():
    from sx127x import SX127x

    sx = SX127x(0)
    sx.standby()
    sx.setMeshtastic("TW", "LONG_FAST")

    node = MeshtasticNode(sx)
    node.run()

if __name__ == "__main__":
    main()
