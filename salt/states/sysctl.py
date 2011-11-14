'''
Kernel Sysctl Management
========================

Control the kernel sysctl system

.. code-block:: yaml

  vm.swappines:
    sysctl:
      - present
      - value: 20
'''


def present(name, value, config='/etc/sysctl.conf'):
    '''
    Ensure that the named sysctl value is set

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
