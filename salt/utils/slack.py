"""
Library for interacting with Slack API

.. versionadded:: 2016.3.0

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.

    For example:

    .. code-block:: yaml

        slack:
          api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
"""

import http.client
import logging
import urllib.parse

import salt.utils.http

log = logging.getLogger(__name__)


def query(
    function,
    api_key=None,
    args=None,
    method="GET",
    header_dict=None,
    data=None,
    opts=None,
):
    """
    Slack object method function to construct and execute on the API URL.

    :param api_key:     The Slack api key.
    :param function:    The Slack api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    """

    ret = {"message": "", "res": True}

    slack_functions = {
        "rooms": {"request": "channels.list", "response": "channels"},
        "users": {"request": "users.list", "response": "members"},
        "message": {"request": "chat.postMessage", "response": "channel"},
    }

    if not api_key:
        api_key = __salt__["config.get"]("slack.api_key") or __salt__["config.get"](
            "slack:api_key"
        )

        if not api_key:
            log.error("No Slack api key found.")
            ret["message"] = "No Slack api key found."
            ret["res"] = False
            return ret

    api_url = "https://slack.com"
    base_url = urllib.parse.urljoin(api_url, "/api/")
    path = slack_functions.get(function).get("request")
    url = urllib.parse.urljoin(base_url, path, False)

    if not isinstance(args, dict):
        query_params = {}
    else:
        query_params = args.copy()

    if header_dict is None:
        header_dict = {}

    if method != "POST":
        header_dict["Accept"] = "application/json"

    # https://api.slack.com/changelog/2020-11-no-more-tokens-in-querystrings-for
    # -newly-created-apps
    # Apps created after February 24, 2021 may no longer send tokens as query
    # parameters and must instead use an HTTP authorization header or
    # send the token in an HTTP POST body.
    # Apps created before February 24, 2021 will continue functioning no
    # matter which way you pass your token.
    header_dict["Authorization"] = "Bearer {}".format(api_key)
    result = salt.utils.http.query(
        url,
        method,
        params=query_params,
        data=data,
        decode=True,
        status=True,
        header_dict=header_dict,
        opts=opts,
    )

    if result.get("status", None) == http.client.OK:
        _result = result["dict"]
        response = slack_functions.get(function).get("response")
        if "error" in _result:
            ret["message"] = _result["error"]
            ret["res"] = False
            return ret
        ret["message"] = _result.get(response)
        return ret
    elif result.get("status", None) == http.client.NO_CONTENT:
        return True
    else:
        log.debug(url)
        log.debug(query_params)
        log.debug(data)
        log.debug(result)
        if "dict" in result:
            _result = result["dict"]
            if "error" in _result:
                ret["message"] = result["error"]
                ret["res"] = False
                return ret
            ret["message"] = "Unknown response"
            ret["res"] = False
        else:
            ret["message"] = "invalid_auth"
            ret["res"] = False
        return ret
