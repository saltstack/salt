'''
Support for Tomcat
'''

# Import python libs
import glob


def __virtual__():
    '''
    Only load tomcat if it is installed
    '''
    if __catalina_home():
        return 'tomcat'
    return False

def __catalina_home():
    '''
    Tomcat paths differ depending on packaging
    '''
    locations = ['/usr/share/tomcat*', '/opt/tomcat']
    for location in locations:
        catalina_home = glob.glob(location)
    if catalina_home:
        return catalina_home[-1]


def version():
    '''
    Return server version from catalina.sh version

    CLI Example::

        salt '*' tomcat.version
    '''
    cmd = __catalina_home() + '/bin/catalina.sh version'
    out = __salt__['cmd.run'](cmd).splitlines()
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
    out = __salt__['cmd.run'](cmd).splitlines()
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

    cmd = '{0}/bin/catalina.sh {1}'.format(
        __catalina_home(), valid_signals[signal]
    )
    __salt__['cmd.run'](cmd)
