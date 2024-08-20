"""
Library for interacting with Pushover API

.. versionadded:: 2016.3.0
"""

import http.client
import logging
from urllib.parse import urlencode, urljoin

import salt.utils.http
from salt.version import __version__

log = logging.getLogger(__name__)


def query(
    function,
    token=None,
    api_version="1",
    method="POST",
    header_dict=None,
    data=None,
    query_params=None,
    opts=None,
):
    """
    PushOver object method function to construct and execute on the API URL.

    :param token:       The PushOver api key.
    :param api_version: The PushOver API version to use, defaults to version 1.
    :param function:    The PushOver api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    """

    ret = {"message": "", "res": True}

    pushover_functions = {
        "message": {"request": "messages.json", "response": "status"},
        "validate_user": {"request": "users/validate.json", "response": "status"},
        "validate_sound": {"request": "sounds.json", "response": "status"},
    }

    api_url = "https://api.pushover.net"
    base_url = urljoin(api_url, api_version + "/")
    path = pushover_functions.get(function).get("request")
    url = urljoin(base_url, path, False)

    if not query_params:
        query_params = {}

    decode = True
    if method == "DELETE":
        decode = False

    result = salt.utils.http.query(
        url,
        method,
        params=query_params,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type="json",
        text=True,
        status=True,
        cookies=True,
        persist_session=True,
        opts=opts,
    )

    if result.get("status", None) == http.client.OK:
        response = pushover_functions.get(function).get("response")
        if response in result and result[response] == 0:
            ret["res"] = False
        ret["message"] = result
        return ret
    else:
        try:
            if "response" in result and result[response] == 0:
                ret["res"] = False
            ret["message"] = result
        except ValueError:
            ret["res"] = False
            ret["message"] = result
        return ret


def validate_sound(sound, token):
    """
    Send a message to a Pushover user or group.
    :param sound:       The sound that we want to verify
    :param token:       The PushOver token.
    """
    ret = {"message": "Sound is invalid", "res": False}
    parameters = dict()
    parameters["token"] = token

    response = query(function="validate_sound", method="GET", query_params=parameters)

    if response["res"]:
        if "message" in response:
            _message = response.get("message", "")
            if "status" in _message:
                if _message.get("dict", {}).get("status", "") == 1:
                    sounds = _message.get("dict", {}).get("sounds", "")
                    if sound in sounds:
                        ret["message"] = f"Valid sound {sound}."
                        ret["res"] = True
                    else:
                        ret["message"] = f"Warning: {sound} not a valid sound."
                        ret["res"] = False
                else:
                    ret["message"] = "".join(_message.get("dict", {}).get("errors"))
    return ret


def validate_user(user, device, token):
    """
    Send a message to a Pushover user or group.
    :param user:        The user or group name, either will work.
    :param device:      The device for the user.
    :param token:       The PushOver token.
    """
    res = {"message": "User key is invalid", "result": False}

    parameters = dict()
    parameters["user"] = user
    parameters["token"] = token
    if device:
        parameters["device"] = device

    response = query(
        function="validate_user",
        method="POST",
        header_dict={"Content-Type": "application/x-www-form-urlencoded"},
        data=urlencode(parameters),
    )

    if response["res"]:
        if "message" in response:
            _message = response.get("message", "")
            if "status" in _message:
                if _message.get("dict", {}).get("status", None) == 1:
                    res["result"] = True
                    res["message"] = "User key is valid."
                else:
                    res["result"] = False
                    res["message"] = "".join(_message.get("dict", {}).get("errors"))
    return res
