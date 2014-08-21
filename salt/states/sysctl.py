# -*- coding: utf-8 -*-
'''
Configuration of the Linux kernel using sysctl
==============================================

Control the kernel sysctl system.

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
    return 'sysctl.show' in __salt__


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
    configured = __salt__['sysctl.show'](config_file=True)
    if __opts__['test']:
        if name in current and name not in configured:
            if re.sub(' +|\t+', ' ', current[name]) != re.sub(' +|\t+', ' ', str(value)):
                ret['result'] = None
                ret['comment'] = (
                        'Sysctl option {0} set to be changed to {1}'
                        ).format(name, value)
                return ret
            else:
                ret['result'] = None
                ret['comment'] = 'Sysctl value is currently set on the running system but not in a config file.\n'\
                'Sysctl option {0} set to be changed to {1} in config file.'.format(name, value)
                return ret
        elif name in configured and name not in current:
            ret['result'] = None
            ret['comment'] = 'Sysctl value {0} is present in configuration file but is not present in the running config.\n'\
                    'The value {0} is set to be changed to {1} '
            return ret
        elif name in configured and name in current:
            if str(value) == __salt__['sysctl.get'](name):
                ret['result'] = True
                ret['comment'] = 'Sysctl value {0} = {1} is already set'.format(
                        name,
                        value
                        )
                return ret
        # otherwise, we don't have it set anywhere and need to set it
        ret['result'] = None
        ret['comment'] = 'Sysctl option {0}  set to be changed to {1}'.format(name, value)
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
