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
:codeauthor: `Bo Maryniuk <bo@suse.de>`

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
import tempfile

# Import salt modules
import salt.fileclient
import salt.utils.decorators.path
import salt.exceptions
import salt.utils.odict

log = logging.getLogger(__name__)
__virtualname__ = 'support'


class SaltSupportState(object):
    '''
    Salt-support.
    '''
    EXPORTED = ['collected', 'taken']

    def get_kwargs(self, data):
        kwargs = {}
        for keyset in data:
            kwargs.update(keyset)

        return kwargs

    def __call__(self, state):
        '''
        Call support.

        :param args:
        :param kwargs:
        :return:
        '''
        ret = {
            'name': state.pop('name'),
            'changes': {},
            'result': True,
            'comment': '',
        }

        out = {}
        functions = ['Functions:']
        try:
            for ref_func, ref_kwargs in state.items():
                if ref_func not in self.EXPORTED:
                    raise salt.exceptions.SaltInvocationError('Function {} is not found'.format(ref_func))
                out[ref_func] = getattr(self, ref_func)(**self.get_kwargs(ref_kwargs))
                functions.append('  - {}'.format(ref_func))
            ret['comment'] = '\n'.join(functions)
        except Exception as ex:
            ret['comment'] = str(ex)
            ret['result'] = False
        ret['changes'] = out

        return ret

    def check_destination(self, location, group):
        '''
        Check destination for the archives.
        :return:
        '''
        # Pre-create destination, since rsync will
        # put one file named as group
        try:
            destination = os.path.join(location, group)
            if os.path.exists(destination) and not os.path.isdir(destination):
                raise salt.exceptions.SaltException('Destination "{}" should be directory!'.format(destination))
            if not os.path.exists(destination):
                os.makedirs(destination)
                log.debug('Created destination directory for archives: %s', destination)
            else:
                log.debug('Archives destination directory %s already exists', destination)
        except OSError as err:
            log.error(err)

    def collected(self, group, filename=None, host=None, location=None, move=True, all=True):
        '''
        Sync archives to a central place.

        :param name:
        :param group:
        :param filename:
        :param host:
        :param location:
        :param move:
        :param all:
        :return:
        '''
        ret = {
            'name': 'support.collected',
            'changes': {},
            'result': True,
            'comment': '',
        }
        location = location or tempfile.gettempdir()
        self.check_destination(location, group)
        ret['changes'] = __salt__['support.sync'](group, name=filename, host=host,
                                                  location=location, move=move, all=all)

        return ret

    def taken(self, profile='default', pillar=None, archive=None, output='nested'):
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


_support_state = SaltSupportState()


def __call__(*args, **kwargs):
    '''
    SLS single-ID syntax processing.

    module:
        This module reference, equals to sys.modules[__name__]

    state:
        Compiled state in preserved order. The function supposed to look
        at first level array of functions.

    :param cdata:
    :param kwargs:
    :return:
    '''
    return _support_state(kwargs.get('state', {}))


def taken(name, profile='default', pillar=None, archive=None, output='nested'):
    return _support_state.taken(profile=profile, pillar=pillar,
                                archive=archive, output=output)


def collected(name, group, filename=None, host=None, location=None, move=True, all=True):
    return _support_state.collected(group=group, filename=filename,
                                    host=host, location=location, move=move, all=all)


def __virtual__():
    '''
    Salt Support state
    '''
    return __virtualname__
