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

    Query a resource, and decode the return data

    Passes through all the parameters described in the
    :py:func:`utils.http.query function <salt.utils.http.query>`:

    .. autofunction:: salt.utils.http.query

    raise_error : True
        If ``False``, and if a connection cannot be made, the error will be
        suppressed and the body of the return will simply be ``None``.

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
