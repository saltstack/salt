# -*- coding: utf-8 -*-
"""
Run munin plugins/checks from salt and format the output as data.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import stat

import salt.utils.files
import salt.utils.stringutils

# Import salt libs
from salt.ext import six

PLUGINDIR = "/etc/munin/plugins/"


def __virtual__():
    """
    Only load the module if munin-node is installed
    """
    if os.path.exists("/etc/munin/munin-node.conf"):
        return "munin"
    return (
        False,
        "The munin execution module cannot be loaded: munin-node is not installed.",
    )


def _get_conf(fname="/etc/munin/munin-node.cfg"):
    with salt.utils.files.fopen(fname, "r") as fp_:
        return salt.utils.stringutils.to_unicode(fp_.read())


def run(plugins):
    """
    Run one or more named munin plugins

    CLI Example:

    .. code-block:: bash

        salt '*' munin.run uptime
        salt '*' munin.run uptime,cpu,load,memory
    """
    all_plugins = list_plugins()

    if isinstance(plugins, six.string_types):
        plugins = plugins.split(",")

    data = {}
    for plugin in plugins:
        if plugin not in all_plugins:
            continue
        data[plugin] = {}
        muninout = __salt__["cmd.run"](
            "munin-run {0}".format(plugin), python_shell=False
        )
        for line in muninout.split("\n"):
            if "value" in line:  # This skips multigraph lines, etc
                key, val = line.split(" ")
                key = key.split(".")[0]
                try:
                    # We only want numbers
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                    data[plugin][key] = val
                except ValueError:
                    pass
    return data


def run_all():
    """
    Run all the munin plugins

    CLI Example:

    .. code-block:: bash

        salt '*' munin.run_all
    """
    plugins = list_plugins()
    ret = {}
    for plugin in plugins:
        ret.update(run(plugin))
    return ret


def list_plugins():
    """
    List all the munin plugins

    CLI Example:

    .. code-block:: bash

        salt '*' munin.list_plugins
    """
    pluginlist = os.listdir(PLUGINDIR)
    ret = []
    for plugin in pluginlist:
        # Check if execute bit
        statf = os.path.join(PLUGINDIR, plugin)
        try:
            executebit = stat.S_IXUSR & os.stat(statf)[stat.ST_MODE]
        except OSError:
            pass
        if executebit:
            ret.append(plugin)
    return ret
