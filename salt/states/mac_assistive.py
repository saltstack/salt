# -*- coding: utf-8 -*-
'''
Allows you to manage assistive access on OS X minions with 10.9+
=======================

Install, enable and disable assitive access on OS X minions

.. code-block:: yaml

    /usr/bin/osacript:
      assistive.installed:
        - enabled: True
'''

# Import python libs
from __future__ import absolute_import
from distutils.version import LooseVersion
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = "assistive"


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if salt.utils.is_darwin() and LooseVersion(__grains__['osrelease']) >= LooseVersion('10.9'):
        return True
    return False


def installed(name, enabled=True):
    '''
    Make sure that we have the given bundle ID or path to command
    installed in the assistive access panel.

    name
        The bundle ID or path to command

    enable
        Should assistive access be enabled on this application?

    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    is_installed = __salt__['assistive.installed'](name)

    if is_installed:
        is_enabled = __salt__['assistive.enabled'](name)

        if enabled != is_enabled:
            __salt__['assistive.enable'](name, enabled)
            ret['comment'] = 'Updated enable to {0}'.format(enabled)
        else:
            ret['comment'] = 'Already in the correct state'

    else:
        __salt__['assistive.install'](name, enabled)
        ret['comment'] = 'Installed {0} into the assistive access panel'.format(name)

    return ret
