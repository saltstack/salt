"""
Grains from cloud metadata servers at 169.254.169.254 in
google compute engine

.. versionadded:: 3005.0

:depends: requests

To enable these grains that pull from the http://169.254.169.254/computeMetadata/v1/
metadata server set `metadata_server_grains: True` in the minion config.

.. code-block:: yaml

    metadata_server_grains: True

"""

import salt.utils.http as http
import salt.utils.json
import logging

__virtualname__ = "gce"
IP = "169.254.169.254"
URL = f"http://{IP}/computeMetadata/v1/?alt=json&recursive=true"
log = logging.getLogger(__name__)

def __virtual__():
    checks = []
    # Check if metadata_server_grains minion option is enabled
    if __opts__.get("metadata_server_grains", False) is False:
        checks.append(False)
    else:
        checks.append(True)

    # Check if metadata server is reachable
    googletest = http.query(f"http://{IP}", status=True, headers=True)
    if googletest.get("status", 404) == 200:
        checks.append(True)
    else:
        checks.append(False)

    # Check if headers include Google flavor
    if googletest.get("headers", {}).get("Metadata-Flavor", False) == "Google":
        checks.append(True)
    else:
        checks.append(False)

    # Only load the module if all checks were True
    if all(checks):
        log.debug("All checks true - loading gce metadata")
        return __virtualname__
    else:
        log.debug("Some checks false - skipping gce metadata")
        return False

def fetch_gce_metadata():
    result = http.query(URL, headers=True, header_list=['Metadata-Flavor: Google'])
    metadata = salt.utils.json.loads(result.get('body',{}))

    return metadata


