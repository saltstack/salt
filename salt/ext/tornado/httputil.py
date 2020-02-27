#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""HTTP utility code shared by clients and servers.

This module also defines the `HTTPServerRequest` class which is exposed
via `tornado.web.RequestHandler.request`.
"""
# pylint: skip-file

from __future__ import absolute_import, division, print_function

import calendar
import collections
import copy
import datetime
import email.utils
import numbers
import re
import time

from salt.ext.tornado.escape import native_str, parse_qs_bytes, utf8
from salt.ext.tornado.log import gen_log
from salt.ext.tornado.util import ObjectDict, PY3

if PY3:
    import http.cookies as Cookie
    from http.client import responses
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
else:
    import Cookie
    from httplib import responses
    from urllib import urlencode
    from urlparse import urlparse, urlunparse, parse_qsl


# responses is unused in this file, but we re-export it to other files.
# Reference it so pyflakes doesn't complain.
responses

try:
    from ssl import SSLError
except ImportError:
    # ssl is unavailable on app engine.
    class _SSLError(Exception):
        pass
    # Hack around a mypy limitation. We can't simply put "type: ignore"
    # on the class definition itself; must go through an assignment.
    SSLError = _SSLError  # type: ignore

try:
    import typing
except ImportError:
    pass


# RFC 7230 section 3.5: a recipient MAY recognize a single LF as a line
# terminator and ignore any preceding CR.
_CRLF_RE = re.compile(r'\r?\n')


class _NormalizedHeaderCache(dict):
    """Dynamic cached mapping of header names to Http-Header-Case.

    Implemented as a dict subclass so that cache hits are as fast as a
    normal dict lookup, without the overhead of a python function
    call.

    >>> normalized_headers = _NormalizedHeaderCache(10)
    >>> normalized_headers["coNtent-TYPE"]
    'Content-Type'
    """
    def __init__(self, size):
        super(_NormalizedHeaderCache, self).__init__()
        self.size = size
        self.queue = collections.deque()

    def __missing__(self, key):
        normalized = "-".join([w.capitalize() for w in key.split("-")])
        self[key] = normalized
        self.queue.append(key)
        if len(self.queue) > self.size:
            # Limit the size of the cache.  LRU would be better, but this
            # simpler approach should be fine.  In Python 2.7+ we could
            # use OrderedDict (or in 3.2+, @functools.lru_cache).
            old_key = self.queue.popleft()
            del self[old_key]
        return normalized


_normalized_headers = _NormalizedHeaderCache(1000)


class HTTPHeaders(collections.MutableMapping):
    """A dictionary that maintains ``Http-Header-Case`` for all keys.

    Supports multiple values per key via a pair of new methods,
    `add()` and `get_list()`.  The regular dictionary interface
    returns a single value per key, with multiple values joined by a
    comma.

    >>> h = HTTPHeaders({"content-type": "text/html"})
    >>> list(h.keys())
    ['Content-Type']
    >>> h["Content-Type"]
    'text/html'

    >>> h.add("Set-Cookie", "A=B")
    >>> h.add("Set-Cookie", "C=D")
    >>> h["set-cookie"]
    'A=B,C=D'
    >>> h.get_list("set-cookie")
    ['A=B', 'C=D']

    >>> for (k,v) in sorted(h.get_all()):
    ...    print('%s: %s' % (k,v))
    ...
    Content-Type: text/html
    Set-Cookie: A=B
    Set-Cookie: C=D
    """
    def __init__(self, *args, **kwargs):
        self._dict = {}  # type: typing.Dict[str, str]
        self._as_list = {}  # type: typing.Dict[str, typing.List[str]]
        self._last_key = None
        if (len(args) == 1 and len(kwargs) == 0 and
                isinstance(args[0], HTTPHeaders)):
            # Copy constructor
            for k, v in args[0].get_all():
                self.add(k, v)
        else:
            # Dict-style initialization
            self.update(*args, **kwargs)

    # new public methods

    def add(self, name, value):
        # type: (str, str) -> None
        """Adds a new value for the given key."""
        norm_name = _normalized_headers[name]
        self._last_key = norm_name
        if norm_name in self:
            self._dict[norm_name] = (native_str(self[norm_name]) + ',' +
                                     native_str(value))
            self._as_list[norm_name].append(value)
        else:
            self[norm_name] = value

    def get_list(self, name):
        """Returns all values for the given header as a list."""
        norm_name = _normalized_headers[name]
        return self._as_list.get(norm_name, [])

    def get_all(self):
        # type: () -> typing.Iterable[typing.Tuple[str, str]]
        """Returns an iterable of all (name, value) pairs.

        If a header has multiple values, multiple pairs will be
        returned with the same name.
        """
        for name, values in self._as_list.items():
            for value in values:
                yield (name, value)

    def parse_line(self, line):
        """Updates the dictionary with a single header line.

        >>> h = HTTPHeaders()
        >>> h.parse_line("Content-Type: text/html")
        >>> h.get('content-type')
        'text/html'
        """
        if line[0].isspace():
            # continuation of a multi-line header
            new_part = ' ' + line.lstrip()
            self._as_list[self._last_key][-1] += new_part
            self._dict[self._last_key] += new_part
        else:
            name, value = line.split(":", 1)
            self.add(name, value.strip())

    @classmethod
    def parse(cls, headers):
        """Returns a dictionary from HTTP header text.

        >>> h = HTTPHeaders.parse("Content-Type: text/html\\r\\nContent-Length: 42\\r\\n")
        >>> sorted(h.items())
        [('Content-Length', '42'), ('Content-Type', 'text/html')]
        """
        h = cls()
        for line in _CRLF_RE.split(headers):
            if line:
                h.parse_line(line)
        return h

    # MutableMapping abstract method implementations.

    def __setitem__(self, name, value):
        norm_name = _normalized_headers[name]
        self._dict[norm_name] = value
        self._as_list[norm_name] = [value]

    def __getitem__(self, name):
        # type: (str) -> str
        return self._dict[_normalized_headers[name]]

    def __delitem__(self, name):
        norm_name = _normalized_headers[name]
        del self._dict[norm_name]
        del self._as_list[norm_name]

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def copy(self):
        # defined in dict but not in MutableMapping.
        return HTTPHeaders(self)

    # Use our overridden copy method for the copy.copy module.
    # This makes shallow copies one level deeper, but preserves
    # the appearance that HTTPHeaders is a single container.
    __copy__ = copy

    def __str__(self):
        lines = []
        for name, value in self.get_all():
            lines.append("%s: %s\n" % (name, value))
        return "".join(lines)

    __unicode__ = __str__


class HTTPServerRequest(object):
    """A single HTTP request.

    All attributes are type `str` unless otherwise noted.

    .. attribute:: method

       HTTP request method, e.g. "GET" or "POST"

    .. attribute:: uri

       The requested uri.

    .. attribute:: path

       The path portion of `uri`

    .. attribute:: query

       The query portion of `uri`

    .. attribute:: version

       HTTP version specified in request, e.g. "HTTP/1.1"

    .. attribute:: headers

       `.HTTPHeaders` dictionary-like object for request headers.  Acts like
       a case-insensitive dictionary with additional methods for repeated
       headers.

    .. attribute:: body

       Request body, if present, as a byte string.

    .. attribute:: remote_ip

       Client's IP address as a string.  If ``HTTPServer.xheaders`` is set,
       will pass along the real IP address provided by a load balancer
       in the ``X-Real-Ip`` or ``X-Forwarded-For`` header.

    .. versionchanged:: 3.1
       The list format of ``X-Forwarded-For`` is now supported.

    .. attribute:: protocol

       The protocol used, either "http" or "https".  If ``HTTPServer.xheaders``
       is set, will pass along the protocol used by a load balancer if
       reported via an ``X-Scheme`` header.

    .. attribute:: host

       The requested hostname, usually taken from the ``Host`` header.

    .. attribute:: arguments

       GET/POST arguments are available in the arguments property, which
       maps arguments names to lists of values (to support multiple values
       for individual names). Names are of type `str`, while arguments
       are byte strings.  Note that this is different from
       `.RequestHandler.get_argument`, which returns argument values as
       unicode strings.

    .. attribute:: query_arguments

       Same format as ``arguments``, but contains only arguments extracted
       from the query string.

       .. versionadded:: 3.2

    .. attribute:: body_arguments

       Same format as ``arguments``, but contains only arguments extracted
       from the request body.

       .. versionadded:: 3.2

    .. attribute:: files

       File uploads are available in the files property, which maps file
       names to lists of `.HTTPFile`.

    .. attribute:: connection

       An HTTP request is attached to a single HTTP connection, which can
       be accessed through the "connection" attribute. Since connections
       are typically kept open in HTTP/1.1, multiple requests can be handled
       sequentially on a single connection.

    .. versionchanged:: 4.0
       Moved from ``tornado.httpserver.HTTPRequest``.
    """
    def __init__(self, method=None, uri=None, version="HTTP/1.0", headers=None,
                 body=None, host=None, files=None, connection=None,
                 start_line=None, server_connection=None):
        if start_line is not None:
            method, uri, version = start_line
        self.method = method
        self.uri = uri
        self.version = version
        self.headers = headers or HTTPHeaders()
        self.body = body or b""

        # set remote IP and protocol
        context = getattr(connection, 'context', None)
        self.remote_ip = getattr(context, 'remote_ip', None)
        self.protocol = getattr(context, 'protocol', "http")

        self.host = host or self.headers.get("Host") or "127.0.0.1"
        self.host_name = split_host_and_port(self.host.lower())[0]
        self.files = files or {}
        self.connection = connection
        self.server_connection = server_connection
        self._start_time = time.time()
        self._finish_time = None

        self.path, sep, self.query = uri.partition('?')
        self.arguments = parse_qs_bytes(self.query, keep_blank_values=True)
        self.query_arguments = copy.deepcopy(self.arguments)
        self.body_arguments = {}

    def supports_http_1_1(self):
        """Returns True if this request supports HTTP/1.1 semantics.

        .. deprecated:: 4.0
           Applications are less likely to need this information with the
           introduction of `.HTTPConnection`.  If you still need it, access
           the ``version`` attribute directly.
        """
        return self.version == "HTTP/1.1"

    @property
    def cookies(self):
        """A dictionary of Cookie.Morsel objects."""
        if not hasattr(self, "_cookies"):
            self._cookies = Cookie.SimpleCookie()
            if "Cookie" in self.headers:
                try:
                    parsed = parse_cookie(self.headers["Cookie"])
                except Exception:
                    pass
                else:
                    for k, v in parsed.items():
                        try:
                            self._cookies[k] = v
                        except Exception:
                            # SimpleCookie imposes some restrictions on keys;
                            # parse_cookie does not. Discard any cookies
                            # with disallowed keys.
                            pass
        return self._cookies

    def write(self, chunk, callback=None):
        """Writes the given chunk to the response stream.

        .. deprecated:: 4.0
           Use ``request.connection`` and the `.HTTPConnection` methods
           to write the response.
        """
        assert isinstance(chunk, bytes)
        assert self.version.startswith("HTTP/1."), \
            "deprecated interface only supported in HTTP/1.x"
        self.connection.write(chunk, callback=callback)

    def finish(self):
        """Finishes this HTTP request on the open connection.

        .. deprecated:: 4.0
           Use ``request.connection`` and the `.HTTPConnection` methods
           to write the response.
        """
        self.connection.finish()
        self._finish_time = time.time()

    def full_url(self):
        """Reconstructs the full URL for this request."""
        return self.protocol + "://" + self.host + self.uri

    def request_time(self):
        """Returns the amount of time it took for this request to execute."""
        if self._finish_time is None:
            return time.time() - self._start_time
        else:
            return self._finish_time - self._start_time

    def get_ssl_certificate(self, binary_form=False):
        """Returns the client's SSL certificate, if any.

        To use client certificates, the HTTPServer's
        `ssl.SSLContext.verify_mode` field must be set, e.g.::

            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain("foo.crt", "foo.key")
            ssl_ctx.load_verify_locations("cacerts.pem")
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            server = HTTPServer(app, ssl_options=ssl_ctx)

        By default, the return value is a dictionary (or None, if no
        client certificate is present).  If ``binary_form`` is true, a
        DER-encoded form of the certificate is returned instead.  See
        SSLSocket.getpeercert() in the standard library for more
        details.
        http://docs.python.org/library/ssl.html#sslsocket-objects
        """
        try:
            return self.connection.stream.socket.getpeercert(
                binary_form=binary_form)
        except SSLError:
            return None

    def _parse_body(self):
        parse_body_arguments(
            self.headers.get("Content-Type", ""), self.body,
            self.body_arguments, self.files,
            self.headers)

        for k, v in self.body_arguments.items():
            self.arguments.setdefault(k, []).extend(v)

    def __repr__(self):
        attrs = ("protocol", "host", "method", "uri", "version", "remote_ip")
        args = ", ".join(["%s=%r" % (n, getattr(self, n)) for n in attrs])
        return "%s(%s, headers=%s)" % (
            self.__class__.__name__, args, dict(self.headers))


class HTTPInputError(Exception):
    """Exception class for malformed HTTP requests or responses
    from remote sources.

    .. versionadded:: 4.0
    """
    pass


class HTTPOutputError(Exception):
    """Exception class for errors in HTTP output.

    .. versionadded:: 4.0
    """
    pass


class HTTPServerConnectionDelegate(object):
    """Implement this interface to handle requests from `.HTTPServer`.

    .. versionadded:: 4.0
    """
    def start_request(self, server_conn, request_conn):
        """This method is called by the server when a new request has started.

        :arg server_conn: is an opaque object representing the long-lived
            (e.g. tcp-level) connection.
        :arg request_conn: is a `.HTTPConnection` object for a single
            request/response exchange.

        This method should return a `.HTTPMessageDelegate`.
        """
        raise NotImplementedError()

    def on_close(self, server_conn):
        """This method is called when a connection has been closed.

        :arg server_conn: is a server connection that has previously been
            passed to ``start_request``.
        """
        pass


class HTTPMessageDelegate(object):
    """Implement this interface to handle an HTTP request or response.

    .. versionadded:: 4.0
    """
    def headers_received(self, start_line, headers):
        """Called when the HTTP headers have been received and parsed.

        :arg start_line: a `.RequestStartLine` or `.ResponseStartLine`
            depending on whether this is a client or server message.
        :arg headers: a `.HTTPHeaders` instance.

        Some `.HTTPConnection` methods can only be called during
        ``headers_received``.

        May return a `.Future`; if it does the body will not be read
        until it is done.
        """
        pass

    def data_received(self, chunk):
        """Called when a chunk of data has been received.

        May return a `.Future` for flow control.
        """
        pass

    def finish(self):
        """Called after the last chunk of data has been received."""
        pass

    def on_connection_close(self):
        """Called if the connection is closed without finishing the request.

        If ``headers_received`` is called, either ``finish`` or
        ``on_connection_close`` will be called, but not both.
        """
        pass


class HTTPConnection(object):
    """Applications use this interface to write their responses.

    .. versionadded:: 4.0
    """
    def write_headers(self, start_line, headers, chunk=None, callback=None):
        """Write an HTTP header block.

        :arg start_line: a `.RequestStartLine` or `.ResponseStartLine`.
        :arg headers: a `.HTTPHeaders` instance.
        :arg chunk: the first (optional) chunk of data.  This is an optimization
            so that small responses can be written in the same call as their
            headers.
        :arg callback: a callback to be run when the write is complete.

        The ``version`` field of ``start_line`` is ignored.

        Returns a `.Future` if no callback is given.
        """
        raise NotImplementedError()

    def write(self, chunk, callback=None):
        """Writes a chunk of body data.

        The callback will be run when the write is complete.  If no callback
        is given, returns a Future.
        """
        raise NotImplementedError()

    def finish(self):
        """Indicates that the last body data has been written.
        """
        raise NotImplementedError()


def url_concat(url, args):
    """Concatenate url and arguments regardless of whether
    url has existing query parameters.

    ``args`` may be either a dictionary or a list of key-value pairs
    (the latter allows for multiple values with the same key.

    >>> url_concat("http://example.com/foo", dict(c="d"))
    'http://example.com/foo?c=d'
    >>> url_concat("http://example.com/foo?a=b", dict(c="d"))
    'http://example.com/foo?a=b&c=d'
    >>> url_concat("http://example.com/foo?a=b", [("c", "d"), ("c", "d2")])
    'http://example.com/foo?a=b&c=d&c=d2'
    """
    if args is None:
        return url
    parsed_url = urlparse(url)
    if isinstance(args, dict):
        parsed_query = parse_qsl(parsed_url.query, keep_blank_values=True)
        parsed_query.extend(args.items())
    elif isinstance(args, list) or isinstance(args, tuple):
        parsed_query = parse_qsl(parsed_url.query, keep_blank_values=True)
        parsed_query.extend(args)
    else:
        err = "'args' parameter should be dict, list or tuple. Not {0}".format(
            type(args))
        raise TypeError(err)
    final_query = urlencode(parsed_query)
    url = urlunparse((
        parsed_url[0],
        parsed_url[1],
        parsed_url[2],
        parsed_url[3],
        final_query,
        parsed_url[5]))
    return url


class HTTPFile(ObjectDict):
    """Represents a file uploaded via a form.

    For backwards compatibility, its instance attributes are also
    accessible as dictionary keys.

    * ``filename``
    * ``body``
    * ``content_type``
    """
    pass


def _parse_request_range(range_header):
    """Parses a Range header.

    Returns either ``None`` or tuple ``(start, end)``.
    Note that while the HTTP headers use inclusive byte positions,
    this method returns indexes suitable for use in slices.

    >>> start, end = _parse_request_range("bytes=1-2")
    >>> start, end
    (1, 3)
    >>> [0, 1, 2, 3, 4][start:end]
    [1, 2]
    >>> _parse_request_range("bytes=6-")
    (6, None)
    >>> _parse_request_range("bytes=-6")
    (-6, None)
    >>> _parse_request_range("bytes=-0")
    (None, 0)
    >>> _parse_request_range("bytes=")
    (None, None)
    >>> _parse_request_range("foo=42")
    >>> _parse_request_range("bytes=1-2,6-10")

    Note: only supports one range (ex, ``bytes=1-2,6-10`` is not allowed).

    See [0] for the details of the range header.

    [0]: http://greenbytes.de/tech/webdav/draft-ietf-httpbis-p5-range-latest.html#byte.ranges
    """
    unit, _, value = range_header.partition("=")
    unit, value = unit.strip(), value.strip()
    if unit != "bytes":
        return None
    start_b, _, end_b = value.partition("-")
    try:
        start = _int_or_none(start_b)
        end = _int_or_none(end_b)
    except ValueError:
        return None
    if end is not None:
        if start is None:
            if end != 0:
                start = -end
                end = None
        else:
            end += 1
    return (start, end)


def _get_content_range(start, end, total):
    """Returns a suitable Content-Range header:

    >>> print(_get_content_range(None, 1, 4))
    bytes 0-0/4
    >>> print(_get_content_range(1, 3, 4))
    bytes 1-2/4
    >>> print(_get_content_range(None, None, 4))
    bytes 0-3/4
    """
    start = start or 0
    end = (end or total) - 1
    return "bytes %s-%s/%s" % (start, end, total)


def _int_or_none(val):
    val = val.strip()
    if val == "":
        return None
    return int(val)


def parse_body_arguments(content_type, body, arguments, files, headers=None):
    """Parses a form request body.

    Supports ``application/x-www-form-urlencoded`` and
    ``multipart/form-data``.  The ``content_type`` parameter should be
    a string and ``body`` should be a byte string.  The ``arguments``
    and ``files`` parameters are dictionaries that will be updated
    with the parsed contents.
    """
    if headers and 'Content-Encoding' in headers:
        gen_log.warning("Unsupported Content-Encoding: %s",
                        headers['Content-Encoding'])
        return
    if content_type.startswith("application/x-www-form-urlencoded"):
        try:
            uri_arguments = parse_qs_bytes(native_str(body), keep_blank_values=True)
        except Exception as e:
            gen_log.warning('Invalid x-www-form-urlencoded body: %s', e)
            uri_arguments = {}
        for name, values in uri_arguments.items():
            if values:
                arguments.setdefault(name, []).extend(values)
    elif content_type.startswith("multipart/form-data"):
        try:
            fields = content_type.split(";")
            for field in fields:
                k, sep, v = field.strip().partition("=")
                if k == "boundary" and v:
                    parse_multipart_form_data(utf8(v), body, arguments, files)
                    break
            else:
                raise ValueError("multipart boundary not found")
        except Exception as e:
            gen_log.warning("Invalid multipart/form-data: %s", e)


def parse_multipart_form_data(boundary, data, arguments, files):
    """Parses a ``multipart/form-data`` body.

    The ``boundary`` and ``data`` parameters are both byte strings.
    The dictionaries given in the arguments and files parameters
    will be updated with the contents of the body.
    """
    # The standard allows for the boundary to be quoted in the header,
    # although it's rare (it happens at least for google app engine
    # xmpp).  I think we're also supposed to handle backslash-escapes
    # here but I'll save that until we see a client that uses them
    # in the wild.
    if boundary.startswith(b'"') and boundary.endswith(b'"'):
        boundary = boundary[1:-1]
    final_boundary_index = data.rfind(b"--" + boundary + b"--")
    if final_boundary_index == -1:
        gen_log.warning("Invalid multipart/form-data: no final boundary")
        return
    parts = data[:final_boundary_index].split(b"--" + boundary + b"\r\n")
    for part in parts:
        if not part:
            continue
        eoh = part.find(b"\r\n\r\n")
        if eoh == -1:
            gen_log.warning("multipart/form-data missing headers")
            continue
        headers = HTTPHeaders.parse(part[:eoh].decode("utf-8"))
        disp_header = headers.get("Content-Disposition", "")
        disposition, disp_params = _parse_header(disp_header)
        if disposition != "form-data" or not part.endswith(b"\r\n"):
            gen_log.warning("Invalid multipart/form-data")
            continue
        value = part[eoh + 4:-2]
        if not disp_params.get("name"):
            gen_log.warning("multipart/form-data value missing name")
            continue
        name = disp_params["name"]
        if disp_params.get("filename"):
            ctype = headers.get("Content-Type", "application/unknown")
            files.setdefault(name, []).append(HTTPFile(  # type: ignore
                filename=disp_params["filename"], body=value,
                content_type=ctype))
        else:
            arguments.setdefault(name, []).append(value)


def format_timestamp(ts):
    """Formats a timestamp in the format used by HTTP.

    The argument may be a numeric timestamp as returned by `time.time`,
    a time tuple as returned by `time.gmtime`, or a `datetime.datetime`
    object.

    >>> format_timestamp(1359312200)
    'Sun, 27 Jan 2013 18:43:20 GMT'
    """
    if isinstance(ts, numbers.Real):
        pass
    elif isinstance(ts, (tuple, time.struct_time)):
        ts = calendar.timegm(ts)
    elif isinstance(ts, datetime.datetime):
        ts = calendar.timegm(ts.utctimetuple())
    else:
        raise TypeError("unknown timestamp type: %r" % ts)
    return email.utils.formatdate(ts, usegmt=True)


RequestStartLine = collections.namedtuple(
    'RequestStartLine', ['method', 'path', 'version'])


def parse_request_start_line(line):
    """Returns a (method, path, version) tuple for an HTTP 1.x request line.

    The response is a `collections.namedtuple`.

    >>> parse_request_start_line("GET /foo HTTP/1.1")
    RequestStartLine(method='GET', path='/foo', version='HTTP/1.1')
    """
    try:
        method, path, version = line.split(" ")
    except ValueError:
        raise HTTPInputError("Malformed HTTP request line")
    if not re.match(r"^HTTP/1\.[0-9]$", version):
        raise HTTPInputError(
            "Malformed HTTP version in HTTP Request-Line: %r" % version)
    return RequestStartLine(method, path, version)


ResponseStartLine = collections.namedtuple(
    'ResponseStartLine', ['version', 'code', 'reason'])


def parse_response_start_line(line):
    """Returns a (version, code, reason) tuple for an HTTP 1.x response line.

    The response is a `collections.namedtuple`.

    >>> parse_response_start_line("HTTP/1.1 200 OK")
    ResponseStartLine(version='HTTP/1.1', code=200, reason='OK')
    """
    line = native_str(line)
    match = re.match("(HTTP/1.[0-9]) ([0-9]+) ([^\r]*)", line)
    if not match:
        raise HTTPInputError("Error parsing response start line")
    return ResponseStartLine(match.group(1), int(match.group(2)),
                             match.group(3))

# _parseparam and _parse_header are copied and modified from python2.7's cgi.py
# The original 2.7 version of this code did not correctly support some
# combinations of semicolons and double quotes.
# It has also been modified to support valueless parameters as seen in
# websocket extension negotiations.


def _parseparam(s):
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]


def _parse_header(line):
    """Parse a Content-type like header.

    Return the main content-type and a dictionary of options.

    """
    parts = _parseparam(';' + line)
    key = next(parts)
    pdict = {}
    for p in parts:
        i = p.find('=')
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i + 1:].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
                value = value.replace('\\\\', '\\').replace('\\"', '"')
            pdict[name] = value
        else:
            pdict[p] = None
    return key, pdict


def _encode_header(key, pdict):
    """Inverse of _parse_header.

    >>> _encode_header('permessage-deflate',
    ...     {'client_max_window_bits': 15, 'client_no_context_takeover': None})
    'permessage-deflate; client_max_window_bits=15; client_no_context_takeover'
    """
    if not pdict:
        return key
    out = [key]
    # Sort the parameters just to make it easy to test.
    for k, v in sorted(pdict.items()):
        if v is None:
            out.append(k)
        else:
            # TODO: quote if necessary.
            out.append('%s=%s' % (k, v))
    return '; '.join(out)


def doctests():
    import doctest
    return doctest.DocTestSuite()


def split_host_and_port(netloc):
    """Returns ``(host, port)`` tuple from ``netloc``.

    Returned ``port`` will be ``None`` if not present.

    .. versionadded:: 4.1
    """
    match = re.match(r'^(.+):(\d+)$', netloc)
    if match:
        host = match.group(1)
        port = int(match.group(2))
    else:
        host = netloc
        port = None
    return (host, port)


_OctalPatt = re.compile(r"\\[0-3][0-7][0-7]")
_QuotePatt = re.compile(r"[\\].")
_nulljoin = ''.join


def _unquote_cookie(str):
    """Handle double quotes and escaping in cookie values.

    This method is copied verbatim from the Python 3.5 standard
    library (http.cookies._unquote) so we don't have to depend on
    non-public interfaces.
    """
    # If there aren't any doublequotes,
    # then there can't be any special characters.  See RFC 2109.
    if str is None or len(str) < 2:
        return str
    if str[0] != '"' or str[-1] != '"':
        return str

    # We have to assume that we must decode this string.
    # Down to work.

    # Remove the "s
    str = str[1:-1]

    # Check for special sequences.  Examples:
    #    \012 --> \n
    #    \"   --> "
    #
    i = 0
    n = len(str)
    res = []
    while 0 <= i < n:
        o_match = _OctalPatt.search(str, i)
        q_match = _QuotePatt.search(str, i)
        if not o_match and not q_match:              # Neither matched
            res.append(str[i:])
            break
        # else:
        j = k = -1
        if o_match:
            j = o_match.start(0)
        if q_match:
            k = q_match.start(0)
        if q_match and (not o_match or k < j):     # QuotePatt matched
            res.append(str[i:k])
            res.append(str[k + 1])
            i = k + 2
        else:                                      # OctalPatt matched
            res.append(str[i:j])
            res.append(chr(int(str[j + 1:j + 4], 8)))
            i = j + 4
    return _nulljoin(res)


def parse_cookie(cookie):
    """Parse a ``Cookie`` HTTP header into a dict of name/value pairs.

    This function attempts to mimic browser cookie parsing behavior;
    it specifically does not follow any of the cookie-related RFCs
    (because browsers don't either).

    The algorithm used is identical to that used by Django version 1.9.10.

    .. versionadded:: 4.4.2
    """
    cookiedict = {}
    for chunk in cookie.split(str(';')):
        if str('=') in chunk:
            key, val = chunk.split(str('='), 1)
        else:
            # Assume an empty name per
            # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
            key, val = str(''), chunk
        key, val = key.strip(), val.strip()
        if key or val:
            # unquote using Python's algorithm.
            cookiedict[key] = _unquote_cookie(val)
    return cookiedict
