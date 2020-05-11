# -*- coding: utf-8 -*-
'''
Control a salt cloud system
'''
# Import python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import salt libs
import salt.utils.data
import salt.utils.json

HAS_CLOUD = False
try:
    import saltcloud  # pylint: disable=W0611
    HAS_CLOUD = True
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'saltcloud'


def __virtual__():
    '''
    Only load if salt cloud is installed
    '''
    if HAS_CLOUD:
        return __virtualname__
    return (False, 'The saltcloudmod execution module failed to load: requires the saltcloud library.')


def create(name, profile):
    '''
    Create the named vm

    CLI Example:

    .. code-block:: bash

        salt <minion-id> saltcloud.create webserver rackspace_centos_512
    '''
    cmd = 'salt-cloud --out json -p {0} {1}'.format(profile, name)
    out = __salt__['cmd.run_stdout'](cmd, python_shell=False)
    try:
        ret = salt.utils.json.loads(out)
    except ValueError:
        ret = {}
    return ret
