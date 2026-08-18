"""
Support for IFTTT

.. versionadded:: 2015.8.0

Requires an ``api_key`` in ``/etc/salt/minion``:

.. code-block:: yaml

    ifttt:
      secret_key: '280d4699-a817-4719-ba6f-ca56e573e44f'
"""

import logging
import time

import salt.utils.http
import salt.utils.json

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if apache is installed
    """
    if not __salt__["config.get"]("ifttt.secret_key") and not __salt__["config.get"](
        "ifttt:secret_key"
    ):
        return (False, "IFTTT Secret Key Unavailable, not loading.")
    return True


def _query(event=None, method="GET", args=None, header_dict=None, data=None):
    """
    Make a web call to IFTTT.
    """
    secret_key = __salt__["config.get"]("ifttt.secret_key") or __salt__["config.get"](
        "ifttt:secret_key"
    )
    path = f"https://maker.ifttt.com/trigger/{event}/with/key/{secret_key}"

    if header_dict is None:
        header_dict = {"Content-type": "application/json"}

    if method != "POST":
        header_dict["Accept"] = "application/json"

    result = salt.utils.http.query(
        path,
        method,
        params={},
        data=data,
        header_dict=header_dict,
        decode=True,
        decode_type="auto",
        text=True,
        status=True,
        cookies=True,
        persist_session=True,
        opts=__opts__,
        backend="requests",
    )
    return result


def trigger_event(event=None, **kwargs):
    """
    Trigger a configured event in IFTTT.

    :param event:   The name of the event to trigger.

    :return:        A dictionary with status, text, and error if result was failure.
    """

    res = {"result": False, "message": "Something went wrong"}

    data = {}
    for value in ("value1", "value2", "value3", "Value1", "Value2", "Value3"):
        if value in kwargs:
            data[value.lower()] = kwargs[value]
    data["occurredat"] = time.strftime("%B %d, %Y %I:%M%p", time.localtime())
    result = _query(event=event, method="POST", data=salt.utils.json.dumps(data))
    if "status" in result:
        if result["status"] == 200:
            res["result"] = True
            res["message"] = result["text"]
        else:
            if "error" in result:
                res["message"] = result["error"]
    return res
