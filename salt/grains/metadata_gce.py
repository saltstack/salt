"""
Grains from cloud metadata servers at 169.254.169.254 in
google compute engine

.. versionadded:: 3005

:depends: requests

To enable these grains that pull from the http://169.254.169.254/computeMetadata/v1/
metadata server remove "metadata_server" from "disabled_grains" in the minion config.
"""

import logging

import salt.utils.http as http
import salt.utils.json

HOST = "http://169.254.169.254"
URL = f"{HOST}/computeMetadata/v1/?alt=json&recursive=true"
log = logging.getLogger(__name__)


def __virtual__():
    # Check if metadata_server_grains minion option is enabled
    if "metadata_server" in __opts__.get("disabled_grains", []):
        return False
    googletest = http.query(HOST, status=True, headers=True)
    if (
        googletest.get("status", 404) != 200
        or googletest.get("headers", {}).get("Metadata-Flavor", False) != "Google"
    ):
        return False
    return True


def metadata():
    """Takes no arguments, returns a dictionary of metadata values from Google."""
    log.debug("All checks true - loading gce metadata")
    result = http.query(URL, headers=True, header_list=["Metadata-Flavor: Google"])
    metadata = salt.utils.json.loads(result.get("body", {}))

    return metadata
