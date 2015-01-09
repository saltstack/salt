# -*- coding: utf-8 -*-
'''
Control a salt cloud system
'''
from __future__ import absolute_import

# Import python libs
import json

# Import salt libs
import salt.utils
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
    return False


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
        ret = json.loads(out, object_hook=salt.utils.decode_dict)
    except ValueError:
        ret = {}
    return ret
