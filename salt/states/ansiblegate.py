# -*- coding: utf-8 -*-
r'''
Author: Bo Maryniuk <bo@suse.de>

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
from __future__ import absolute_import
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
            'result': None,
        }

        for mod_name, mod_params in kwargs.items():
            args, kwargs = self.get_args(mod_params)
            ans_mod_out = __salt__['ansible.{0}'.format(mod_name)](*args, **kwargs)
            ret['changes'][mod_name] = ans_mod_out

        return ret


def __virtual__():
    '''
    Disable, if Ansible is not available around on the Minion.
    '''
    setattr(sys.modules[__name__], 'call', lambda **kwargs: AnsibleState()(**kwargs))
    return ansible is not None
