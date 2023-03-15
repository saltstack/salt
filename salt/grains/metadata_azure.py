"""
Grains from cloud metadata servers at 169.254.169.254 in Azure Virtual Machine

.. versionadded:: 3006.0

:depends: requests

To enable these grains that pull from the http://169.254.169.254/metadata/instance?api-version=2020-09-01
metadata server set `metadata_server_grains: True` in the minion config.

.. code-block:: yaml

    metadata_server_grains: True

"""

import logging

import salt.utils.http as http
import salt.utils.json

HOST = "http://169.254.169.254"
URL = f"{HOST}/metadata/instance?api-version=2020-09-01"
log = logging.getLogger(__name__)


def __virtual__():
    # Check if metadata_server_grains minion option is enabled
    if __opts__.get("metadata_server_grains", False) is False:
        return False
    azuretest = http.query(
        URL, status=True, headers=True, header_list=["Metadata: true"]
    )
    if azuretest.get("status", 404) != 200:
        return False
    return True


def metadata():
    """Takes no arguments, returns a dictionary of metadata values from Azure."""
    log.debug("All checks true - loading azure metadata")
    result = http.query(URL, headers=True, header_list=["Metadata: true"])
    metadata = salt.utils.json.loads(result.get("body", {}))

    return metadata
