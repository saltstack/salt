from __future__ import absolute_import, print_function, unicode_literals

import logging
import typing

import salt.ext.tornado.gen
from salt.ext.tornado.concurrent import Future

from salt.transport.client import AsyncReqChannel
from salt.transport.client import AsyncPubChannel
from salt.transport.ipc import IPCMessageServer
from salt.transport.ipc import IPCMessageClient
from salt.transport.ipc import IPCMessagePublisher
from salt.transport.ipc import IPCMessageSubscriber

from opentelemetry import context, propagators, trace
from opentelemetry.trace.status import Status, StatusCanonicalCode

from salt.utils.tracing import setup_jaeger


def get_header_from_dict(scope: dict, header_name: str) -> typing.List[str]:
    try:
        return [scope[header_name]]
    except KeyError:
        return []

def set_header_into_dict(dicty, key, value):
    dicty[key] = value

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
        return self._traced_helper(self.channel.send, load, tries, timeout, raw)

    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        return self._traced_helper(self.channel.crypted_transfer_decode_dictentry, load, dictkey, tries, timeout)

    def _traced_helper(self, method, load, *args, **kwargs):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)

        span_name = "TracedReqChannel." + method.__name__

        attributes = {
            key: str(value) for key, value in load.items()
            if key in ['id', 'cmd', 'data', 'tag', 'tgt', 'fun', 'arg', 'user']
        }
        attributes.update({'raw_' + key: str(value) for key, value in load.items()})
        attributes['raw'] = str(load)
        send = tracer.start_span(span_name, kind=trace.SpanKind.PRODUCER, attributes=attributes)
        with tracer.use_span(send, end_on_exit=False):
            with tracer.start_as_current_span(span_name + "(calling send)", kind=trace.SpanKind.INTERNAL, parent=send, attributes=attributes) as span:
                propagators.inject(set_header_into_dict, load)
                reply = method(load, *args, **kwargs)
            # Start a span to register callback wait time
            waiting_for_callback = tracer.start_span(span_name + "(waiting for callback)", kind=trace.SpanKind.INTERNAL, parent=send)

            wrapped_reply = Future()

            def callback(future):
                # No longer waiting for a callback
                waiting_for_callback.end()
                # Fetch result and call all handlers via set_result
                value = future.result()
                attributes = {}
                if value:
                    attribute_dict = value['load'].items() if 'load' in value else value.items()
                    attributes = {
                        key: str(value) for key, value in attribute_dict
                        if key in ['jid', 'minions']
                    }
                    attributes.update({'raw_' + key: str(value) for key, value in attribute_dict})
                attributes['raw'] = str(value)
                with tracer.start_as_current_span(span_name + "(callback)", kind=trace.SpanKind.INTERNAL, parent=send, attributes=attributes) as span:
                    log.warning("%s.send (reply callback) %s", __class__, value)
                    wrapped_reply.set_result(value)
                # Finish top-level
                send.set_status(Status(StatusCanonicalCode.OK))
                send.end()

            reply.add_done_callback(callback)

            return wrapped_reply

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
        log.warning("%s.__init__", __class__)

    def connect(self):
        log.warning("%s.connect", __class__)
        return self.channel.connect()

    def on_recv(self, callback):
        log.warning("%s.on_recv %s", __class__, callback)

        def wrapped_callback(*args, **kwargs):
            log.warning("%s.wrapped_callback %s %s", __class__, args, kwargs)

            load = args[0]['load']
            if 'traceparent' in load:
                print("Parent:", load['traceparent'])

            setup_jaeger()
            token = context.attach(
                propagators.extract(get_header_from_dict, load)
            )
            span_name = "TracedPubChannel.wrapped_callback"
            reply = None
            try:
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(
                    span_name,
                    kind=trace.SpanKind.CONSUMER,
                ):
                    reply = callback(*args, **kwargs)
                    log.warning("%s.wrapped_callback (reply) %s", __class__, reply)
            finally:
                context.detach(token)
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
        log.warning("%s.__init__", __class__)

    def pre_fork(self, process_manager):
        log.warning("%s.pre_fork %s", __class__, process_manager)
        return self.channel.pre_fork(process_manager)

    def post_fork(self, payload_handler, io_loop):
        log.warning("%s.post_fork %s %s", __class__, payload_handler, io_loop)

        def wrapped_payload_handler(*args, **kwargs):
            log.warning("%s.wrapped_payload_handler %s %s", __class__, args, kwargs)

            load = args[0]['load']
            if 'traceparent' in load:
                print("Parent:", load['traceparent'])

            setup_jaeger()
            token = context.attach(
                propagators.extract(get_header_from_dict, load)
            )
            span_name = "TracedReqServerChannel.payload_handler"

            attributes = {
                key: str(value) for key, value in load.items()
                if key in ['cmd', 'id', 'jiq', 'return', 'retcode', 'fun', 'fun_args', 'data', 'tag', 'tgt', 'arg', 'user']
            }
            attributes.update({'raw_' + key: str(value) for key, value in load.items()})
            attributes['raw'] = str(load)

            reply = None
            try:
                tracer = trace.get_tracer(__name__)
                send = tracer.start_span(span_name, kind=trace.SpanKind.PRODUCER, attributes=attributes)
                with tracer.start_as_current_span(span_name + "(running handler)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
                    reply = payload_handler(*args, **kwargs)
                child = tracer.start_span(span_name + "(waiting for callback)", kind=trace.SpanKind.INTERNAL, parent=send)
                wrapped_reply = Future()

                def callback(future):
                    child.end()
                    value = future.result()
                    attributes = {}
                    if type(value) == "dict":
                        attribute_dict = value['load'].items() if 'load' in value else value.items()
                        attributes = {
                            key: str(value) for key, value in attribute_dict
                            if key in ['jid', 'minions']
                        }
                        attributes.update({'raw_' + key: str(value) for key, value in attribute_dict})
                    attributes['raw'] = str(value)
                    log.warning("%s.send (reply callback) %s", __class__, value)
                    with tracer.start_as_current_span(span_name + "(callback)", kind=trace.SpanKind.INTERNAL, parent=send, attributes=attributes) as span:
                        wrapped_reply.set_result(value)
                    send.set_status(Status(StatusCanonicalCode.OK))
                    send.end()

                reply.add_done_callback(callback)

                return wrapped_reply
            finally:
                context.detach(token)
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
        log.warning("%s.__init__", __class__)

    def pre_fork(self, process_manager, kwargs=None):
        log.warning("%s.pre_fork %s %s", __class__, process_manager, kwargs)
        return self.channel.pre_fork(process_manager, kwargs)

    def publish(self, load):
        log.warning("%s.publish %s", __class__, load)

        setup_jaeger()
        tracer = trace.get_tracer(__name__)

        span_name = "TracedPubServerChannel.publish"

        attributes = {
            key: str(value) for key, value in load.items()
            if key in ['fun', 'jid', 'user']
        }
        attributes.update({'raw_' + key: str(value) for key, value in load.items()})
        attributes['raw'] = str(load)
        with tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.PRODUCER,
            attributes=attributes,
        ):
            propagators.inject(set_header_into_dict, load)
            log.warning("%s.publish modified %s", __class__, load)

            reply = self.channel.publish(load)
            print(type(reply))
            log.warning("%s.publish (reply) %s", __class__, reply)
            return reply


# TODO: IPCClient, IPCServer

class TracedPushChannel(IPCMessageClient):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject
        log.warning("%s.__init__", __class__)

    @salt.ext.tornado.gen.coroutine
    def send(self, msg, timeout=None, tries=None):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)
        span_name = "TracedPushChannel.send"
        with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL):
            reply = self.channel.send(msg, timeout, tries)
            print(span_name, reply)
            return reply


class TracedPullChannel(IPCMessageServer):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject
        log.warning("%s.__init__", __class__)

        # Wrap payload handler for IPC
        payload_handler = self.channel.payload_handler
        setup_jaeger()

        def wrapped_payload_handler(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = "TracedPullChannel.wrapped_payload_handler"
            with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL):
                reply = payload_handler(*args, **kwargs)
                print(span_name, reply)
                return reply

        self.channel.payload_handler = wrapped_payload_handler


class TracedIPCPubChannel(IPCMessagePublisher):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject
        log.warning("%s.__init__", __class__)

    def publish(self, msg):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)
        span_name = "TracedIPCPubChannel.publish"
        with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL):
            reply = self.channel.publish(msg)
            print(span_name, reply)
            return reply


class TracedIPCSubChannel(IPCMessageSubscriber):
    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.channel = baseObject
        log.warning("%s.__init__", __class__)

    def read_sync(self, timeout=None):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)
        span_name = "TracedIPCSubChannel.read_sync"
        with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL):
            reply = self.channel.read_sync(timeout)
            print(span_name, reply)
            return reply

    @salt.ext.tornado.gen.coroutine
    def read_async(self, callback):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)
        span_name = "TracedIPCSubChannel.read_async"
        def wrapped_callback(*args, **kwargs):
            with tracer.start_as_current_span(span_name, kind=trace.SpanKind.INTERNAL):
                reply = callback(*args, **kwargs)
                print(span_name, reply)
                return reply
        return self.channel.read_async(wrapped_callback)
