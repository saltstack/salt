"""
HTTP monitoring states

Perform an HTTP query and statefully return the result

.. versionadded:: 2015.5.0
"""

import logging
import re
import sys
import time

__monitor__ = [
    "query",
]

log = logging.getLogger(__name__)


def query(
    name,
    match=None,
    match_type="string",
    status=None,
    status_type="string",
    wait_for=None,
    **kwargs,
):
    """
    Perform an HTTP query and statefully return the result

    Passes through all the parameters described in the
    :py:func:`utils.http.query function <salt.utils.http.query>`:

    name
        The name of the query.

    match
        Specifies a pattern to look for in the return text. By default, this will
        perform a string comparison of looking for the value of match in the return
        text.

    match_type
        Specifies the type of pattern matching to use on match. Default is ``string``, but
        can also be set to ``pcre`` to use regular expression matching if a more
        complex pattern matching is required.

        .. note::

            Despite the name of ``match_type`` for this argument, this setting
            actually uses Python's ``re.search()`` function rather than Python's
            ``re.match()`` function.

    status
        The status code for a URL for which to be checked. Can be used instead of
        or in addition to the ``match`` setting. This can be passed as an individual status code
        or a list of status codes.

    status_type
        Specifies the type of pattern matching to use for status. Default is ``string``, but
        can also be set to ``pcre`` to use regular expression matching if a more
        complex pattern matching is required. Additionally, if a list of strings representing
        statuses is given, the type ``list`` can be used.

        .. versionadded:: 3000

        .. note::

            Despite the name of ``match_type`` for this argument, this setting
            actually uses Python's ``re.search()`` function rather than Python's
            ``re.match()`` function.

    If both ``match`` and ``status`` options are set, both settings will be checked.
    However, note that if only one option is ``True`` and the other is ``False``,
    then ``False`` will be returned. If this case is reached, the comments in the
    return data will contain troubleshooting information.

    For more information about the ``http.query`` state, refer to the
    :ref:`HTTP Tutorial <tutorial-http>`.

    .. code-block:: yaml

        query_example:
          http.query:
            - name: 'http://example.com/'
            - status: 200

        query_example2:
          http.query:
            - name: 'http://example.com/'
            - status:
                - 200
                - 201
            - status_type: list

    """
    # Monitoring state, but changes may be made over HTTP
    ret = {
        "name": name,
        "result": None,
        "comment": "",
        "changes": {},
        "data": {},
    }  # Data field for monitoring state

    if match is None and status is None:
        ret["result"] = False
        ret[
            "comment"
        ] += " Either match text (match) or a status code (status) is required."
        return ret

    if "decode" not in kwargs:
        kwargs["decode"] = False
    kwargs["text"] = True
    kwargs["status"] = True
    if __opts__["test"]:
        kwargs["test"] = True

    if wait_for:
        data = __salt__["http.wait_for_successful_query"](
            name, wait_for=wait_for, **kwargs
        )
    else:
        data = __salt__["http.query"](name, **kwargs)

    if match is not None:
        if match_type == "string":
            if str(match) in data.get("text", ""):
                ret["result"] = True
                ret["comment"] += f' Match text "{match}" was found.'
            else:
                ret["result"] = False
                ret["comment"] += f' Match text "{match}" was not found.'
        elif match_type == "pcre":
            if re.search(str(match), str(data.get("text", ""))):
                ret["result"] = True
                ret["comment"] += f' Match pattern "{match}" was found.'
            else:
                ret["result"] = False
                ret["comment"] += f' Match pattern "{match}" was not found.'

    if status is not None:
        # Deals with case of status_type as a list of strings representing statuses
        if status_type == "list":
            for stat in status:
                if str(data.get("status", "")) == str(stat):
                    ret["comment"] += f" Status {stat} was found."
                    if ret["result"] is None:
                        ret["result"] = True
            if ret["result"] is not True:
                ret["comment"] += f" Statuses {status} were not found."
                ret["result"] = False

        # Deals with the case of status_type representing a regex
        elif status_type == "pcre":
            if re.search(str(status), str(data.get("status", ""))):
                ret["comment"] += f' Status pattern "{status}" was found.'
                if ret["result"] is None:
                    ret["result"] = True
            else:
                ret["comment"] += f' Status pattern "{status}" was not found.'
                ret["result"] = False

        # Deals with the case of status_type as a single string representing a status
        elif status_type == "string":
            if str(data.get("status", "")) == str(status):
                ret["comment"] += f" Status {status} was found."
                if ret["result"] is None:
                    ret["result"] = True
            else:
                ret["comment"] += f" Status {status} was not found."
                ret["result"] = False

    # cleanup spaces in comment
    ret["comment"] = ret["comment"].strip()

    if __opts__["test"] is True:
        ret["result"] = None
        ret["comment"] += " (TEST MODE"
        if "test_url" in kwargs:
            ret["comment"] += ", TEST URL WAS: {}".format(kwargs["test_url"])
        ret["comment"] += ")"

    ret["data"] = data
    return ret


def wait_for_successful_query(name, wait_for=300, **kwargs):
    """
    Like query but, repeat and wait until match/match_type or status is fulfilled. State returns result from last
    query state in case of success or if no successful query was made within wait_for timeout.

    name
        The name of the query.

    wait_for
        Total time to wait for requests that succeed.

    request_interval
        Optional interval to delay requests by N seconds to reduce the number of requests sent.

    .. note::

        All other arguments are passed to the http.query state.
    """
    starttime = time.time()

    while True:
        caught_exception = None
        exception_type = None
        stacktrace = None
        ret = None
        try:
            ret = query(name, **kwargs)
            if ret["result"]:
                return ret
        except Exception as exc:  # pylint: disable=broad-except
            exception_type, caught_exception, stacktrace = sys.exc_info()

        if time.time() > starttime + wait_for:
            if not ret and caught_exception:
                raise caught_exception.with_traceback(stacktrace)
            return ret
        elif "request_interval" in kwargs:
            # Space requests out by delaying for an interval
            log.debug("delaying query for %s seconds.", kwargs["request_interval"])
            time.sleep(kwargs["request_interval"])
