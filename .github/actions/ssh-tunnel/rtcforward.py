import argparse
import asyncio
import base64
import concurrent
import io
import json
import logging
import os
import sys
import textwrap
import time

aiortc = None
try:
    import aiortc.exceptions
    from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
except ImportError:
    pass

uvloop = None
try:
    import uvloop
except ImportError:
    pass

if sys.platform == "win32":
    if not aiortc:
        print("Please run 'pip install aiortc' and try again.")
        sys.exit(1)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    if not aiortc or not uvloop:
        print("Please run 'pip install aiortc uvloop' and try again.")
        sys.exit(1)
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


log = logging.getLogger(__name__)


def object_from_string(message_str):
    message = json.loads(message_str)
    if message["type"] in ["answer", "offer"]:
        return RTCSessionDescription(**message)
    elif message["type"] == "candidate" and message["candidate"]:
        candidate = candidate_from_sdp(message["candidate"].split(":", 1)[1])
        candidate.sdpMid = message["id"]
        candidate.sdpMLineIndex = message["label"]
        return candidate
    elif message["type"] == "bye":
        return BYE


def object_to_string(obj):
    if isinstance(obj, RTCSessionDescription):
        message = {"sdp": obj.sdp, "type": obj.type}
    elif isinstance(obj, RTCIceCandidate):
        message = {
            "candidate": "candidate:" + candidate_to_sdp(obj),
            "id": obj.sdpMid,
            "label": obj.sdpMLineIndex,
            "type": "candidate",
        }
    else:
        assert obj is BYE
        message = {"type": "bye"}
    return json.dumps(message, sort_keys=True)


def print_pastable(data, message="offer"):
    print(f"-- {message} --")
    sys.stdout.flush()
    print(f"{data}")
    sys.stdout.flush()
    print(f"-- end {message} --")
    sys.stdout.flush()


class ProxyClient:

    def __init__(self, args, channel):
        self.args = args
        self.channel = channel

    def start(self):
        self.channel.on("message")(self.on_message)

    def on_message(self, message):
        msg = json.loads(message)
        key = msg["key"]
        data = msg["data"]
        log.debug("new connection messsage %s", key)

        pc = RTCPeerConnection()

        @pc.on("datachannel")
        def on_channel(channel):
            log.info("Sub channel established %s", key)
            asyncio.ensure_future(self.handle_channel(channel))

        async def finalize_connection():
            obj = object_from_string(data)
            if isinstance(obj, RTCSessionDescription):
                await pc.setRemoteDescription(obj)
                if obj.type == "offer":
                    # send answer
                    await pc.setLocalDescription(await pc.createAnswer())
                    msg = {"key": key, "data": object_to_string(pc.localDescription)}
                    self.channel.send(json.dumps(msg))
            elif isinstance(obj, RTCIceCandidate):
                await pc.addIceCandidate(obj)
            elif obj is BYE:
                log.warning("Exiting")

        asyncio.ensure_future(finalize_connection())

    async def handle_channel(self, channel):
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", self.args.port)
            log.info("opened connection to port %s", self.args.port)

            @channel.on("message")
            def on_message(message):
                log.debug("rtc to socket %r", message)
                writer.write(message)
                asyncio.ensure_future(writer.drain())

            while True:
                data = await reader.read(100)
                if data:
                    log.debug("socket to rtc %r", data)
                    channel.send(data)
        except Exception:
            log.exception("WTF4")


class ProxyServer:

    def __init__(self, args, channel):
        self.args = args
        self.channel = channel
        self.connections = {}

    async def start(self):
        @self.channel.on("message")
        def handle_message(message):
            asyncio.ensure_future(self.handle_message(message))

        self.server = await asyncio.start_server(
            self.new_connection, "127.0.0.1", self.args.port
        )
        log.info("Listening on port %s", self.args.port)
        async with self.server:
            await self.server.serve_forever()

    async def handle_message(self, message):
        msg = json.loads(message)
        key = msg["key"]
        pc = self.connections[key].pc
        channel = self.connections[key].channel
        obj = object_from_string(msg["data"])
        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)
            if obj.type == "offer":
                # send answer
                await pc.setLocalDescription(await pc.createAnswer())
                msg = {
                    "key": key,
                    "data": object_to_string(pc.localDescription),
                }
                self.channel.send(json.dumps(msg))
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")

    async def new_connection(self, reader, writer):
        try:
            info = writer.get_extra_info("peername")
            key = f"{info[0]}:{info[1]}"
            log.info("Connection from %s", key)
            pc = RTCPeerConnection()
            channel = pc.createDataChannel("{key}")

            async def readerproxy():
                while True:
                    data = await reader.read(100)
                    if data:
                        log.debug("socket to rtc %r", data)
                        try:
                            channel.send(data)
                        except aiortc.exceptions.InvalidStateError:
                            log.error(
                                "Channel was in an invalid state %s, bailing reader coroutine",
                                key,
                            )
                            break

            @channel.on("open")
            def on_open():
                asyncio.ensure_future(readerproxy())

            @channel.on("message")
            def on_message(message):
                log.debug("rtc to socket %r", message)
                writer.write(message)
                asyncio.ensure_future(writer.drain())

            self.connections[key] = ProxyConnection(pc, channel)
            await pc.setLocalDescription(await pc.createOffer())
            msg = {
                "key": key,
                "data": object_to_string(pc.localDescription),
            }
            log.debug("Send new offer")
            self.channel.send(json.dumps(msg, sort_keys=True))
        except Exception:
            log.exception("WTF")


class ProxyConnection:
    def __init__(self, pc, channel):
        self.pc = pc
        self.channel = channel


async def read_from_stdin():
    loop = asyncio.get_event_loop()
    line = await loop.run_in_executor(
        None, input, "-- Please enter a message from remote party --\n"
    )
    data = line
    while line:
        try:
            line = await loop.run_in_executor(None, input)
        except EOFError:
            break
        data += line
    print("-- Message received --")
    return data


async def run_answer(pc, args):
    """
    Top level offer answer server.
    """

    @pc.on("datachannel")
    def on_datachannel(channel):
        log.info("Channel created")
        client = ProxyClient(args, channel)
        client.start()

    data = await read_from_stdin()
    data = base64.b64decode(data)
    obj = object_from_string(data)
    if isinstance(obj, RTCSessionDescription):
        log.debug("received rtc session description")
        await pc.setRemoteDescription(obj)
        if obj.type == "offer":
            await pc.setLocalDescription(await pc.createAnswer())
            data = object_to_string(pc.localDescription)
            data = base64.b64encode(data.encode())
            data = os.linesep.join(textwrap.wrap(data.decode(), 80))
            print_pastable(data, "reply")
    elif isinstance(obj, RTCIceCandidate):
        log.debug("received rtc ice candidate")
        await pc.addIceCandidate(obj)
    elif obj is BYE:
        print("Exiting")

    while True:
        await asyncio.sleep(0.3)


async def run_offer(pc, args):
    """
    Top level offer server this will estabilsh a data channel and start a tcp
    server on the port provided. New connections to the server will start the
    creation of a new rtc connectin and a new data channel used for proxying
    the client's connection to the remote side.
    """
    control_channel = pc.createDataChannel("main")
    log.info("Created control channel.")

    async def start_server():
        """
        Start the proxy server. The proxy server will create a local port and
        handle creation of additional rtc peer connections for each new client
        to the proxy server port.
        """
        server = ProxyServer(args, control_channel)
        await server.start()

    @control_channel.on("open")
    def on_open():
        """
        Start the proxy server when the control channel is connected.
        """
        asyncio.ensure_future(start_server())

    await pc.setLocalDescription(await pc.createOffer())

    data = object_to_string(pc.localDescription).encode()
    data = base64.b64encode(data)
    data = os.linesep.join(textwrap.wrap(data.decode(), 80))

    print_pastable(data, "offer")

    data = await read_from_stdin()
    data = base64.b64decode(data.encode())
    obj = object_from_string(data)
    if isinstance(obj, RTCSessionDescription):
        log.debug("received rtc session description")
        await pc.setRemoteDescription(obj)
        if obj.type == "offer":
            # send answer
            await pc.setLocalDescription(await pc.createAnswer())
            await signaling.send(pc.localDescription)
    elif isinstance(obj, RTCIceCandidate):
        log.debug("received rtc ice candidate")
        await pc.addIceCandidate(obj)
    elif obj is BYE:
        print("Exiting")

    while True:
        await asyncio.sleep(0.3)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description="Port proxy")
    parser.add_argument("role", choices=["offer", "answer"])
    parser.add_argument("--port", type=int, default=11224)
    parser.add_argument("--verbose", "-v", action="count", default=None)
    args = parser.parse_args()

    if args.verbose is None:
        logging.basicConfig(level=logging.WARNING)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    pc = RTCPeerConnection()
    if args.role == "offer":
        coro = run_offer(pc, args)
    else:
        coro = run_answer(pc, args)

    # run event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(pc.close())
