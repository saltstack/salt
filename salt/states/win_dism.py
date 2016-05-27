# -*- coding: utf-8 -*-
'''
Installing of Windows features using DISM
=======================

Install windows features/capabilties with DISM

.. code-block:: yaml

    Language.Basic~~~en-US~0.0.1.0:
      dism.capability_installed

    NetFx3:
      dism.feature_installed
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = "dism"


def __virtual__():
    '''
    Only work on Windows
    '''
    if salt.utils.is_windows() and 'dism.install_capability' in __salt__:
        return __virtualname__
    return False


def capability_installed(name, source=None, limit_access=False):
    '''
    Install a DISM capability

    name
        The capability in which to install

    source
        The optional source of the capability

    limit_access
        Prevent DISM from contacting Windows Update for online images

    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    comment = []

    installed_capabilities = __salt__['dism.installed_capabilities']()

    if name in installed_capabilities:
        comment.append("{0} was already installed.\n".format(name))
    else:
        out = __salt__['dism.install_capability'](name, source, limit_access)
        if out['retcode'] == 0:
            comment.append("{0} was installed.\n".format(name))
            ret['changes']['installed'] = name
        else:
            comment.append("{0} was unable to be installed. {1}\n".format(name, out['stdout']))
            ret['result'] = False

    ret['comment'] = ' '.join(comment)
    return ret


def feature_installed(name, source=None, limit_access=False):
    '''
    Install a DISM feature

    name
        The feature in which to install

    source
        The optional source of the feature

    limit_access
        Prevent DISM from contacting Windows Update for online images

    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    comment = []

    installed_features = __salt__['dism.installed_features']()

    if name in installed_features:
        comment.append("{0} was already installed.\n".format(name))
    else:
        out = __salt__['dism.install_feature'](name, source, limit_access)
        if out['retcode'] == 0:
            comment.append("{0} was installed.\n".format(name))
            ret['changes']['installed'] = name
        else:
            comment.append("{0} was unable to be installed. {1}\n".format(name, out['stdout']))
            ret['result'] = False

    ret['comment'] = ' '.join(comment)
    return ret
