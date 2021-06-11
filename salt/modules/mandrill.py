"""
Mandrill
========

Send out emails using the Mandrill_ API_.

.. _Mandrill: https://mandrillapp.com
.. _API: https://mandrillapp.com/api/docs/

In the minion configuration file, the following block is required:

.. code-block:: yaml

  mandrill:
    key: <API_KEY>

.. versionadded:: 2018.3.0
"""


import logging

import salt.utils.json
import salt.utils.versions

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

__virtualname__ = "mandrill"

log = logging.getLogger(__file__)

BASE_URL = "https://mandrillapp.com/api"
DEFAULT_VERSION = 1


def __virtual__():
    """
    Return the execution module virtualname.
    """
    if HAS_REQUESTS is False:
        return (
            False,
            "The requests python package is required for the mandrill execution module",
        )
    return __virtualname__


def _default_ret():
    """
    Default dictionary returned.
    """
    return {"result": False, "comment": "", "out": None}


def _get_api_params(api_url=None, api_version=None, api_key=None):
    """
    Retrieve the API params from the config file.
    """
    mandrill_cfg = __salt__["config.merge"]("mandrill")
    if not mandrill_cfg:
        mandrill_cfg = {}
    return {
        "api_url": api_url or mandrill_cfg.get("api_url") or BASE_URL,  # optional
        "api_key": api_key or mandrill_cfg.get("key"),  # mandatory
        "api_version": api_version
        or mandrill_cfg.get("api_version")
        or DEFAULT_VERSION,
    }


def _get_url(method, api_url, api_version):
    """
    Build the API URL.
    """
    return "{url}/{version}/{method}.json".format(
        url=api_url, version=float(api_version), method=method
    )


def _get_headers():
    """
    Return HTTP headers required for the Mandrill API.
    """
    return {"content-type": "application/json", "user-agent": "Mandrill-Python/1.0.57"}


def _http_request(url, headers=None, data=None):
    """
    Make the HTTP request and return the body as python object.
    """
    if not headers:
        headers = _get_headers()
    session = requests.session()
    log.debug("Querying %s", url)
    req = session.post(url, headers=headers, data=salt.utils.json.dumps(data))
    req_body = req.json()
    ret = _default_ret()
    log.debug("Status code: %d", req.status_code)
    log.debug("Response body:")
    log.debug(req_body)
    if req.status_code != 200:
        if req.status_code == 500:
            ret["comment"] = req_body.pop("message", "")
            ret["out"] = req_body
            return ret
        ret.update({"comment": req_body.get("error", "")})
        return ret
    ret.update({"result": True, "out": req.json()})
    return ret


# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def send(
    message,
    asynchronous=False,
    ip_pool=None,
    send_at=None,
    api_url=None,
    api_version=None,
    api_key=None,
):
    """
    Send out the email using the details from the ``message`` argument.

    message
        The information on the message to send. This argument must be
        sent as dictionary with at fields as specified in the Mandrill API
        documentation.

    asynchronous: ``False``
        Enable a background sending mode that is optimized for bulk sending.
        In asynchronous mode, messages/send will immediately return a status of
        "queued" for every recipient. To handle rejections when sending in asynchronous
        mode, set up a webhook for the 'reject' event. Defaults to false for
        messages with no more than 10 recipients; messages with more than 10
        recipients are always sent asynchronously, regardless of the value of
        asynchronous.

    ip_pool
        The name of the dedicated ip pool that should be used to send the
        message. If you do not have any dedicated IPs, this parameter has no
        effect. If you specify a pool that does not exist, your default pool
        will be used instead.

    send_at
        When this message should be sent as a UTC timestamp in
        ``YYYY-MM-DD HH:MM:SS`` format. If you specify a time in the past,
        the message will be sent immediately. An additional fee applies for
        scheduled email, and this feature is only available to accounts with a
        positive balance.

    .. note::
        Fur further details please consult the `API documentation <https://mandrillapp.com/api/docs/messages.dart.html>`_.

    CLI Example:

    .. code-block:: bash

        salt '*' mandrill.send message="{'subject': 'Hi', 'from_email': 'test@example.com', 'to': [{'email': 'recv@example.com', 'type': 'to'}]}"

    ``message`` structure example (as YAML for readability):

    .. code-block:: yaml

        message:
            text: |
                This is the body of the email.
                This is the second line.
            subject: Email subject
            from_name: Test At Example Dot Com
            from_email: test@example.com
            to:
              - email: recv@example.com
                type: to
                name: Recv At Example Dot Com
              - email: cc@example.com
                type: cc
                name: CC At Example Dot Com
            important: true
            track_clicks: true
            track_opens: true
            attachments:
              - type: text/x-yaml
                name: yaml_file.yml
                content: aV9hbV9zdXBlcl9jdXJpb3VzOiB0cnVl

    Output example:

    .. code-block:: bash

        minion:
            ----------
            comment:
            out:
                |_
                  ----------
                  _id:
                      c4353540a3c123eca112bbdd704ab6
                  email:
                      recv@example.com
                  reject_reason:
                      None
                  status:
                      sent
            result:
                True
    """
    params = _get_api_params(api_url=api_url, api_version=api_version, api_key=api_key)
    url = _get_url(
        "messages/send", api_url=params["api_url"], api_version=params["api_version"]
    )
    data = {
        "key": params["api_key"],
        "message": message,
        "async": asynchronous,
        "ip_pool": ip_pool,
        "send_at": send_at,
    }
    return _http_request(url, data=data)
