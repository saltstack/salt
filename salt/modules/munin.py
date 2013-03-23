#!/usr/bin/env python
'''
Run munin plugins/checks from salt and format the output as data.
'''

# Import python libs
import os
import stat

# Import salt libs
import salt.utils
from salt.exceptions import SaltException

PLUGINDIR = '/etc/munin/plugins/'

def __virtual__():
    '''
    Only load the module if munin-node is installed
    '''
    if os.path.exists('/etc/munin/munin-node.conf'):
        return 'munin'
    return False

def _get_conf(fname='/etc/munin/munin-node.cfg'):
    fp = salt.utils.fopen(fname, 'r')
    return fp.read()

def run(plugin):
    '''
    Run a named munin plugin

    CLI Example::

        salt '*' munin.run uptime
    '''
    plugins = list_plugins()
    if plugin in plugins:
        muninout =  __salt__['cmd.run']('munin-run ' + plugin)
        data = {
            plugin: {}
        }
        for line in muninout.split('\n'):
            if 'value' in line: # This skips multigraph lines, etc
                key, val = line.split(' ')
                key = key.split('.')[0]
                try:
                    # We only want numbers
                    val = float(val)
                    data[plugin][key] = val
                except ValueError:
                    pass
        return data
    else:
        return 'Munin plugin with name "%s" not found' %plugin

def run_all():
    '''
    Run all the munin plugins

    CLI Example::

        salt '*' munin.run_all
    '''
    plugins = list_plugins()
    ret = {}
    for plugin in plugins:
        ret[plugin] = run(plugin)
    return ret

def list_plugins():
    '''
    List all the munin plugins

    CLI Example::

        salt '*' munin.list_plugins
    '''
    pluginlist = os.listdir(PLUGINDIR)
    ret = []
    for plugin in pluginlist:
        # Check if execute bit
        statf = os.path.join(PLUGINDIR, plugin)
        executebit = stat.S_IXUSR & os.stat(statf)[stat.ST_MODE]
        if executebit:
            ret.append(plugin)
    return ret


