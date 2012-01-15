'''
Support for Tomcat
'''

import os


def __catalina_home():
    '''
    Tomcat paths differ depending on packaging
    '''
    locations = ['/usr/share/tomcat6', '/opt/tomcat']
    for location in locations:
        if os.path.isdir(location):
            return location


def version():
    '''
    Return server version from catalina.sh version

    CLI Example::

        salt '*' tomcat.version
    '''
    cmd = __catalina_home() + '/bin/catalina.sh version'
    out = __salt__['cmd.run'](cmd).split('\n')
    ret = out[0].split(': ')
    for line in out:
        if not line:
            continue
        if 'Server version' in line:
            comps = line.split(': ')
            return comps[1]


def fullversion():
    '''
    Return all server information from catalina.sh version

    CLI Example::

        salt '*' tomcat.fullversion
    '''
    cmd = __catalina_home() + '/bin/catalina.sh version'
    ret = {}
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if not line:
            continue
        if ': ' in line:
            comps = line.split(': ')
            ret[comps[0]] = comps[1]
    return ret


def signal(signal=None):
    '''
    Signals catalina to start, stop, securestart, forcestop.

    CLI Example::

        salt '*' tomcat.signal start
    '''
    valid_signals = {'forcestop': 'stop -force',
                     'securestart': 'start -security',
                     'start': 'start',
                     'stop': 'stop'}

    if not valid_signals[signal]:
        return

    cmd = __catalina_home() + '/bin/catalina.sh %s' % valid_signals[signal]
    out = __salt__['cmd.run'](cmd)
