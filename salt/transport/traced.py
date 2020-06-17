from __future__ import absolute_import, print_function, unicode_literals

import logging
import typing

import salt.ext.tornado.gen
from salt.transport.client import AsyncReqChannel
from salt.transport.client import AsyncPubChannel
from salt.transport.ipc import IPCServer
from salt.transport.ipc import IPCMessageClient

from opentelemetry import context, propagators, trace
from opentelemetry.trace.status import Status, StatusCanonicalCode

from contextvars import ContextVar
service_name = ContextVar('service_name')

from functools import wraps
def service_name_wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        service_name.set(func.__name__)
        setup_jaeger()
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(func.__name__, kind=trace.SpanKind.INTERNAL) as span:
            return func(*args, **kwargs)
    return wrapped


def setup_jaeger():
    import threading
    print(threading.get_ident(), service_name.get('unknown'))
    #import traceback
    #traceback.print_stack()
    from opentelemetry.ext import jaeger
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchExportSpanProcessor

    trace.set_tracer_provider(TracerProvider())

    # Create a BatchExportSpanProcessor and add the exporter to it
    trace.get_tracer_provider().add_span_processor(
        BatchExportSpanProcessor(
            jaeger.JaegerSpanExporter(
                service_name=service_name.get('unknown'),
                # configure agent
                agent_host_name='localhost',
                agent_port=6831,
            )
        )
    )

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
        setup_jaeger()
        tracer = trace.get_tracer(__name__)

        span_name = "TracedReqChannel.send"

        attributes = {
            key: str(value) for key, value in load.items()
            if key in ['id', 'cmd', 'data', 'tag']
        }
        send = tracer.start_span(span_name, kind=trace.SpanKind.PRODUCER, attributes=attributes)
        with tracer.start_as_current_span(span_name + "(running handler)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
            propagators.inject(set_header_into_dict, load)
            reply = self.channel.send(load, tries, timeout, raw)
        child = tracer.start_span(span_name + "(waiting for callback)", kind=trace.SpanKind.INTERNAL, parent=send)

        from salt.ext.tornado.concurrent import Future
        wrapped_reply = Future()

        def callback(future):
            child.end()
            value = future.result()
            log.warning("%s.send (reply callback) %s", __class__, value)
            with tracer.start_as_current_span(span_name + "(callback)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
                wrapped_reply.set_result(value)
            send.set_status(Status(StatusCanonicalCode.OK))
            send.end()

        reply.add_done_callback(callback)

        return wrapped_reply

    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        setup_jaeger()
        tracer = trace.get_tracer(__name__)

        span_name = "TracedReqChannel.crypted_transfer_decode_dictentry"

        attributes = {
            key: str(value) for key, value in load.items()
            if key in ['id', 'cmd', 'data', 'tag']
        }
        send = tracer.start_span(span_name, kind=trace.SpanKind.PRODUCER, attributes=attributes)
        with tracer.start_as_current_span(span_name + "(running handler)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
            propagators.inject(set_header_into_dict, load)
            reply = self.channel.crypted_transfer_decode_dictentry(load, dictkey, tries, timeout)
        child = tracer.start_span(span_name + "(waiting for callback)", kind=trace.SpanKind.CONSUMER, parent=send)

        from salt.ext.tornado.concurrent import Future
        wrapped_reply = Future()

        def callback(future):
            child.end()
            value = future.result()
            log.warning("%s.send (reply callback) %s", __class__, value)
            with tracer.start_as_current_span(span_name + "(callback)", kind=trace.SpanKind.PRODUCER, parent=send) as span:
                wrapped_reply.set_result(value)
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
                if key in ['cmd', 'id', 'jiq', 'return', 'retcode', 'fun', 'fun_args']
            }

            reply = None
            try:
                tracer = trace.get_tracer(__name__)
                send = tracer.start_span(span_name, kind=trace.SpanKind.PRODUCER, attributes=attributes)
                with tracer.start_as_current_span(span_name + "(running handler)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
                    reply = payload_handler(*args, **kwargs)
                child = tracer.start_span(span_name + "(waiting for callback)", kind=trace.SpanKind.INTERNAL, parent=send)
                from salt.ext.tornado.concurrent import Future
                wrapped_reply = Future()

                def callback(future):
                    child.end()
                    value = future.result()
                    log.warning("%s.send (reply callback) %s", __class__, value)
                    with tracer.start_as_current_span(span_name + "(callback)", kind=trace.SpanKind.INTERNAL, parent=send) as span:
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
        span_name = "TracedPubServerChannel.publish"

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.PRODUCER,
        ):
            propagators.inject(set_header_into_dict, load)
            log.warning("%s.publish modified %s", __class__, load)

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
        log.warning("%s.__init__", __class__)

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
        log.warning("%s.__init__", __class__)

        # Wrap payload handler for IPC
        self.payload_handler = self.channel.payload_handler
        def wrapped_payload_handler(*args, **kwargs):
            log.warning("%s.wrapped_payload_handler %s %s", __class__, args, kwargs)
            reply = self.payload_handler(*args, **kwargs)
            log.warning("%s.wrapped_payload_handler (reply) %s", __class__, reply)
            return reply

        self.channel.payload_handler = wrapped_payload_handler
