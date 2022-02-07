"""
A module to pull data from Foreman via its API into the Pillar dictionary


Configuring the Foreman ext_pillar
==================================

Set the following Salt config to setup Foreman as external pillar source:

.. code-block:: yaml

  ext_pillar:
    - foreman:
        key: foreman # Nest results within this key
        only: ['hostgroup_name', 'parameters'] # Add only these keys to pillar

  foreman.url: https://example.com/foreman_api
  foreman.user: username # default is admin
  foreman.password: password # default is changeme

The following options are optional:

.. code-block:: yaml

  foreman.api: apiversion # default is 2 (1 is not supported yet)
  foreman.verifyssl: False # default is True
  foreman.certfile: /etc/ssl/certs/mycert.pem # default is None
  foreman.keyfile: /etc/ssl/private/mykey.pem # default is None
  foreman.cafile: /etc/ssl/certs/mycert.ca.pem # default is None
  foreman.lookup_parameters: True # default is True

An alternative would be to use the Foreman modules integrating Salt features
in the Smart Proxy and the webinterface.

Further information can be found on `GitHub <https://github.com/theforeman/foreman_salt>`_.

Module Documentation
====================
"""

import logging

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

__opts__ = {
    "foreman.url": "http://foreman/api",
    "foreman.user": "admin",
    "foreman.password": "changeme",
    "foreman.api": 2,
    "foreman.verifyssl": True,
    "foreman.certfile": None,
    "foreman.keyfile": None,
    "foreman.cafile": None,
    "foreman.lookup_parameters": True,
}


# Set up logging
log = logging.getLogger(__name__)

# Declare virtualname
__virtualname__ = "foreman"


def __virtual__():
    """
    Only return if all the modules are available
    """
    if not HAS_REQUESTS:
        return False
    return __virtualname__


def ext_pillar(minion_id, pillar, key=None, only=()):  # pylint: disable=W0613
    """
    Read pillar data from Foreman via its API.
    """
    url = __opts__["foreman.url"]
    user = __opts__["foreman.user"]
    password = __opts__["foreman.password"]
    api = __opts__["foreman.api"]
    verify = __opts__["foreman.verifyssl"]
    certfile = __opts__["foreman.certfile"]
    keyfile = __opts__["foreman.keyfile"]
    cafile = __opts__["foreman.cafile"]
    lookup_parameters = __opts__["foreman.lookup_parameters"]

    log.info("Querying Foreman at %r for information for %r", url, minion_id)
    try:
        # Foreman API version 1 is currently not supported
        if api != 2:
            log.error(
                "Foreman API v2 is supported only, please specify"
                "version 2 in your Salt master config"
            )
            raise Exception

        headers = {"accept": "version=" + str(api) + ",application/json"}

        if verify and cafile is not None:
            verify = cafile

        resp = requests.get(
            url + "/hosts/" + minion_id,
            auth=(user, password),
            headers=headers,
            verify=verify,
            cert=(certfile, keyfile),
        )
        result = resp.json()

        log.debug("Raw response of the Foreman request is %r", result)

        if lookup_parameters:
            parameters = dict()
            for param in result["all_parameters"]:
                parameters.update({param["name"]: param["value"]})

            result["parameters"] = parameters

        if only:
            result = {k: result[k] for k in only if k in result}

    except Exception:  # pylint: disable=broad-except
        log.exception("Could not fetch host data via Foreman API:")
        return {}

    if key:
        result = {key: result}

    return result
