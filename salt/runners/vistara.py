"""
Vistara Runner

Runner to interact with the Vistara (http://www.vistarait.com/) REST API

:codeauthor: Brad Thurber <brad.thurber@gmail.com>

To use this runner, the Vistara client_id and Vistara oauth2 client_key
and client_secret must be set in the master config.

For example ``/etc/salt/master.d/_vistara.conf``:

.. code-block:: yaml

    vistara:
      client_id: client_012345
      client_key: N0tReallyaR3alKeyButShouldB12345
      client_secret: ThisI5AreallyLongsecretKeyIwonderwhyTheyMakethemSoBigTheseDays00


"""

import logging

import salt.output

# See https://docs.saltproject.io/en/latest/topics/tutorials/http.html
import salt.utils.http

log = logging.getLogger(__name__)


def __virtual__():
    """
    Check to see if master config has the necessary config
    """
    vistara_config = __opts__["vistara"] if "vistara" in __opts__ else None

    if vistara_config:
        client_id = vistara_config.get("client_id", None)
        client_key = vistara_config.get("client_key", None)
        client_secret = vistara_config.get("client_secret", None)

        if not client_id or not client_key or not client_secret:
            return (
                False,
                "vistara client_id or client_key or client_secret "
                "has not been specified in the Salt master config.",
            )
        return True

    return (
        False,
        "vistara config has not been specificed in the Salt master "
        "config. See documentation for this runner.",
    )


def _get_vistara_configuration():
    """
    Return the Vistara configuration read from the master config
    """
    return {
        "client_id": __opts__["vistara"]["client_id"],
        "client_key": __opts__["vistara"]["client_key"],
        "client_secret": __opts__["vistara"]["client_secret"],
    }


def delete_device(name, safety_on=True):
    """
    Deletes a device from Vistara based on DNS name or partial name. By default,
    delete_device will only perform the delete if a single host is returned. Set
    safety_on=False to delete all matches (up to default API search page size)

    CLI Example:

    .. code-block:: bash

        salt-run vistara.delete_device 'hostname-101.mycompany.com'
        salt-run vistara.delete_device 'hostname-101'
        salt-run vistara.delete_device 'hostname-1' safety_on=False

    """

    config = _get_vistara_configuration()
    if not config:
        return False

    access_token = _get_oath2_access_token(
        config["client_key"], config["client_secret"]
    )

    if not access_token:
        return "Vistara access token not available"

    query_string = "dnsName:{}".format(name)

    devices = _search_devices(query_string, config["client_id"], access_token)

    if not devices:
        return "No devices found"

    device_count = len(devices)

    if safety_on and device_count != 1:
        return (
            "Expected to delete 1 device and found {}. "
            "Set safety_on=False to override.".format(device_count)
        )

    delete_responses = []
    for device in devices:
        device_id = device["id"]
        log.debug(device_id)
        delete_response = _delete_resource(device_id, config["client_id"], access_token)
        if not delete_response:
            return False
        delete_responses.append(delete_response)

    return delete_responses


def _search_devices(query_string, client_id, access_token):

    authstring = "Bearer {}".format(access_token)

    headers = {
        "Authorization": authstring,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    params = {"queryString": query_string}

    method = "GET"
    url = "https://api.vistara.io/api/v2/tenants/{}/devices/search".format(client_id)

    resp = salt.utils.http.query(
        url=url, method=method, header_dict=headers, params=params, opts=__opts__
    )

    respbody = resp.get("body", None)
    if not respbody:
        return False

    respbodydict = salt.utils.json.loads(resp["body"])
    deviceresults = respbodydict["results"]

    return deviceresults


def _delete_resource(device_id, client_id, access_token):

    authstring = "Bearer {}".format(access_token)

    headers = {
        "Authorization": authstring,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    method = "DELETE"
    url = "https://api.vistara.io/api/v2/tenants/{}/rtype/DEVICE/resource/{}".format(
        client_id, device_id
    )

    resp = salt.utils.http.query(
        url=url, method=method, header_dict=headers, opts=__opts__
    )

    respbody = resp.get("body", None)
    if not respbody:
        return False

    respbodydict = salt.utils.json.loads(resp["body"])

    return respbodydict


def _get_oath2_access_token(client_key, client_secret):
    """
    Query the vistara API and get an access_token

    """
    if not client_key and not client_secret:
        log.error(
            "client_key and client_secret have not been specified "
            "and are required parameters."
        )
        return False

    method = "POST"
    url = "https://api.vistara.io/auth/oauth/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    params = {
        "grant_type": "client_credentials",
        "client_id": client_key,
        "client_secret": client_secret,
    }

    resp = salt.utils.http.query(
        url=url, method=method, header_dict=headers, params=params, opts=__opts__
    )

    respbody = resp.get("body", None)

    if not respbody:
        return False

    access_token = salt.utils.json.loads(respbody)["access_token"]
    return access_token
