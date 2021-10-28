"""
Grains from cloud metadata servers at 169.254.169.254 in
google cloud engine

.. versionadded:: 3005.0

:depends: requests

To enable these grains that pull from the http://169.254.169.254/computeMetadata/v1/
metadata server set `metadata_server_grains: True` in the minion config.

.. code-block:: yaml

    metadata_server_grains: True

"""

import logging
import os

import salt.utils.data
import salt.utils.http as http
import salt.utils.json
import salt.utils.stringutils

# metadata server information
IP = "169.254.169.254"
HOST = f"http://{IP}/"

log = logging.getLogger(__name__)


def __virtual__():
    if __opts__.get("metadata_server_grains", False) is False:
        return False
    googletest = http.query(HOST, status=True, headers=True)
    if (
        googletest.get("status") != 200
        and googletest["headers"].get("Metadata-Flavor", False) != "Google"
    ):
        return False
    return True


def _search(prefix="computeMetadata/v1/"):
    """
    Recursively look up all grains in the metadata server
    """
    ret = {}
    heads = ["Metadata-Flavor: Google"]
    linedata = http.query(os.path.join(HOST, prefix), headers=True, header_list=heads)
    if "body" not in linedata:
        return ret
    body = salt.utils.stringutils.to_unicode(linedata["body"])
    if (
        linedata["headers"].get("Content-Type", "text/plain")
        == "application/octet-stream"
    ):
        return body
    for line in body.split("\n"):
        # Block list, null bytes are causing oddities. and project contains ssh keys used to login to the system.
        # so keeping both from showing up in the grains.
        if line in ["", "project/"]:
            continue
        if line.endswith("/"):
            ret[line[:-1]] = _search(prefix=os.path.join(prefix, line))
        else:
            retdata = http.query(
                os.path.join(HOST, prefix, line), header_list=heads
            ).get("body", None)
            if isinstance(retdata, bytes):
                try:
                    ret[line] = salt.utils.json.loads(
                        salt.utils.stringutils.to_unicode(retdata)
                    )
                except ValueError:
                    ret[line] = salt.utils.stringutils.to_unicode(retdata)
            else:
                ret[line] = retdata
    return salt.utils.data.decode(ret)


def metadata():
    """
    main function to output grains into loader
    """
    return _search()
