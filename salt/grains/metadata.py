"""
Grains from cloud metadata servers at 169.254.169.254

.. versionadded:: 2017.7.0

:depends: requests

To enable these grains that pull from the http://169.254.169.254/latest
metadata server set `metadata_server_grains: True` in the minion config.

.. code-block:: yaml

    metadata_server_grains: True

"""

import os

import salt.utils.aws as metadata
import salt.utils.data
import salt.utils.json
import salt.utils.stringutils

def _search(prefix="latest/"):
    """
    Recursively look up all grains in the metadata server
    """
    ret = {}
    result = metadata.get_metadata(prefix)
    body = result.text
    for line in body.split("\n"):
        if line.endswith("/"):
            ret[line[:-1]] = _search(prefix=os.path.join(prefix, line))
        elif prefix == "latest/":
            # (gtmanfred) The first level should have a forward slash since
            # they have stuff underneath. This will not be doubled up though,
            # because lines ending with a slash are checked first.
            ret[line] = _search(prefix=os.path.join(prefix, line + "/"))
        elif line.endswith(("dynamic", "meta-data")):
            ret[line] = _search(prefix=os.path.join(prefix, line))
        elif "=" in line:
            key, value = line.split("=")
            ret[value] = _search(prefix=os.path.join(prefix, key))
        else:
            retdata = metadata.get_metadata(os.path.join(prefix, line)).text
            # (gtmanfred) This try except block is slightly faster than
            # checking if the string starts with a curly brace
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

def main():
    ret = {}
    ret['dynamic'] = _search('dynamic')
    ret['meta-data'] = _search('meta-data')
    return ret
