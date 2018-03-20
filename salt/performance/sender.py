import logging

import time
import zmq

from salt.utils import json

log = logging.getLogger(__name__)


class JsonRenderer(object):
    def marshal(self, smth):
        return json.dumps(smth)


# FIXME [KN] refactor to use salt.transport.zmq instead
class ZmqSender(object):
    def __init__(self, json_renderer, zmq_host='localhost', zmq_port=9900):
        self.json_renderer = json_renderer
        log.debug("ZMQ version: {}".format(zmq.zmq_version()))

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.SNDBUF, 102400)
        self.socket.setsockopt(zmq.LINGER, 2000)

        self.socket.set_hwm(10240)

        zmq_address = "tcp://%s:%d" % (zmq_host, zmq_port)
        log.info("Connecting to ZMQ at address: %s" % zmq_address)

        self.socket.connect(zmq_address)
        time.sleep(2)

    def send(self, payload):
        out_str = self.json_renderer.marshal(payload)
        log.debug("Sent message: {}".format(out_str))
        self.socket.send_unicode("{} {}".format("topic", out_str))

    def close(self):
        self.socket.close()
        self.context.destroy(linger=3000)
