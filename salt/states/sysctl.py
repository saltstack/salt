'''
Configuration of the Linux kernel using sysctrl.
================================================

Control the kernel sysctl system

.. code-block:: yaml

  vm.swappines:
    sysctl.present:
      - value: 20
'''

# Import python libs
import re

def present(name, value, config='/etc/sysctl.conf'):
    '''
    Ensure that the named sysctl value is set in memory and persisted to the
    named configuration file. The default sysctl configuration file is
    /etc/sysctl.conf

    name
        The name of the sysctl value to edit

    value
        The sysctl value to apply

    config
        The location of the sysctl configuration file
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

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
