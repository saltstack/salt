'''
Management of timezones
=======================

The timezone can be managed for the system:

.. code-block:: yaml

    America/Denver:
      timezone.system

The system and the hardware clock are not necessarily set to the same time.
By default, the hardware clock is set to localtime, meaning it is set to the
same time as the system clock. If `utc` is set to True, then the hardware clock
will be set to UTC, and the system clock will be an offset of that.

.. code-block:: yaml

    America/Denver:
      timezone.system:
        - utc: True

The Ubuntu community documentation contains an explanation of this setting, as
it applies to systems that dual-boot with Windows.

http://tinyurl.com/5fjzmn
'''


def __virtual__():
    '''
    Only load if the timezone module is available in __salt__
    '''
    return 'timezone' if 'timezone.get_zone' in __salt__ else False


def system(name, utc=''):
    '''
    Set the timezone for the system.

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
    compzone = __salt__['timezone.zone_compare'](name)
    myutc = True
    messages = []
    if __salt__['timezone.get_hwclock']() == 'localtime':
        myutc = False

    # Check the time zone
    if compzone is True:
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
        if compzone is False:
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
