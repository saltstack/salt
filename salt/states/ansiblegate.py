# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
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

Execution of Ansible modules from within states
===============================================

With `ansible.call` these states allow individual Ansible module calls to be
made via states. To call an Ansible module function use a :mod:`module.run <salt.states.ansible.call>`
state:

.. code-block:: yaml

    some_set_of_tasks:
      ansible:
        - system.ping
        - packaging.os.zypper
          - name: emacs
          - state: installed

'''
from __future__ import absolute_import, print_function, unicode_literals
import sys
try:
    import ansible
except ImportError as err:
    ansible = None


__virtualname__ = 'ansible'


class AnsibleState(object):
    '''
    Ansible state caller.
    '''
    def get_args(self, argset):
        '''
        Get args and kwargs from the argset.

        :param argset:
        :return:
        '''
        args = []
        kwargs = {}
        for element in argset or []:
            if isinstance(element, dict):
                kwargs.update(element)
            else:
                args.append(element)
        return args, kwargs

    def __call__(self, **kwargs):
        '''
        Call Ansible module.

        :return:
        '''

        ret = {
            'name': kwargs.pop('name'),
            'changes': {},
            'comment': '',
            'result': True,
        }

        for mod_name, mod_params in kwargs.items():
            args, kwargs = self.get_args(mod_params)
            try:
                ans_mod_out = __salt__['ansible.{0}'.format(mod_name)](**{'__pub_arg': [args, kwargs]})
            except Exception as err:
                ans_mod_out = 'Module "{0}" failed. Error message: ({1}) {2}'.format(
                    mod_name, err.__class__.__name__, err)
                ret['result'] = False
            ret['changes'][mod_name] = ans_mod_out

        return ret


def __virtual__():
    '''
    Disable, if Ansible is not available around on the Minion.
    '''
    setattr(sys.modules[__name__], 'call', lambda **kwargs: AnsibleState()(**kwargs))   # pylint: disable=W0108
    return ansible is not None
