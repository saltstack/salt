# -*- coding: utf-8 -*-
"""
Library for interacting with Mattermost Incoming Webhooks
:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.
    For example:
    .. code-block:: yaml
        mattermost:
          hook: 3tdgo8restnxiykdx88wqtxryr
          api_url: https://example.com
"""
from __future__ import absolute_import, unicode_literals

import logging

import salt.ext.six.moves.http_client

# pylint: enable=import-error,no-name-in-module
import salt.utils.http
from salt.ext import six

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
from salt.version import __version__

log = logging.getLogger(__name__)


def query(hook=None, api_url=None, data=None):
    """
    Mattermost object method function to construct and execute on the API URL.
    :param api_url:     The Mattermost API URL
    :param hook:        The Mattermost hook.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    """
    method = "POST"

    ret = {"message": "", "res": True}

    base_url = _urljoin(api_url, "/hooks/")
    url = _urljoin(base_url, six.text_type(hook))

    result = salt.utils.http.query(url, method, data=data, decode=True, status=True)

    if result.get("status", None) == salt.ext.six.moves.http_client.OK:
        ret["message"] = "Message posted {0} correctly".format(data)
        return ret
    elif result.get("status", None) == salt.ext.six.moves.http_client.NO_CONTENT:
        return True
    else:
        log.debug(url)
        log.debug(data)
        log.debug(result)
        if "dict" in result:
            _result = result["dict"]
            if "error" in _result:
                ret["message"] = result["error"]
                ret["res"] = False
                return ret
            ret["message"] = "Message not posted"
        else:
            ret["message"] = "invalid_auth"
            ret["res"] = False
    return ret
