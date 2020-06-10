# -*- coding: utf-8 -*-
"""
HTTP - engine
==========================

An engine that reads messages from the salt event bus and pushes
them onto a desired endpoint via HTTP requests.

.. note::
    By default, this engine take everything from the Salt bus and exports into
    defined http endpoint.

:configuration: Example configuration

    .. code-block:: yaml

        engines:
          - http:
              urls:
                  - http://automation.example.com/saltevent
                  - http://localhost:9000/api/v1/events
              headers:
                  X-AUTH-TOKEN: saltapiusertoken
                  AnotherCustomToken: loremipsum
              tags:
                  - salt/job/*/new
                  - salt/job/*/ret/*
              funs:
                  - probes.results
                  - bgp.config
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import python lib
import fnmatch

# Import salt libs
import salt.config
import salt.utils.event
import salt.utils.http
import salt.utils.json

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

_HEADERS = {"Content-Type": "application/json"}

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------


def _http_endpoint(url, data):
    """
    Issues HTTP queries to defined server.
    """
    result = salt.utils.http.query(
        url,
        "POST",
        header_dict=_HEADERS,
        data=salt.utils.json.dumps(data),
        decode=False,
        status=True,
        opts=__opts__,
    )
    return result


# ----------------------------------------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------------------------------------


def start(urls, headers=None, tags=None, funs=None):
    """
    Listen to salt events and forward them to desired endpoint.

    url
        The endpoint.
    headers
        headers which will be included in http headers
    """

    if headers is not None:
        for k, v in headers.items():
            _HEADERS[k] = v

    if __opts__.get("id").endswith("_master"):
        instance = "master"
    else:
        instance = "minion"

    event_bus = salt.utils.event.get_event(
        instance,
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
        opts=__opts__,
    )
    while True:
        event = event_bus.get_event(full=True)
        if event:
            publish = True
            if tags and isinstance(tags, list):
                found_match = False
                for tag in tags:
                    if fnmatch.fnmatch(event["tag"], tag):
                        found_match = True
                publish = found_match
            if funs and "fun" in event["data"]:
                if not event["data"]["fun"] in funs:
                    publish = False
            if publish:
                for url in urls:
                    _http_endpoint(url, event)
