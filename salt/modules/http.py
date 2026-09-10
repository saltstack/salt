"""
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.

.. versionadded:: 2015.5.0
"""

import time

import salt.utils.http
from salt.exceptions import CommandExecutionError


def query(url, **kwargs):
    """
    .. versionadded:: 2015.5.0

    Query a resource, and decode the return data.

    All keyword arguments are forwarded to
    :py:func:`salt.utils.http.query`. The most commonly used kwargs are
    summarized below; see the underlying utility for the full reference.

    Request
        ``method`` (default ``GET``), ``params`` (query string dict),
        ``data`` (request body string), ``data_file`` (path or salt:// URL
        to read body from), ``data_render`` / ``data_renderer`` to render
        the body through a Salt renderer, ``template_dict`` of values to
        expose when rendering.

    Headers
        ``header_dict`` (dict of headers), ``header_list`` (list of
        ``Name: value`` strings), ``header_file`` (path or salt:// URL),
        ``header_render`` / ``header_renderer`` to render headers through a
        Salt renderer.

    Authentication
        ``username`` and ``password`` for HTTP basic auth, ``auth`` for a
        pre-built ``(user, pass)`` tuple, ``cert`` for a client certificate
        path or ``(cert, key)`` pair.

    TLS
        ``verify_ssl`` (default ``True``), ``ca_bundle`` to point at an
        alternate CA bundle. Set ``verify_ssl=False`` only for trusted
        development endpoints.

    Cookies and sessions
        ``cookies`` to send a cookie jar, ``cookie_jar`` to load/save the
        jar from disk, ``cookie_format`` (``lwp`` or ``mozilla``),
        ``persist_session`` and ``session_cookie_jar`` to persist a session
        across calls.

    Response decoding
        ``decode`` (default ``False``) parses the response body using
        ``decode_type`` (``auto``, ``json``, ``yaml``, ``xml`` or
        ``plain``). ``decode_body`` (default ``True``) controls whether to
        decode bytes to text at all. ``text`` returns the raw text body in
        the result, ``status`` returns the HTTP status code, ``headers``
        returns response headers.

    Streaming
        ``stream`` (default ``False``) streams the response body.
        ``streaming_callback`` and ``header_callback`` receive chunks as
        they arrive.

    Output capture
        ``text_out``, ``headers_out`` and ``decode_out`` are paths to which
        the corresponding parts of the response will be written.

    Form data
        ``formdata`` (default ``False``) sends a multipart/form-data body.
        ``formdata_fieldname`` and ``formdata_filename`` configure the file
        part.

    Transport
        ``backend`` (``tornado``, ``requests`` or ``urllib2``),
        ``agent`` (``User-Agent`` header), ``port`` (used when the URL has
        no explicit port), ``handle`` (default ``False``) returns the raw
        backend response object.

    Error handling
        ``raise_error`` (default ``True``). If ``False``, connection errors
        are suppressed and the body of the return will simply be ``None``.

    Sensitive data
        ``hide_fields`` is a list of header or form field names whose
        values should be redacted in the logged trace output.

    Test mode
        ``test`` (default ``False``) and ``test_url`` allow you to dry-run
        the request against a fixture URL without making the real call.

    CLI Example:

    .. code-block:: bash

        salt '*' http.query http://somelink.com/
        salt '*' http.query http://somelink.com/ method=POST \
            params='{"key1": "val1", "key2": "val2"}'
        salt '*' http.query http://somelink.com/ method=POST \
            data='<xml>somecontent</xml>'
    """
    opts = __opts__.copy()
    if "opts" in kwargs:
        opts.update(kwargs["opts"])
        del kwargs["opts"]

    try:
        return salt.utils.http.query(url=url, opts=opts, **kwargs)
    except Exception as exc:  # pylint: disable=broad-except
        raise CommandExecutionError(str(exc))


def wait_for_successful_query(url, wait_for=300, **kwargs):
    """
    Query a resource until a successful response, and decode the return data

    CLI Example:

    .. code-block:: bash

        salt '*' http.wait_for_successful_query http://somelink.com/ wait_for=160 request_interval=1
    """

    starttime = time.time()

    while True:
        caught_exception = None
        result = None
        try:
            result = query(url=url, **kwargs)
            if not result.get("Error") and not result.get("error"):
                return result
        except Exception as exc:  # pylint: disable=broad-except
            caught_exception = exc

        if time.time() > starttime + wait_for:
            if not result and caught_exception:
                # workaround pylint bug https://www.logilab.org/ticket/3207
                raise caught_exception  # pylint: disable=E0702

            return result
        elif "request_interval" in kwargs:
            # Space requests out by delaying for an interval
            time.sleep(kwargs["request_interval"])


def update_ca_bundle(target=None, source=None, merge_files=None):
    """
    Update the local CA bundle file from a URL

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' http.update_ca_bundle
        salt '*' http.update_ca_bundle target=/path/to/cacerts.pem
        salt '*' http.update_ca_bundle source=https://example.com/cacerts.pem

    If the ``target`` is not specified, it will be pulled from the ``ca_cert``
    configuration variable available to the minion. If it cannot be found there,
    it will be placed at ``<<FILE_ROOTS>>/cacerts.pem``.

    If the ``source`` is not specified, it will be pulled from the
    ``ca_cert_url`` configuration variable available to the minion. If it cannot
    be found, it will be downloaded from the cURL website, using an http (not
    https) URL. USING THE DEFAULT URL SHOULD BE AVOIDED!

    ``merge_files`` may also be specified, which includes a string or list of
    strings representing a file or files to be appended to the end of the CA
    bundle, once it is downloaded.

    CLI Example:

    .. code-block:: bash

        salt '*' http.update_ca_bundle merge_files=/path/to/mycert.pem
    """
    if target is None:
        target = __salt__["config.get"]("ca_bundle", None)

    if source is None:
        source = __salt__["config.get"]("ca_bundle_url", None)

    return salt.utils.http.update_ca_bundle(target, source, __opts__, merge_files)
