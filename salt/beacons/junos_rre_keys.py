"""
Junos redundant routing engine beacon.

.. note::

   This beacon only works on the Juniper native minion.

Copies salt-minion keys to the backup RE when present

Configure with

.. code-block:: yaml

    beacon:
      beacons:
        junos_rre_keys:
          - interval: 43200

`interval` above is in seconds, 43200 is recommended (every 12 hours)
"""

__virtualname__ = "junos_rre_keys"


def beacon(config):
    ret = []

    engine_status = __salt__["junos.routing_engine"]()

    if not engine_status["success"]:
        return []

    for e in engine_status["backup"]:
        result = __salt__["junos.dir_copy"]("/var/local/salt/etc", e)
        ret.append({"result": result, "success": True})

    return ret
