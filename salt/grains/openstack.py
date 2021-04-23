"""
Grains from `OpenStack metadata service`__.

.. __: https://docs.openstack.org/nova/latest/user/metadata.html#the-metadata-service

.. versionadded:: 3003

Metadata from Nova (`meta_data.json`) is stored on the `"nova"` sub-key, and
metadata from Neutron (`network_data.json`) is stored on the `"neutron"`
sub-key. For more information on the format of this data, please see the
OpenStack Metadata service `documentation`__.

.. __: https://docs.openstack.org/nova/latest/user/metadata.html#metadata-openstack-format

:maintainer: Zane Mingee <zmingee@gmail.com>
:maturity: stable
:platform: all

To enable these grains, set :conf_minion:`openstack_metadata_grains` to
``True``:

.. code-block:: yaml

    openstack_metadata_grains: True

The following options are enabled by default:

.. code-block:: yaml

    openstack_metadata_version: latest

"""
import json
import logging
import socket

import salt.utils.http

LOGGER = logging.getLogger(__name__)
METADATA_IP = "169.254.169.254"
METADATA_MAP = {"nova": "meta_data.json", "neutron": "network_data.json"}


def __virtual__():
    if __opts__.get("openstack_metadata_grains", False) is False:
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0)
    try:
        sock.connect((METADATA_IP, 80))
    except BlockingIOError:
        pass
    except OSError:
        return False

    metadata_url = "http://{}/openstack/{}".format(
        METADATA_IP, __opts__.get("openstack_metadata_version", "latest")
    )
    if salt.utils.http.query(metadata_url, status=True).get("status") != 200:
        return False

    return True


def _normalize_dict(data):
    output = {}
    for (key, value) in data.items():
        if isinstance(value, dict):
            value = _normalize_dict(value)
        if isinstance(value, str):
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.lower() == "none" or value.lower() == "null":
                value = None
        output[key] = value
    return output


def get_metadata():
    metadata = {}
    for (service, path) in METADATA_MAP.items():
        metadata_url = "http://{}/openstack/{}/{}".format(
            METADATA_IP, __opts__.get("openstack_metadata_version", "latest"), path
        )

        resp = salt.utils.http.query(metadata_url)
        if resp.get("error"):
            LOGGER.error("Metadata query failed: %s", resp["error"])
            return None

        try:
            metadata[service] = json.loads(resp["body"])
        except json.decoder.JSONDecodeError:
            LOGGER.error("Invalid metadata: %s", resp["body"])
            return None

    return {"openstack": _normalize_dict(metadata)}
