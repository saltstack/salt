# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2018 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r'''
:codeauthor: :email:`Bo Maryniuk <bo@suse.de>`

Execution of Salt Support from within states
============================================

State to collect support data from the systems:

.. code-block:: yaml

    examine_my_systems:
      support.taken:
        - profile: default

      support.collected:
        - group: somewhere
        - move: true

'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import sys

# Import salt modules
import salt.fileclient
import salt.ext.six as six
from salt.utils.decorators import depends
import salt.utils.decorators.path

log = logging.getLogger(__name__)
__virtualname__ = 'support'


def taken(name, profile='default', pillar=None, archive=None, output='nested'):
    '''
    Takes minion support config data.

    :param profile:
    :param pillar:
    :param archive:
    :param output:
    :return:
    '''
    ret = {
        'name': 'support.taken',
        'changes': {},
        'result': True,
    }

    result = __salt__['support.run'](profile=profile, pillar=pillar, archive=archive, output=output)
    if result.get('archive'):
        ret['comment'] = 'Information about this system has been saved to {} file.'.format(result['archive'])
        ret['changes']['archive'] = result['archive']
        ret['changes']['messages'] = {}
        for key in ['info', 'error', 'warning']:
            if result.get('messages', {}).get(key):
                ret['changes']['messages'][key] = result['messages'][key]
    else:
        ret['comment'] = ''

    return ret


def __virtual__():
    '''
    Salt Support state
    '''
    return __virtualname__
