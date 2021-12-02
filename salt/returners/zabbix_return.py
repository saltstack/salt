"""
Return salt data to Zabbix

The following Type: "Zabbix trapper" with "Type of information" Text items are required:

.. code-block:: cfg

    Key: salt.trap.info
    Key: salt.trap.warning
    Key: salt.trap.high

To use the Zabbix returner, append '--return zabbix' to the salt command. ex:

.. code-block:: bash

    salt '*' test.ping --return zabbix
"""


import os

# Define the module's virtual name
__virtualname__ = "zabbix"


ZABBIX_SENDER_CANDIDATES = [
    "/usr/local/zabbix/bin/zabbix_sender",
    "/usr/bin/zabbix_sender",
]

ZABBIX_CONFIG_CANDIDATES = [
    "/usr/local/zabbix/etc/zabbix_agentd.conf",
    "/usr/local/zabbix/etc/zabbix_agent2.conf",
    "/etc/zabbix/zabbix_agentd.conf",
    "/etc/zabbix/zabbix_agent2.conf",
]

ZABBIX_SENDER = next((p for p in ZABBIX_SENDER_CANDIDATES if os.path.exists(p)), None)
ZABBIX_CONFIG = next((p for p in ZABBIX_CONFIG_CANDIDATES if os.path.exists(p)), None)


def __virtual__():
    if ZABBIX_SENDER is None or ZABBIX_CONFIG is None:
        message = "No zabbix_sender and no zabbix_agent(d|2).conf found."
        if ZABBIX_SENDER:
            message = "No zabbix_agent(d|2).conf found"
        elif ZABBIX_CONFIG:
            message = "No zabbix_sender found"
        return False, f"Zabbix returner: {message}"
    return True


def zabbix_send(key, output):
    assert ZABBIX_SENDER and ZABBIX_CONFIG
    cmd = (
        ZABBIX_SENDER
        + " -c "
        + ZABBIX_CONFIG
        + " -k "
        + key
        + ' -o "'
        + output
        + '"'
    )
    __salt__["cmd.shell"](cmd)


def save_load(jid, load, minions=None):
    """
    Included for API consistency
    """


def returner(ret):
    changes = False
    errors = False
    job_minion_id = ret["id"]

    if type(ret["return"]) is dict:
        for state, item in ret["return"].items():
            if "comment" in item and "name" in item and item["result"] is False:
                errors = True
                zabbix_send(
                    "salt.trap.high",
                    "SALT:\nname: {}\ncomment: {}".format(
                        item["name"], item["comment"]
                    ),
                )
            elif "comment" in item and "name" in item and item["changes"]:
                changes = True
                zabbix_send(
                    "salt.trap.warning",
                    "SALT:\nname: {}\ncomment: {}".format(
                        item["name"], item["comment"]
                    ),
                )

    if not changes and not errors:
        zabbix_send("salt.trap.info", "SALT {} OK".format(job_minion_id))
