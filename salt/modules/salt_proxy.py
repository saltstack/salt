"""
    Salt proxy module

    .. versionadded:: 2015.8.3

    Module to deploy and manage salt-proxy processes
    on a minion.
"""

import logging
import os
import shlex

import salt.syspaths
import salt.utils.files

log = logging.getLogger(__name__)


def _write_proxy_conf(proxyfile):
    """
    write to file
    """
    msg = "Invalid value for proxy file provided!, Supplied value = {}".format(
        proxyfile
    )

    log.trace("Salt Proxy Module: write proxy conf")

    if proxyfile:
        log.debug("Writing proxy conf file")
        with salt.utils.files.fopen(proxyfile, "w") as proxy_conf:
            proxy_conf.write(
                salt.utils.stringutils.to_str("master: {}".format(__grains__["master"]))
            )
        msg = f"Wrote proxy file {proxyfile}"
        log.debug(msg)

    return msg


def _proxy_conf_file(proxyfile, test):
    """
    Check if proxy conf exists and update
    """
    changes_old = []
    changes_new = []
    success = True
    if not os.path.exists(proxyfile):
        try:
            if not test:
                changes_new.append(_write_proxy_conf(proxyfile))
                msg = f"Salt Proxy: Wrote proxy conf {proxyfile}"
            else:
                msg = f"Salt Proxy: Update required to proxy conf {proxyfile}"
        except OSError as err:
            success = False
            msg = f"Salt Proxy: Error writing proxy file {err}"
            log.error(msg)
            changes_new.append(msg)
        changes_new.append(msg)
        log.debug(msg)
    else:
        msg = f"Salt Proxy: {proxyfile} already exists, skipping"
        changes_old.append(msg)
        log.debug(msg)
    return success, changes_new, changes_old


def _is_proxy_running(proxyname):
    """
    Check if proxy for this name is running
    """
    cmd = 'ps ax | grep "salt-proxy --proxyid={}" | grep -v grep'.format(
        shlex.quote(proxyname)
    )
    cmdout = __salt__["cmd.run_all"](cmd, timeout=5, python_shell=True)
    if not cmdout["stdout"]:
        return False
    else:
        return True


def _proxy_process(proxyname, test):
    """
    Check and execute proxy process
    """
    changes_old = []
    changes_new = []
    if not _is_proxy_running(proxyname):
        if not test:
            __salt__["cmd.run_all"](
                f"salt-proxy --proxyid={shlex.quote(proxyname)} -l info -d",
                timeout=5,
            )
            changes_new.append(f"Salt Proxy: Started proxy process for {proxyname}")
        else:
            changes_new.append(f"Salt Proxy: process {proxyname} will be started")
    else:
        changes_old.append(f"Salt Proxy: already running for {proxyname}")
    return True, changes_new, changes_old


def configure_proxy(proxyname, start=True):
    """
    Create the salt proxy file and start the proxy process
    if required

    Parameters:
        proxyname:
            Name to be used for this proxy (should match entries in pillar)
        start:
            Boolean indicating if the process should be started
            default = True

    CLI Example:

    .. code-block:: bash

        salt deviceminion salt_proxy.configure_proxy p8000
    """
    changes_new = []
    changes_old = []
    status_file = True
    test = __opts__["test"]

    # write the proxy file if necessary
    proxyfile = os.path.join(salt.syspaths.CONFIG_DIR, "proxy")
    status_file, msg_new, msg_old = _proxy_conf_file(proxyfile, test)
    changes_new.extend(msg_new)
    changes_old.extend(msg_old)
    status_proc = False

    # start the proxy process
    if start:
        status_proc, msg_new, msg_old = _proxy_process(proxyname, test)
        changes_old.extend(msg_old)
        changes_new.extend(msg_new)
    else:
        changes_old.append("Start is False, not starting salt-proxy process")
        log.debug("Process not started")

    return {
        "result": status_file and status_proc,
        "changes": {"old": "\n".join(changes_old), "new": "\n".join(changes_new)},
    }


def is_running(proxyname):
    """
    Check if the salt-proxy process associated
    with this proxy (name) is running.

    Returns True if the process is running
    False otherwise

    Parameters:
        proxyname:
            String name of the proxy (p8000 for example)

    CLI Example:

    .. code-block:: bash

        salt deviceminion salt_proxy.is_running p8000
    """
    return {"result": _is_proxy_running(proxyname)}
