import sys
import radio
import time
from node import *
from channel import *
from packet import DEFAULT_KEY, MeshPacket
import threading
import meshtastic.protobuf.config_pb2
from common import *
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
import models
import json
import os
import configparser

BASE_DIR = os.path.dirname(__file__)

DEVICE_HARDWARE = json.load(open(os.path.join(BASE_DIR, "Meshtastic-Android/app/src/main/assets/device_hardware.json")))

RETRY_INTERVAL = 7
PACKET_LOOKBACK_TTL = 30
NODE_INFO_REPORT_INTERVAL = 3600

def bool_from_str(s):
    return s.lower()[0] in "yt1" if s else False

class PendingTX():
    def __init__(self, packetID, payload, retry):
        self.packetID = packetID
        self.payload = payload
        self.retry = retry
        self.last = 0
        self.acked = 0

class Client():
    def __init__(self, device, cfg):
        self.device = device
        self.state = State()

        self.addr = bytes.fromhex(cfg["macaddr"])[-4:][::-1]
        self.mute = bool_from_str(cfg["mute"])
        self.state.short_name = cfg["short_name"]
        self.state.long_name = cfg["long_name"]
        self.state.macaddr = bytes.fromhex(cfg["macaddr"])
        self.state.hw_model = int(cfg["hw_model"])
        self.state.is_licensed = bool_from_str(cfg["is_licensed"])
        self.state.public_key = bytes.fromhex(cfg["public_key"])

        print("Address", self.addr[::-1].hex())
        print("Short Name", self.state.short_name)
        print("Long Name", self.state.long_name)
        print("MAC Address", self.state.macaddr.hex())
        print("HW Model", self.state.hw_model)
        print("Is Licensed", self.state.is_licensed)
        print("Public Key", self.state.public_key.hex())

        self.state.lat = 0
        self.state.lng = 0
        self.state.channels = []
        self.state.channels.append(Channel(radio.Meshtastic.BROADCAST_ADDR.hex(), "Public Channel"))
        self.state.nodes = {}
        self.txPool = []
        self.thread = threading.Thread(target=self.looper, daemon=True)
        self.thread.start()
        self.last_node_info_report = 0
        self.db = create_engine('sqlite:///meshtastic.db')
        self.checkout()

    def checkout(self):
        with Session(self.db) as sess:
            for n in sess.execute(select(models.Node).order_by(models.Node.id)).scalars():
                node = Node(n.id)
                node.state.short_name = n.short_name
                node.state.long_name = n.long_name
                node.state.macaddr = n.macaddr
                node.state.hw_model = n.hw_model
                node.state.public_key = n.public_key
                node.state.lat = n.latitude
                node.state.lng = n.longitude
                node.state.alt = n.altitude
                self.state.nodes[bytes.fromhex(n.id)] = node

    def looper(self):
        from datetime import datetime
        while True:
            self.device.receive()

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
                        p.acked = time.time()
                else:
                    Node.handle(self, packet, time.time())
                    if not self.mute:
                        rebroadcast = packet.rebroadcast()
                        if rebroadcast:
                            self.txPool.append(PendingTX(packet.packetID, rebroadcast, 2))

            now = time.time()
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
            elif now - self.last_node_info_report > NODE_INFO_REPORT_INTERVAL:
                self.last_node_info_report = now
                self.sendNodeInfo()

    def sendNodeInfo(self):
        packetPayload = mesh_pb2.Data()
        packetPayload.portnum = portnums_pb2.PortNum.NODEINFO_APP
        user = mesh_pb2.User()
        user.id = "!" + self.addr.hex()
        user.short_name = self.state.short_name
        user.long_name = self.state.long_name
        user.macaddr = self.state.macaddr
        user.hw_model = self.state.hw_model
        user.is_licensed = self.state.is_licensed
        user.role = meshtastic.protobuf.config_pb2.Config.DeviceConfig.Role.CLIENT
        user.public_key = self.state.public_key

        packetPayload.payload = user.SerializeToString()
        packetPayload.want_response = False
        packetPayload.dest = 0
        packetPayload.source = 0
        packetPayload.request_id = 0
        packetPayload.reply_id = 0
        packetPayload.emoji = 0
        packetPayload.bitfield = 0
        packet = MeshPacket.new(radio.Meshtastic.BROADCAST_ADDR, self.addr, packetPayload, DEFAULT_KEY)
        self.txPool.append(PendingTX(packet.packetID, packet.bytes, 2))

    def updateNode(self, node):
        with Session(self.db) as sess:
            n = models.Node(
                id=node.id,

                short_name=node.state.short_name,
                long_name=node.state.long_name,
                macaddr=node.state.macaddr,
                hw_model=node.state.hw_model,
                public_key=node.state.public_key,

                latitude=node.state.lat,
                longitude=node.state.lng,
                altitude=node.state.alt,
            )
            sess.merge(n)
            sess.commit()

    def send(self, dest, message):
        if type(dest) is str:
            dest = bytes.fromhex(dest)
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
        node = Node.get(self.state.nodes, dest)
        node.state.messages.append(Message(dest, self.addr, message, time.time()))

class App(Application):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.state = State()
        self.state.edit = ""
        self.state.focus = self.client.state.channels[0]

    def content(self):
        with Window(title="Meshtastic.py", size=(640, 480)):
            with HBox():
                with VBox().layout(weight=1):
                    with Scroll().layout(weight=1):
                        with VBox():
                            for channel in self.client.state.channels:
                                l = Label(f"{channel.state.name}").click(self.select, channel)
                                if self.state.focus is channel:
                                    l.style(bgColor=0x555555)
                            for node in self.client.state.nodes.values():
                                if node.state.short_name is None:
                                    continue
                                l = Label(f"{node.state.long_name}").click(self.select, node)
                                if self.state.focus is node:
                                    l.style(bgColor=0x555555)
                            Spacer()

                    if isinstance(self.state.focus, Node):
                        with VBox():
                            Label(f"ID: {self.state.focus.node_id}")
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
                    with Scroll().layout(weight=1).scrollY(Scroll.END):
                        with VBox():
                            Spacer()
                            for message in self.state.focus.state.messages:
                                if message.sender == self.client.addr:
                                    with HBox():
                                        Spacer()
                                        Label(message.text)
                                else:
                                    with HBox():
                                        Label(message.text)
                                        Spacer()
                    with HBox():
                        TextField(self.state("edit")).layout(weight=1)
                        Button("Send").click(self.sendMessage)

    def sendMessage(self, e):
        if self.state.edit == "":
            return
        self.client.send(self.state.focus.id, self.state.edit)
        self.state.edit = ""

    def select(self, e, item):
        self.state.focus = item

def main():
    from alembic.config import Config
    from alembic import command

    command.upgrade(Config(os.path.join(BASE_DIR, "alembic.ini")), "head")

    cfg = configparser.ConfigParser(inline_comment_prefixes="#")
    cfg.read(os.path.join(BASE_DIR, "meshtastic.ini"))
    print(dict(cfg["meshtastic"]))

    adapter = cfg["interface"]["adapter"]
    if adapter == "sx127x":
        from sx127x import SX127x
        sx = SX127x(0)
        sx.standby()
        sx.setMeshtastic(cfg["radio"]["region"], cfg["radio"]["preset"], cfg["radio"]["slot"])
    else:
        raise Exception(f"Unsupported adapter: {adapter}")

    client = Client(sx, cfg["meshtastic"])

    app = App(client)
    app.run()

if __name__ == "__main__":
    main()
