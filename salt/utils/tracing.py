import threading
from contextvars import ContextVar
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor


service_name = ContextVar('service_name')


def service_name_wrapper(*args):
    def _trace(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            service_name.set(func.__name__)
            setup_jaeger()
            if start_span:
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span(func.__name__ + " (service_name_wrapper)", kind=trace.SpanKind.INTERNAL) as span:
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapped

    # If no arguments are set, this is the decorator, and we load defaults
    if len(args) == 1 and callable(args[0]):
        start_span = False
        return _trace(args[0])
    else:  # We got arguments, so we return the decorator instead of calling it
        start_span, = args
        return _trace


def setup_jaeger():
    print("setup_jaeger called from thread:", threading.get_ident(), "service name:", service_name.get('unknown'))

    from opentelemetry.ext import jaeger
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
