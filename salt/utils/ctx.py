import contextlib

try:
    # Try the stdlib C extension first
    import _contextvars as contextvars
except ImportError:
    # Py<3.7
    import contextvars

DEFAULT_CTX_VAR = "request_ctxvar"
request_ctxvar = contextvars.ContextVar(DEFAULT_CTX_VAR)


@contextlib.contextmanager
def request_context(data):
    """
    A context manager that sets and un-sets the loader context.
    """
    tok = request_ctxvar.set(data)
    try:
        yield
    finally:
        request_ctxvar.reset(tok)


def get_request_context():
    """
    Get the data from the current request context.
    """
    return request_ctxvar.get({})


def subproxy_log_context(opts, *, child_id=None, data=None):
    """Attribute logs to a DeltaProxy child without modifying a shared job load."""
    if child_id is None:
        if not opts.get("subproxy"):
            return contextlib.nullcontext()
        child_id = opts["id"]
    return request_context(
        {"data": dict(data or {}, id=child_id), "opts": opts, "subproxy_id": child_id}
    )
