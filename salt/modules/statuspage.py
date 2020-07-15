# -*- coding: utf-8 -*-
"""
StatusPage
==========

Handle requests for the StatusPage_ API_.

.. _StatusPage: https://www.statuspage.io/
.. _API: http://doers.statuspage.io/api/v1/

In the minion configuration file, the following block is required:

.. code-block:: yaml

  statuspage:
    api_key: <API_KEY>
    page_id: <PAGE_ID>

.. versionadded:: 2017.7.0
"""

from __future__ import absolute_import, print_function, unicode_literals

# import python std lib
import logging

# import salt
from salt.ext import six

# import third party
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "statuspage"

log = logging.getLogger(__file__)

BASE_URL = "https://api.statuspage.io"
DEFAULT_VERSION = 1

UPDATE_FORBIDDEN_FILEDS = [
    "id",  # can't rewrite this
    "created_at",
    "updated_at",  # updated_at and created_at are handled by the backend framework of the API
    "page_id",  # can't move it to a different page
]
INSERT_FORBIDDEN_FILEDS = UPDATE_FORBIDDEN_FILEDS[:]  # they are the same for the moment

METHOD_OK_STATUS = {"POST": 201, "DELETE": 204}

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    Return the execution module virtualname.
    """
    if HAS_REQUESTS is False:
        return False, "The requests python package is not installed"
    return __virtualname__


def _default_ret():
    """
    Default dictionary returned.
    """
    return {"result": False, "comment": "", "out": None}


def _get_api_params(api_url=None, page_id=None, api_key=None, api_version=None):
    """
    Retrieve the API params from the config file.
    """
    statuspage_cfg = __salt__["config.get"]("statuspage")
    if not statuspage_cfg:
        statuspage_cfg = {}
    return {
        "api_url": api_url or statuspage_cfg.get("api_url") or BASE_URL,  # optional
        "api_page_id": page_id or statuspage_cfg.get("page_id"),  # mandatory
        "api_key": api_key or statuspage_cfg.get("api_key"),  # mandatory
        "api_version": api_version
        or statuspage_cfg.get("api_version")
        or DEFAULT_VERSION,
    }


def _validate_api_params(params):
    """
    Validate the API params as specified in the config file.
    """
    # page_id and API key are mandatory and they must be string/unicode
    return isinstance(
        params["api_page_id"], (six.string_types, six.text_type)
    ) and isinstance(params["api_key"], (six.string_types, six.text_type))


def _get_headers(params):
    """
    Return HTTP headers required.
    """
    return {"Authorization": "OAuth {oauth}".format(oauth=params["api_key"])}


def _http_request(url, method="GET", headers=None, data=None):
    """
    Make the HTTP request and return the body as python object.
    """
    req = requests.request(method, url, headers=headers, data=data)
    ret = _default_ret()
    ok_status = METHOD_OK_STATUS.get(method, 200)
    if req.status_code != ok_status:
        ret.update({"comment": req.json().get("error", "")})
        return ret
    ret.update(
        {
            "result": True,
            "out": req.json() if method != "DELETE" else None,  # no body when DELETE
        }
    )
    return ret


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def create(
    endpoint="incidents",
    api_url=None,
    page_id=None,
    api_key=None,
    api_version=None,
    **kwargs
):
    """
    Insert a new entry under a specific endpoint.

    endpoint: incidents
        Insert under this specific endpoint.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    CLI Example:

    .. code-block:: bash

        salt 'minion' statuspage.create endpoint='components' name='my component' group_id='993vgplshj12'

    Example output:

    .. code-block:: bash

        minion:
            ----------
            comment:
            out:
                ----------
                created_at:
                    2017-01-05T19:35:27.135Z
                description:
                    None
                group_id:
                    993vgplshj12
                id:
                    mjkmtt5lhdgc
                name:
                    my component
                page_id:
                    ksdhgfyiuhaa
                position:
                    7
                status:
                    operational
                updated_at:
                    2017-01-05T19:35:27.135Z
            result:
                True
    """
    params = _get_api_params(
        api_url=api_url, page_id=page_id, api_key=api_key, api_version=api_version
    )
    if not _validate_api_params(params):
        log.error("Invalid API params.")
        log.error(params)
        return {"result": False, "comment": "Invalid API params. See log for details"}
    endpoint_sg = endpoint[:-1]  # singular
    headers = _get_headers(params)
    create_url = "{base_url}/v{version}/pages/{page_id}/{endpoint}.json".format(
        base_url=params["api_url"],
        version=params["api_version"],
        page_id=params["api_page_id"],
        endpoint=endpoint,
    )
    change_request = {}
    for karg, warg in six.iteritems(kwargs):
        if warg is None or karg.startswith("__") or karg in INSERT_FORBIDDEN_FILEDS:
            continue
        change_request_key = "{endpoint_sg}[{karg}]".format(
            endpoint_sg=endpoint_sg, karg=karg
        )
        change_request[change_request_key] = warg
    return _http_request(
        create_url, method="POST", headers=headers, data=change_request
    )


def retrieve(
    endpoint="incidents", api_url=None, page_id=None, api_key=None, api_version=None
):
    """
    Retrieve a specific endpoint from the Statuspage API.

    endpoint: incidents
        Request a specific endpoint.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    CLI Example:

    .. code-block:: bash

        salt 'minion' statuspage.retrieve components

    Example output:

    .. code-block:: bash

        minion:
            ----------
            comment:
            out:
                |_
                  ----------
                  backfilled:
                      False
                  created_at:
                      2015-01-26T20:25:02.702Z
                  id:
                      kh2qwjbheqdc36
                  impact:
                      major
                  impact_override:
                      None
                  incident_updates:
                      |_
                        ----------
                        affected_components:
                            None
                        body:
                            We are currently investigating this issue.
                        created_at:
                            2015-01-26T20:25:02.849Z
                        display_at:
                            2015-01-26T20:25:02.849Z
                        id:
                            zvx7xz2z5skr
                        incident_id:
                            kh2qwjbheqdc36
                        status:
                            investigating
                        twitter_updated_at:
                            None
                        updated_at:
                            2015-01-26T20:25:02.849Z
                        wants_twitter_update:
                            False
                  monitoring_at:
                      None
                  name:
                      just testing some stuff
                  page_id:
                      ksdhgfyiuhaa
                  postmortem_body:
                      None
                  postmortem_body_last_updated_at:
                      None
                  postmortem_ignored:
                      False
                  postmortem_notified_subscribers:
                      False
                  postmortem_notified_twitter:
                      False
                  postmortem_published_at:
                      None
                  resolved_at:
                      None
                  scheduled_auto_completed:
                      False
                  scheduled_auto_in_progress:
                      False
                  scheduled_for:
                      None
                  scheduled_remind_prior:
                      False
                  scheduled_reminded_at:
                      None
                  scheduled_until:
                      None
                  shortlink:
                      http://stspg.io/voY
                  status:
                      investigating
                  updated_at:
                      2015-01-26T20:25:13.379Z
            result:
                True
    """
    params = _get_api_params(
        api_url=api_url, page_id=page_id, api_key=api_key, api_version=api_version
    )
    if not _validate_api_params(params):
        log.error("Invalid API params.")
        log.error(params)
        return {"result": False, "comment": "Invalid API params. See log for details"}
    headers = _get_headers(params)
    retrieve_url = "{base_url}/v{version}/pages/{page_id}/{endpoint}.json".format(
        base_url=params["api_url"],
        version=params["api_version"],
        page_id=params["api_page_id"],
        endpoint=endpoint,
    )
    return _http_request(retrieve_url, headers=headers)


def update(
    endpoint="incidents",
    id=None,
    api_url=None,
    page_id=None,
    api_key=None,
    api_version=None,
    **kwargs
):
    """
    Update attribute(s) of a specific endpoint.

    id
        The unique ID of the enpoint entry.

    endpoint: incidents
        Endpoint name.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    CLI Example:

    .. code-block:: bash

        salt 'minion' statuspage.update id=dz959yz2nd4l status=resolved

    Example output:

    .. code-block:: bash

        minion:
            ----------
            comment:
            out:
                ----------
                created_at:
                    2017-01-03T15:25:30.718Z
                description:
                    None
                group_id:
                    993vgplshj12
                id:
                    dz959yz2nd4l
                name:
                    Management Portal
                page_id:
                    xzwjjdw87vpf
                position:
                    11
                status:
                    resolved
                updated_at:
                    2017-01-05T15:34:27.676Z
            result:
                True
    """
    endpoint_sg = endpoint[:-1]  # singular
    if not id:
        log.error("Invalid %s ID", endpoint_sg)
        return {
            "result": False,
            "comment": "Please specify a valid {endpoint} ID".format(
                endpoint=endpoint_sg
            ),
        }
    params = _get_api_params(
        api_url=api_url, page_id=page_id, api_key=api_key, api_version=api_version
    )
    if not _validate_api_params(params):
        log.error("Invalid API params.")
        log.error(params)
        return {"result": False, "comment": "Invalid API params. See log for details"}
    headers = _get_headers(params)
    update_url = "{base_url}/v{version}/pages/{page_id}/{endpoint}/{id}.json".format(
        base_url=params["api_url"],
        version=params["api_version"],
        page_id=params["api_page_id"],
        endpoint=endpoint,
        id=id,
    )
    change_request = {}
    for karg, warg in six.iteritems(kwargs):
        if warg is None or karg.startswith("__") or karg in UPDATE_FORBIDDEN_FILEDS:
            continue
        change_request_key = "{endpoint_sg}[{karg}]".format(
            endpoint_sg=endpoint_sg, karg=karg
        )
        change_request[change_request_key] = warg
    return _http_request(
        update_url, method="PATCH", headers=headers, data=change_request
    )


def delete(
    endpoint="incidents",
    id=None,
    api_url=None,
    page_id=None,
    api_key=None,
    api_version=None,
):
    """
    Remove an entry from an endpoint.

    endpoint: incidents
        Request a specific endpoint.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    CLI Example:

    .. code-block:: bash

        salt 'minion' statuspage.delete endpoint='components' id='ftgks51sfs2d'

    Example output:

    .. code-block:: bash

        minion:
            ----------
            comment:
            out:
                None
            result:
                True
    """
    params = _get_api_params(
        api_url=api_url, page_id=page_id, api_key=api_key, api_version=api_version
    )
    if not _validate_api_params(params):
        log.error("Invalid API params.")
        log.error(params)
        return {"result": False, "comment": "Invalid API params. See log for details"}
    endpoint_sg = endpoint[:-1]  # singular
    if not id:
        log.error("Invalid %s ID", endpoint_sg)
        return {
            "result": False,
            "comment": "Please specify a valid {endpoint} ID".format(
                endpoint=endpoint_sg
            ),
        }
    headers = _get_headers(params)
    delete_url = "{base_url}/v{version}/pages/{page_id}/{endpoint}/{id}.json".format(
        base_url=params["api_url"],
        version=params["api_version"],
        page_id=params["api_page_id"],
        endpoint=endpoint,
        id=id,
    )
    return _http_request(delete_url, method="DELETE", headers=headers)
