"""
Return salt data to Zabbix.

Zabbix items should be configured with the type "Zabbix trapper".
By default, the key will be `salt.return.{fun}`, and the data will
be formatted with the `nested` outputter.
State output will instead use the `highstate` outputter by default.

Requires the `zabbix_sender` executable to be available on the minion.

Configuration will be taken from the Zabbix agent config by default,
but can be overridden via pillars, grains, minion or master config, with
the `zabbix.` prefix.

+----------------------+-------------------------+--------------------------------+
| Config key           | return_kwargs           | Default value                  |
+======================+=========================+================================+
| output               | output                  | nested                         |
+----------------------+-------------------------+--------------------------------+
| sender_bin           | sender_bin              | /usr/bin/zabbix_sender         |
+----------------------+-------------------------+--------------------------------+
| config_file          | config                  | /etc/zabbix/zabbix_agentd.conf |
+----------------------+-------------------------+--------------------------------+
| serveractive         | zabbix_server           |                                |
+----------------------+-------------------------+--------------------------------+
| port                 | port                    | 10051                          |
+----------------------+-------------------------+--------------------------------+
| sourceip             | source_address          |                                |
+----------------------+-------------------------+--------------------------------+
| timeout              | timeout                 | 60                             |
+----------------------+-------------------------+--------------------------------+
| hostname             | host                    |                                |
+----------------------+-------------------------+--------------------------------+
| return_key           | key                     | salt.return.{fun}              |
+----------------------+-------------------------+--------------------------------+
| tlsconnect           | tls_connect             | unencrypted                    |
+----------------------+-------------------------+--------------------------------+
| tlscafile            | tls_ca_file             |                                |
+----------------------+-------------------------+--------------------------------+
| tlscrlfile           | tls_crl_file            |                                |
+----------------------+-------------------------+--------------------------------+
| tlsservercertissuer  | tls_server_cert_issuer  |                                |
+----------------------+-------------------------+--------------------------------+
| tlsservercertsubject | tls_server_cert_subject |                                |
+----------------------+-------------------------+--------------------------------+
| tlscertfile          | tls_cert_file           |                                |
+----------------------+-------------------------+--------------------------------+
| tlskeyfile           | tls_key_file            |                                |
+----------------------+-------------------------+--------------------------------+
| tlspskidentity       | tls_psk_identity        |                                |
+----------------------+-------------------------+--------------------------------+
| tlspskfile           | tls_psk_file            |                                |
+----------------------+-------------------------+--------------------------------+
| tlscipher13          | tls_cipher13            |                                |
+----------------------+-------------------------+--------------------------------+
| tlscipher            | tls_cipher              |                                |
+----------------------+-------------------------+--------------------------------+

For example, this will send the value "True" to Zabbix with the key "salt.return.test.ping",
 assuming every minion has a standard Zabbix agent installation.

.. code-block:: bash

    salt '*' test.ping --return zabbix

"""

import logging
import os
import shlex

from salt.exceptions import CommandExecutionError
from salt.output import try_printout
from salt.returners import get_returner_options
from salt.utils.path import which_bin

__virtualname__ = "zabbix"
log = logging.getLogger(__name__)


def __virtual__():
    cfg_key = "{}.sender_bin".format(__virtualname__)
    sender_bin = __pillar__.get(
        cfg_key,
        __grains__.get(cfg_key, __opts__.get(cfg_key, which_bin(["zabbix_sender"]))),
    )
    if sender_bin and os.path.exists(sender_bin):
        return __virtualname__
    else:
        return False, "Zabbix returner: No zabbix_sender executable found."


def _get_config(ret):
    defaults = {
        "key": "salt.return.{}".format(ret["fun"]),
        "output": "highstate" if ret["fun"].startswith("state.") else "nested",
        "sender_bin": which_bin(["zabbix_sender"]),
    }
    if os.path.exists("/etc/zabbix/zabbix_agentd.conf"):
        defaults["config"] = "/etc/zabbix/zabbix_agentd.conf"

    return get_returner_options(
        virtualname=__virtualname__,
        ret=ret,
        attrs={
            "output": "output",
            "sender_bin": "sender_bin",
            # The rest are all zabbix_sender CLI options
            #  https://www.zabbix.com/documentation/current/en/manpages/zabbix_sender
            # Config keys match those used by the zabbix_agentd.conf and zabbix formula
            #  https://github.com/saltstack-formulas/zabbix-formula
            "config": "config_file",
            "zabbix_server": "serveractive",
            "port": "port",
            "source_address": "sourceip",
            "timeout": "timeout",
            "host": "hostname",
            "key": "return_key",
            "tls_connect": "tlsconnect",
            "tls_ca_file": "tlscafile",
            "tls_crl_file": "tlscrlfile",
            "tls_server_cert_issuer": "tlsservercertissuer",
            "tls_server_cert_subject": "tlsservercertsubject",
            "tls_cert_file": "tlscertfile",
            "tls_key_file": "tlskeyfile",
            "tls_psk_identity": "tlspskidentity",
            "tls_psk_file": "tlspskfile",
            "tls_cipher13": "tlscipher13",
            "tls_cipher": "tlscipher",
        },
        defaults=defaults,
        __salt__=__salt__,
        __opts__=__opts__,
    )


def _zabbix_send(exe, options):
    cmd = shlex.quote(exe)
    for option, value in options.items():
        option = option.replace("_", "-")
        cmd += " --{} {}".format(shlex.quote(option), shlex.quote(value))

    log.debug("%s", cmd)
    result = __salt__["cmd.run_all"](cmd, ignore_retcode=True, output_loglevel="quiet")
    if result["retcode"] == 0:
        log.debug("zabbix_sender: %s", result["stdout"])
    elif result["retcode"] == 2:
        log.warning("zabbix_sender: %s", result["stdout"])
    else:
        log.error("zabbix_sender: %s", result["stdout"])
        msg = "zabbix_sender failed with retcode {}".format(result["retcode"])
        raise CommandExecutionError(msg)


def save_load(jid, load, minions=None):
    """
    Included for API consistency
    """


def returner(ret):
    config = _get_config(ret)
    log.debug("Config: %s", config)

    if config["output"] == "highstate":
        data = {ret["id"]: ret["return"]}
    else:
        data = ret["return"]

    opts = __opts__.copy()
    opts["color"] = False

    exe = config.pop("sender_bin")
    out = ret.get("out", config.pop("output"))
    config["value"] = try_printout(data, out, opts)
    _zabbix_send(exe, config)
