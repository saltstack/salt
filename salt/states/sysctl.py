# -*- coding: utf-8 -*-
'''
Configuration of the Linux kernel using sysctrl.
================================================

Control the kernel sysctl system

.. code-block:: yaml

  vm.swappiness:
    sysctl.present:
      - value: 20
'''

# Import python libs
import re


def __virtual__():
    '''
    This state is only available on Minions which support sysctl
    '''
    return 'sysctl' if 'sysctl.show' in __salt__ else False


def present(name, value, config=None):
    '''
    Ensure that the named sysctl value is set in memory and persisted to the
    named configuration file. The default sysctl configuration file is
    /etc/sysctl.conf

    name
        The name of the sysctl value to edit

    value
        The sysctl value to apply

    config
        The location of the sysctl configuration file. If not specified, the
        proper location will be detected based on platform.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if config is None:
        # Certain linux systems will ignore /etc/sysctl.conf, get the right
        # default configuration file.
        if 'sysctl.default_config' in __salt__:
            config = __salt__['sysctl.default_config']()
        else:
            config = '/etc/sysctl.conf'

    current = __salt__['sysctl.show']()
    if __opts__['test']:
        if name in current:
            if re.sub(' +|\t+', ' ', current[name]) != re.sub(' +|\t+', ' ', str(value)):
                ret['result'] = None
                ret['comment'] = (
                        'Sysctl option {0} set to be changed to {1}'
                        ).format(name, value)
                return ret
            else:
                ret['comment'] = 'Sysctl value {0} = {1} is already set'.format(name, value)
                return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Invalid sysctl option {0} = {1}'.format(name, value)
            return ret

    update = __salt__['sysctl.persist'](name, value, config)

    if update == 'Updated':
        ret['changes'] = {name: value}
        ret['comment'] = 'Updated sysctl value {0} = {1}'.format(name, value)
    elif update == 'Already set':
        ret['comment'] = 'Sysctl value {0} = {1} is already set'.format(
                name,
                value
                )

    return ret
