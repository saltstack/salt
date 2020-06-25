# -*- coding: utf-8 -*-
"""
Apache Traffic Server execution module.

.. versionadded:: 2015.8.0

``traffic_ctl`` is used to execute individual Traffic Server commands and to
script multiple commands in a shell.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import subprocess

# Import salt libs
import salt.utils.path
import salt.utils.stringutils

__virtualname__ = "trafficserver"

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which("traffic_ctl") or salt.utils.path.which("traffic_line"):
        return __virtualname__
    return (
        False,
        "trafficserver execution module not loaded: "
        "neither traffic_ctl nor traffic_line was found.",
    )


_TRAFFICLINE = salt.utils.path.which("traffic_line")
_TRAFFICCTL = salt.utils.path.which("traffic_ctl")


def _traffic_ctl(*args):
    return [_TRAFFICCTL] + list(args)


def _traffic_line(*args):
    return [_TRAFFICLINE] + list(args)


def _statuscmd():
    if _TRAFFICCTL:
        cmd = _traffic_ctl("server", "status")
    else:
        cmd = _traffic_line("--status")

    return _subprocess(cmd)


def _subprocess(cmd):
    """
    Function to standardize the subprocess call
    """

    log.debug('Running: "%s"', " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        ret = salt.utils.stringutils.to_unicode(proc.communicate()[0]).strip()
        retcode = proc.wait()

        if ret:
            return ret
        elif retcode != 1:
            return True
        else:
            return False
    except OSError as err:
        log.error(err)
        return False


def bounce_cluster():
    """
    Bounce all Traffic Server nodes in the cluster. Bouncing Traffic Server
    shuts down and immediately restarts Traffic Server, node-by-node.

    .. code-block:: bash

        salt '*' trafficserver.bounce_cluster
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("cluster", "restart")
    else:
        cmd = _traffic_line("-B")

    return _subprocess(cmd)


def bounce_local(drain=False):
    """
    Bounce Traffic Server on the local node. Bouncing Traffic Server shuts down
    and immediately restarts the Traffic Server node.

    drain
        This option modifies the restart behavior such that traffic_server
        is not shut down until the number of active client connections
        drops to the number given by the
        proxy.config.restart.active_client_threshold configuration
        variable.

    .. code-block:: bash

        salt '*' trafficserver.bounce_local
        salt '*' trafficserver.bounce_local drain=True
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("server", "restart")
    else:
        cmd = _traffic_line("-b")

    if drain:
        cmd = cmd + ["--drain"]

    return _subprocess(cmd)


def clear_cluster():
    """
    Clears accumulated statistics on all nodes in the cluster.

    .. code-block:: bash

        salt '*' trafficserver.clear_cluster
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "clear", "--cluster")
    else:
        cmd = _traffic_line("-C")

    return _subprocess(cmd)


def clear_node():
    """
    Clears accumulated statistics on the local node.

    .. code-block:: bash

        salt '*' trafficserver.clear_node
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "clear")
    else:
        cmd = _traffic_line("-c")

    return _subprocess(cmd)


def restart_cluster():
    """
    Restart the traffic_manager process and the traffic_server process on all
    the nodes in a cluster.

    .. code-block:: bash

        salt '*' trafficserver.restart_cluster
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("cluster", "restart", "--manager")
    else:
        cmd = _traffic_line("-M")

    return _subprocess(cmd)


def restart_local(drain=False):
    """
    Restart the traffic_manager and traffic_server processes on the local node.

    drain
        This option modifies the restart behavior such that
        ``traffic_server`` is not shut down until the number of
        active client connections drops to the number given by the
        ``proxy.config.restart.active_client_threshold`` configuration
        variable.

    .. code-block:: bash

        salt '*' trafficserver.restart_local
        salt '*' trafficserver.restart_local drain=True
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("server", "restart", "--manager")
    else:
        cmd = _traffic_line("-L")

    if drain:
        cmd = cmd + ["--drain"]

    return _subprocess(cmd)


def match_metric(regex):
    """
    Display the current values of all metrics whose names match the
    given regular expression.

    .. versionadded:: 2016.11.0

    .. code-block:: bash

        salt '*' trafficserver.match_metric regex
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "match", regex)
    else:
        cmd = _traffic_ctl("-m", regex)

    return _subprocess(cmd)


def match_config(regex):
    """
    Display the current values of all configuration variables whose
    names match the given regular expression.

    .. versionadded:: 2016.11.0

    .. code-block:: bash

        salt '*' trafficserver.match_config regex
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("config", "match", regex)
    else:
        cmd = _traffic_line("-m", regex)

    return _subprocess(cmd)


def read_config(*args):
    """
    Read Traffic Server configuration variable definitions.

    .. versionadded:: 2016.11.0

    .. code-block:: bash

        salt '*' trafficserver.read_config proxy.config.http.keep_alive_post_out
    """

    ret = {}
    if _TRAFFICCTL:
        cmd = _traffic_ctl("config", "get")
    else:
        cmd = _traffic_line("-r")

    try:
        for arg in args:
            log.debug("Querying: %s", arg)
            ret[arg] = _subprocess(cmd + [arg])
    except KeyError:
        pass

    return ret


def read_metric(*args):
    """
    Read Traffic Server one or more metrics.

    .. versionadded:: 2016.11.0

    .. code-block:: bash

        salt '*' trafficserver.read_metric proxy.process.http.tcp_hit_count_stat
    """

    ret = {}
    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "get")
    else:
        cmd = _traffic_line("-r")

    try:
        for arg in args:
            log.debug("Querying: %s", arg)
            ret[arg] = _subprocess(cmd + [arg])
    except KeyError:
        pass

    return ret


def set_config(variable, value):
    """
    Set the value of a Traffic Server configuration variable.

    variable
        Name of a Traffic Server configuration variable.

    value
        The new value to set.

    .. versionadded:: 2016.11.0

    .. code-block:: bash

        salt '*' trafficserver.set_config proxy.config.http.keep_alive_post_out 0
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("config", "set", variable, value)
    else:
        cmd = _traffic_line("-s", variable, "-v", value)

    log.debug("Setting %s to %s", variable, value)
    return _subprocess(cmd)


def shutdown():
    """
    Shut down Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.shutdown
    """

    # Earlier versions of traffic_ctl do not support
    # "server stop", so we prefer traffic_line here.
    if _TRAFFICLINE:
        cmd = _traffic_line("-S")
    else:
        cmd = _traffic_ctl("server", "stop")

    _subprocess(cmd)
    return _statuscmd()


def startup():
    """
    Start Traffic Server on the local node.

    .. code-block:: bash

        salt '*' trafficserver.start
    """

    # Earlier versions of traffic_ctl do not support
    # "server start", so we prefer traffic_line here.
    if _TRAFFICLINE:
        cmd = _traffic_line("-U")
    else:
        cmd = _traffic_ctl("server", "start")

    _subprocess(cmd)
    return _statuscmd()


def refresh():
    """
    Initiate a Traffic Server configuration file reread. Use this command to
    update the running configuration after any configuration file modification.

    The timestamp of the last reconfiguration event (in seconds since epoch) is
    published in the proxy.node.config.reconfigure_time metric.

    .. code-block:: bash

        salt '*' trafficserver.refresh
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("config", "reload")
    else:
        cmd = _traffic_line("-x")

    return _subprocess(cmd)


def zero_cluster():
    """
    Reset performance statistics to zero across the cluster.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "clear", "--cluster")
    else:
        cmd = _traffic_line("-Z")

    return _subprocess(cmd)


def zero_node():
    """
    Reset performance statistics to zero on the local node.

    .. code-block:: bash

        salt '*' trafficserver.zero_cluster
    """
    if _TRAFFICCTL:
        cmd = _traffic_ctl("metric", "clear")
    else:
        cmd = _traffic_line("-z")

    return _subprocess(cmd)


def offline(path):
    """
    Mark a cache storage device as offline. The storage is identified by a path
    which must match exactly a path specified in storage.config. This removes
    the storage from the cache and redirects requests that would have used this
    storage to other storage. This has exactly the same effect as a disk
    failure for that storage. This does not persist across restarts of the
    traffic_server process.

    .. code-block:: bash

        salt '*' trafficserver.offline /path/to/cache
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("storage", "offline", path)
    else:
        cmd = _traffic_line("--offline", path)

    return _subprocess(cmd)


def alarms():
    """
    List all alarm events that have not been acknowledged (cleared).

    .. code-block:: bash

        salt '*' trafficserver.alarms
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("alarm", "list")
    else:
        cmd = _traffic_line("--alarms")

    return _subprocess(cmd)


def clear_alarms(alarm):
    """
    Clear (acknowledge) an alarm event. The arguments are “all” for all current
    alarms, a specific alarm number (e.g. ‘‘1’‘), or an alarm string identifier
    (e.g. ‘’MGMT_ALARM_PROXY_CONFIG_ERROR’‘).

    .. code-block:: bash

        salt '*' trafficserver.clear_alarms [all | #event | name]
    """

    if _TRAFFICCTL:
        cmd = _traffic_ctl("alarm", "clear", alarm)
    else:
        cmd = _traffic_line("--clear_alarms", alarm)

    return _subprocess(cmd)


def status():
    """
    Show the current proxy server status, indicating if we’re running or not.

    .. code-block:: bash

        salt '*' trafficserver.status
    """

    return _statuscmd()
