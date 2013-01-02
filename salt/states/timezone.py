'''
Management of timezones
=======================

The timezone can be managed for the system:

.. code-block:: yaml

    America/Denver:
      timezone.system
        utc: True
'''


def __virtual__():
    '''
    Only load if the timezone module is available in __salt__
    '''
    return 'timezone' if 'timezone.get_zone' in __salt__ else False


def system(name, utc=''):
    '''
    Set the timezone for the system

    name
        The name of the timezone to use (e.g.: America/Denver)

    utc
        Whether or not to use UTC (default is True)
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    # Set up metadata
    do_utc = False
    do_zone = False
    myzone = __salt__['timezone.get_zone']()
    myutc = True
    messages = []
    if __salt__['timezone.get_hwclock']() == 'localtime':
        myutc = False

    # Check the time zone
    if myzone == name:
        ret['result'] = True
        messages.append('Timezone {0} already set'.format(name))
    else:
        do_zone = True

    # If the user passed in utc, do a check
    if utc != '' and utc != myutc:
        ret['result'] = None
        do_utc = True
    elif utc != '' and utc == myutc:
        messages.append('UTC already set to {0}'.format(name))

    if ret['result'] == True:
        ret['comment'] = ', '.join(messages)
        return ret

    if __opts__['test']:
        messages = []
        if myzone != name:
            messages.append('Timezone {0} needs to be set'.format(name))
        if utc != '' and myutc != utc:
            messages.append('UTC needs to be set to {0}'.format(utc))
        ret['comment'] = ', '.join(messages)
        return ret

    messages = []

    if do_zone:
        if __salt__['timezone.set_zone'](name):
            ret['changes']['timezone'] = name
            messages.append('Set timezone {0}'.format(name))
            ret['result'] = True
        else:
            messages.append('Failed to set timezone')
            ret['result'] = False

    if do_utc:
        clock = 'localtime'
        if utc:
            clock = 'UTC'
        if __salt__['timezone.set_hwclock'](clock):
            ret['changes']['utc'] = utc
            messages.append('Set UTC to {0}'.format(utc))
            ret['result'] = True
        else:
            messages.append('Failed to set UTC to {0}'.format(utc))
            ret['result'] = False

    ret['comment'] = ', '.join(messages)
    return ret
