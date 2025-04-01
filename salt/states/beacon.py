"""
Management of the Salt beacons
==============================

.. versionadded:: 2015.8.0

.. code-block:: yaml

    ps:
      beacon.present:
        - save: True
        - enable: False
        - services:
            salt-master: running
            apache2: stopped

    sh:
      beacon.present: []

    load:
      beacon.present:
        - averages:
            1m:
              - 0.0
              - 2.0
            5m:
              - 0.0
              - 1.5
            15m:
              - 0.1
              - 1.0

    .. versionadded:: 3000

    Beginning in the 3000 release, multiple copies of a beacon can be configured
    using the ``beacon_module`` parameter.

    inotify_infs:
      beacon.present:
        - save: True
        - enable: True
        - files:
           /etc/infs.conf:
             mask:
               - create
               - delete
               - modify
             recurse: True
             auto_add: True
        - interval: 10
        - beacon_module: inotify
        - disable_during_state_run: True

    inotify_ntp:
      beacon.present:
        - save: True
        - enable: True
        - files:
           /etc/ntp.conf:
             mask:
               - create
               - delete
               - modify
             recurse: True
             auto_add: True
        - interval: 10
        - beacon_module: inotify
        - disable_during_state_run: True
"""

import logging

log = logging.getLogger(__name__)


def present(name, save=False, **kwargs):
    """
    Ensure beacon is configured with the included beacon data.

    name
        The name of the beacon to ensure is configured.
    save
        True/False, if True the beacons.conf file be updated too. Default is False.

    Example:

    .. code-block:: yaml

        ps_beacon:
          beacon.present:
            - name: ps
            - save: True
            - enable: False
            - services:
                salt-master: running
                apache2: stopped
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    current_beacons = __salt__["beacons.list"](return_yaml=False, **kwargs)
    beacon_data = [{k: v} for k, v in kwargs.items()]

    if name in current_beacons:

        if beacon_data == current_beacons[name]:
            ret["comment"].append(f"Job {name} in correct state")
        else:
            if __opts__.get("test"):
                kwargs["test"] = True
                result = __salt__["beacons.modify"](name, beacon_data, **kwargs)
                ret["comment"].append(result["comment"])
                ret["changes"] = result["changes"]
            else:
                result = __salt__["beacons.modify"](name, beacon_data, **kwargs)
                if not result["result"]:
                    ret["result"] = result["result"]
                    ret["comment"] = result["comment"]
                    return ret
                else:
                    if "changes" in result:
                        ret["comment"].append(f"Modifying {name} in beacons")
                        ret["changes"] = result["changes"]
                    else:
                        ret["comment"].append(result["comment"])

    else:
        if __opts__.get("test"):
            kwargs["test"] = True
            result = __salt__["beacons.add"](name, beacon_data, **kwargs)
            ret["comment"].append(result["comment"])
        else:
            result = __salt__["beacons.add"](name, beacon_data, **kwargs)
            if not result["result"]:
                ret["result"] = result["result"]
                ret["comment"] = result["comment"]
                return ret
            else:
                ret["comment"].append(f"Adding {name} to beacons")

    if save:
        if __opts__.get("test"):
            ret["comment"].append(f"Beacon {name} would be saved")
        else:
            __salt__["beacons.save"]()
            ret["comment"].append(f"Beacon {name} saved")

    ret["comment"] = "\n".join(ret["comment"])
    return ret


def absent(name, save=False, **kwargs):
    """
    Ensure beacon is absent.

    name
        The name of the beacon that is ensured absent.
    save
        True/False, if True the beacons.conf file be updated too. Default is False.

    Example:

    .. code-block:: yaml

        remove_beacon:
          beacon.absent:
            - name: ps
            - save: True

    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    current_beacons = __salt__["beacons.list"](return_yaml=False, **kwargs)
    if name in current_beacons:
        if __opts__.get("test"):
            kwargs["test"] = True
            result = __salt__["beacons.delete"](name, **kwargs)
            ret["comment"].append(result["comment"])
        else:
            result = __salt__["beacons.delete"](name, **kwargs)
            if not result["result"]:
                ret["result"] = result["result"]
                ret["comment"] = result["comment"]
                return ret
            else:
                ret["comment"].append(f"Removed {name} from beacons")
    else:
        ret["comment"].append(f"{name} not configured in beacons")

    if save:
        if __opts__.get("test"):
            ret["comment"].append(f"Beacon {name} would be saved")
        else:
            __salt__["beacons.save"]()
            ret["comment"].append(f"Beacon {name} saved")

    ret["comment"] = "\n".join(ret["comment"])
    return ret


def enabled(name, **kwargs):
    """
    Enable a beacon.

    name
        The name of the beacon to enable.

    Example:

    .. code-block:: yaml

        enable_beacon:
          beacon.enabled:
            - name: ps

    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    current_beacons = __salt__["beacons.list"](return_yaml=False, **kwargs)
    if name in current_beacons:
        if __opts__.get("test"):
            kwargs["test"] = True
            result = __salt__["beacons.enable_beacon"](name, **kwargs)
            ret["comment"].append(result["comment"])
        else:
            result = __salt__["beacons.enable_beacon"](name, **kwargs)
            if not result["result"]:
                ret["result"] = result["result"]
                ret["comment"] = result["comment"]
                return ret
            else:
                ret["comment"].append(f"Enabled {name} from beacons")
    else:
        ret["comment"].append(f"{name} not a configured beacon")

    ret["comment"] = "\n".join(ret["comment"])
    return ret


def disabled(name, **kwargs):
    """
    Disable a beacon.

    name
        The name of the beacon to disable.

    Example:

    .. code-block:: yaml

        disable_beacon:
          beacon.disabled:
            - name: psp

    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    current_beacons = __salt__["beacons.list"](return_yaml=False, **kwargs)
    if name in current_beacons:
        if __opts__.get("test"):
            kwargs["test"] = True
            result = __salt__["beacons.disable_beacon"](name, **kwargs)
            ret["comment"].append(result["comment"])
        else:
            result = __salt__["beacons.disable_beacon"](name, **kwargs)
            if not result["result"]:
                ret["result"] = result["result"]
                ret["comment"] = result["comment"]
                return ret
            else:
                ret["comment"].append(f"Disabled beacon {name}.")
    else:
        ret["comment"].append(f"Job {name} is not configured.")

    ret["comment"] = "\n".join(ret["comment"])
    return ret
