# -*- coding: utf-8 -*-
'''
Installation and activation of windows licenses
=======================

Install and activate windows licenses

.. code-block:: yaml

    XXXXX-XXXXX-XXXXX-XXXXX-XXXXX:
      license.activate
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils

log = logging.getLogger(__name__)
__virtualname__ = 'license'


def __virtual__():
    '''
    Only work on Windows
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def activate(name):
    '''
    Install and activate the given product key

    name
        The 5x5 product key given to you by Microsoft

    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    product_key = name

    license_info = __salt__['license.info']()
    licensed = False
    key_match = False
    if license_info is not None:
        licensed = license_info['licensed']
        key_match = license_info['partial_key'] in product_key

    if not key_match:
        out = __salt__['license.install'](product_key)
        licensed = False
        if 'successfully' not in out:
            ret['result'] = False
            ret['comment'] += 'Unable to install the given product key is it valid?'
            return ret
    if not licensed:
        out = __salt__['license.activate']()
        if 'successfully' not in out:
            ret['result'] = False
            ret['comment'] += 'Unable to activate the given product key.'
            return ret
        ret['comment'] += 'Windows is now activated.'
    else:
        ret['comment'] += 'Windows is already activated.'
    return ret
