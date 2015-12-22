# -*- coding: utf-8 -*-
'''
Management zpool

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       zpool
:platform:      smartos, illumos, solaris, freebsd, linux

.. versionadded:: Boron

.. code-block:: yaml

    oldpool:
      zpool.absent:
        - export: true

    newpool:
      zpool.present:
        - config:
            try_import: false
            force: true
        - properties:
            comment: salty pool
        - layout:
            mirror:
              /dev/disk0
              /dev/disk1
            mirror:
              /dev/disk2
              /dev/disk3

.. note::

    only properties will be updated if possible, the layout is fixed at creation time and will not be updated.

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
#from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zpool'


def __virtual__():
    '''
    Provides zpool state
    '''
    if 'zpool.create' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on illumos, Solaris, SmartOS, FreeBSD, ...'.format(
                __virtualname__
            )
        )


def absent(name, export=False, force=False):
    '''
    Ensure storage pool is not absent on the system

    name : string
        name of storage pool
    export : boolean
        export instread of destroy the zpool if present
    force : boolean
        force destroy or export

    '''
    name = name.lower()
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    if __salt__['zpool.exists'](name):
        ret['result'] = False

        if export:  # try to export the zpool
            if __opts__['test']:
                ret['result'] = True
            else:
                ret['result'] = __salt__['zpool.export'](name, force=force)
                ret['result'] = name in ret['result'] and ret['result'][name] == 'exported'

        else:  # try to destroy the zpool
            if __opts__['test']:
                ret['result'] = True
            else:
                ret['result'] = __salt__['zpool.destroy'](name, force=force)
                ret['result'] = name in ret['result'] and ret['result'][name] == 'destroyed'

        if ret['result']:
            ret['changes'][name] = 'exported' if export else 'destroyed'
            ret['comment'] = 'zpool {0} was {1}'.format(name, ret['changes'][name])
    else:
        ret['result'] = True
        ret['comment'] = 'zpool {0} is absent'.format(name)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
