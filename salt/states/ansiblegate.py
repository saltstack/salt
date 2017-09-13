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
try:
    import ansible
except ImportError as err:
    ansible = None


__virtualname__ = 'ansible'


class AnsibleState(object):
    def __init__(self, available):
        self.available = available

    def call(self, **kwargs):
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

        print "\n\n\n>>>", kwargs, "\n\n\n"

        return ret


_ansible_state = AnsibleState(ansible is not None)


def __virtual__():
    '''
    Disable, if Ansible is not available around on the Minion.
    '''
    return _ansible_state.available


def call(**kwargs):
    '''
    Call the Ansible module.
    :param kwargs:
    :return:
    '''
    return _ansible_state.call(**kwargs)
