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

__virtualname__ = 'ansible'


def __virtual__():
    return True


def call(*args, **kwargs):
    '''
    :return:
    '''

    ret = {
        'name': kwargs.keys(),
        'changes': {},
        'comment': '',
        'result': None,
    }
    return ret


