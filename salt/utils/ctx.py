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
