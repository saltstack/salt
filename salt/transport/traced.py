import logging

import salt.ext.tornado.gen
from salt.transport.client import AsyncReqChannel
from salt.transport.client import AsyncPubChannel
from salt.transport.ipc import IPCServer
from salt.transport.ipc import IPCMessageClient

log = logging.getLogger(__name__)


class TracedReqChannel(AsyncReqChannel):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject
        log.warning("%s.__init__", __class__)

    def send(self, load, tries=3, timeout=60, raw=False):
        log.warning("%s.send %s", __class__, load)
        reply = self.channel.send(load, tries, timeout, raw)
        log.warning("%s.send (reply) %s", __class__, reply)

        def callback(future):
            value = future.result()
            log.warning("%s.send (reply callback) %s", __class__, value)

        reply.add_done_callback(callback)

        return reply

    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        log.warning("%s.crypted_transfer_decode_dictentry %s", __class__, load)
        reply = self.channel.crypted_transfer_decode_dictentry(load, dictkey, tries, timeout)
        log.warning("%s.crypted_transfor_decode_dictentry (reply) %s", __class__, reply)

        def callback(future):
            value = future.result()
            log.warning("%s.crypted_transfer_decode_dictentry (reply callback) %s", __class__, value)

        reply.add_done_callback(callback)

        return reply

    def close(self):
        log.warning("%s.close", __class__)
        return self.channel.close()

    def __enter__(self):
        log.warning("%s.__enter__", __class__)
        return self.channel.__enter__()

    def __exit__(self, *args):
        log.warning("%s.__exit__", __class__)
        return self.channel.__exit__()


class TracedPubChannel(AsyncPubChannel):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject

    def connect(self):
        log.warning("%s.connect", __class__)
        return self.channel.connect()

    def on_recv(self, callback):
        log.warning("%s.on_recv %s", __class__, callback)

        def wrapped_callback(*args, **kwargs):
            log.warning("%s.wrapped_callback %s %s", __class__, args, kwargs)
            reply = callback(*args, **kwargs)
            log.warning("%s.wrapped_callback (reply) %s", __class__, reply)
            return reply

        if callback:
            return self.channel.on_recv(wrapped_callback)
        return self.channel.on_recv(None)

    def close(self):
        log.warning("%s.close", __class__)
        return self.channel.close()

    def __enter__(self):
        log.warning("%s.__enter__", __class__)
        return self.channel.__enter__()

    def __exit__(self, *args):
        log.warning("%s.__exit__", __class__)
        return self.channel.__exit__()


class TracedReqServerChannel(object):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject

    def pre_fork(self, process_manager):
        log.warning("%s.pre_fork %s", __class__, process_manager)
        return self.channel.pre_fork(process_manager)

    def post_fork(self, payload_handler, io_loop):
        log.warning("%s.post_fork %s %s", __class__, payload_handler, io_loop)

        def wrapped_payload_handler(*args, **kwargs):
            log.warning("%s.wrapped_payload_handler %s %s", __class__, args, kwargs)
            reply = payload_handler(*args, **kwargs)
            log.warning("%s.wrapped_payload_handler (reply) %s", __class__, reply)

            def callback(future):
                value = future.result()
                log.warning("%s.wrapped_payload_handler (reply callback) %s", __class__, value)

            reply.add_done_callback(callback)

            return reply

        if payload_handler:
            return self.channel.post_fork(wrapped_payload_handler, io_loop)
        return self.channel.post_fork(None, io_loop)


class TracedPubServerChannel(object):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject

    def pre_fork(self, process_manager, kwargs=None):
        log.warning("%s.pre_fork %s %s", __class__, process_manager, kwargs)
        return self.channel.pre_fork(process_manager, kwargs)

    def publish(self, load):
        log.warning("%s.publish %s", __class__, load)
        reply = self.channel.publish(load)
        log.warning("%s.publish (reply) %s", __class__, reply)
        return reply


class TracedPushChannel(IPCMessageClient):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject

    @salt.ext.tornado.gen.coroutine
    def send(self, msg, timeout=None, tries=None):
        log.warning("%s.send %s", __class__, msg)
        reply = yield self.channel.send(msg, timeout, tries)
        log.warning("%s.send (reply) %s", __class__, reply)
        return reply


class TracedPullChannel(IPCServer):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject

        # Wrap payload handler for IPC
        self.payload_handler = self.channel.payload_handler
        def wrapped_payload_handler(*args, **kwargs):
            log.warning("%s.wrapped_payload_handler %s %s", __class__, args, kwargs)
            reply = self.payload_handler(*args, **kwargs)
            log.warning("%s.wrapped_payload_handler (reply) %s", __class__, reply)
            return reply

        self.channel.payload_handler = wrapped_payload_handler
