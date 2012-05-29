import inspect
import sys
import types

try:
    import cPickle as pickle
except ImportError:
    import pickle

# True if we are running on Python 3.
PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str,
    integer_types = int,
    class_types = type,
    text_type = str
    binary_type = bytes
    long = int
else:
    string_types = basestring,
    integer_types = (int, long)
    class_types = (type, types.ClassType)
    text_type = unicode
    binary_type = str
    long = long


def text_(s, encoding='latin-1', errors='strict'):
    """ If ``s`` is an instance of ``binary_type``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``"""
    if isinstance(s, binary_type):
        return s.decode(encoding, errors)
    return s


def bytes_(s, encoding='latin-1', errors='strict'):
    """ If ``s`` is an instance of ``text_type``, return
    ``s.encode(encoding, errors)``, otherwise return ``s``"""
    if isinstance(s, text_type):
        return s.encode(encoding, errors)
    return s


if PY3:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s, 'ascii', 'strict')
else:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s)

ascii_native_.__doc__ = """
Python 3: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s, 'ascii', 'strict')``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s)``
"""


if PY3:
    def native_(s, encoding='latin-1', errors='strict'):
        """ If ``s`` is an instance of ``text_type``, return
        ``s``, otherwise return ``str(s, encoding, errors)``"""
        if isinstance(s, text_type):
            return s
        return str(s, encoding, errors)
else:
    def native_(s, encoding='latin-1', errors='strict'):
        """ If ``s`` is an instance of ``text_type``, return
        ``s.encode(encoding, errors)``, otherwise return ``str(s)``"""
        if isinstance(s, text_type):
            return s.encode(encoding, errors)
        return str(s)

native_.__doc__ = """
Python 3: If ``s`` is an instance of ``text_type``, return ``s``, otherwise
return ``str(s, encoding, errors)``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode(encoding, errors)``, otherwise return ``str(s)``
"""

if PY3:
    from urllib import parse
    from urllib.error import URLError
    import http.server as BaseHTTPServer
    from urllib.error import HTTPError
    urlparse = parse
    from urllib.parse import quote as url_quote
    from urllib.parse import quote_plus as url_quote_plus
    from urllib.parse import unquote as url_unquote
    from urllib.parse import urlencode as url_encode
    from urllib.request import urlopen as url_open
    url_unquote_text = url_unquote
    url_unquote_native = url_unquote
else:
    from urlparse import urlparse
    import BaseHTTPServer
    from urllib2 import HTTPError, URLError
    from urllib import quote as url_quote
    from urllib import quote_plus as url_quote_plus
    from urllib import unquote as url_unquote
    from urllib import urlencode as url_encode
    from urllib2 import urlopen as url_open
    def url_unquote_text(v, encoding='utf-8', errors='replace'):
        v = url_unquote(v)
        return v.decode(encoding, errors)
    def url_unquote_native(v, encoding='utf-8', errors='replace'):
        return native_(url_unquote_text(v, encoding, errors))

if PY3:
    import builtins
    exec_ = getattr(builtins, "exec")

    def reraise(tp, value, tb=None):
        if value is None:
            value = tp
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

    del builtins

else:
    def exec_(code, globs=None, locs=None):
        """Execute code in a namespace."""
        if globs is None:
            frame = sys._getframe(1)
            globs = frame.f_globals
            if locs is None:
                locs = frame.f_locals
            del frame
        elif locs is None:
            locs = globs
        exec("""exec code in globs, locs""")


    exec_("""def reraise(tp, value, tb=None):
    raise tp, value, tb
""")


if PY3:
    def iteritems_(d):
        return d.items()

    def itervalues_(d):
        return d.values()

    def iterkeys_(d):
        return d.keys()
else:
    def iteritems_(d):
        return d.iteritems()

    def itervalues_(d):
        return d.itervalues()

    def iterkeys_(d):
        return d.iterkeys()


if PY3:
    def map_(*arg):
        return list(map(*arg))
else:
    map_ = map

if PY3:
    def is_nonstr_iter(v):
        if isinstance(v, str):
            return False
        return hasattr(v, '__iter__')
else:
    def is_nonstr_iter(v):
        return hasattr(v, '__iter__')

if PY3:
    im_func = '__func__'
    im_self = '__self__'
else:
    im_func = 'im_func'
    im_self = 'im_self'


try:
    input_ = raw_input
except NameError:
    input_ = input


try:
    from StringIO import StringIO as NativeIO
except ImportError:
    from io import StringIO as NativeIO


def is_bound_method(ob):
    return inspect.ismethod(ob) and getattr(ob, im_self, None) is not None
