"""
Library for interacting with PagerDuty API

.. versionadded:: 2014.7.0

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.

    For example:

    .. code-block:: yaml

        my-pagerduty-account:
            pagerduty.subdomain: mysubdomain
            pagerduty.api_key: F3Rbyjbve43rfFWf2214
"""

import logging

import salt.utils.http
import salt.utils.json
from salt.version import __version__

log = logging.getLogger(__name__)


def query(
    method="GET",
    profile_dict=None,
    url=None,
    path="api/v1",
    action=None,
    api_key=None,
    service=None,
    params=None,
    data=None,
    subdomain=None,
    client_url=None,
    description=None,
    opts=None,
    verify_ssl=True,
):
    """
    Query the PagerDuty API
    """
    user_agent = "SaltStack {}".format(__version__)

    if opts is None:
        opts = {}

    if isinstance(profile_dict, dict):
        creds = profile_dict
    else:
        creds = {}

    if api_key is not None:
        creds["pagerduty.api_key"] = api_key

    if service is not None:
        creds["pagerduty.service"] = service

    if subdomain is not None:
        creds["pagerduty.subdomain"] = subdomain

    if client_url is None:
        client_url = "https://{}.pagerduty.com".format(creds["pagerduty.subdomain"])

    if url is None:
        url = "https://{}.pagerduty.com/{}/{}".format(
            creds["pagerduty.subdomain"], path, action
        )

    if params is None:
        params = {}

    if data is None:
        data = {}

    data["client"] = user_agent

    # pagerduty.service is not documented.  While it makes sense to have in
    # some cases, don't force it when it is not defined.
    if "pagerduty.service" in creds and creds["pagerduty.service"] is not None:
        data["service_key"] = creds["pagerduty.service"]
    data["client_url"] = client_url
    if "event_type" not in data:
        data["event_type"] = "trigger"
    if "description" not in data:
        if not description:
            data["description"] = "SaltStack Event Triggered"
        else:
            data["description"] = description

    headers = {
        "User-Agent": user_agent,
        "Authorization": "Token token={}".format(creds["pagerduty.api_key"]),
    }
    if method == "GET":
        data = {}
    else:
        headers["Content-type"] = "application/json"

    result = salt.utils.http.query(
        url,
        method,
        params=params,
        header_dict=headers,
        data=salt.utils.json.dumps(data),
        decode=False,
        text=True,
        opts=opts,
    )

    return result["text"]


def list_items(action, key, profile_dict=None, api_key=None, opts=None):
    """
    List items belonging to an API call. Used for list_services() and
    list_incidents()
    """
    items = salt.utils.json.loads(
        query(profile_dict=profile_dict, api_key=api_key, action=action, opts=opts)
    )
    ret = {}
    for item in items[action]:
        ret[item[key]] = item
    return ret
