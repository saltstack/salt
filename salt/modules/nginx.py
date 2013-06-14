'''
Support for nginx
'''

# Import salt libs
import salt.utils


# Cache the output of running which('nginx') so this module
# doesn't needlessly walk $PATH looking for the same binary
# for nginx over and over and over for each function herein
@salt.utils.memoize
def __detect_os():
    return salt.utils.which('nginx')

def __virtual__():
    '''
    Only load the module if nginx is installed
    '''
    if __detect_os():
        return 'nginx'
    return False

def version():
    '''
    Return server version from nginx -v

    CLI Example::

        salt '*' nginx.version
    '''
    cmd = '{0} -v'.format(__detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[-1]

def configtest():
    '''
    test configuration and exit

    CLI Example::

        salt '*' nginx.configtest
    '''

    cmd = '{0} -t'.format(__detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[-1]


def signal(signal=None):
    '''
    Signals nginx to start, reload, reopen or stop.

    CLI Example::

        salt '*' nginx.signal reload
    '''
    valid_signals = ('start', 'reopen', 'stop', 'quit', 'reload')

    if signal not in valid_signals:
        return

    # Make sure you use the right arguments
    if signal == "start":
        arguments = ''
    else:
        arguments = ' -s {0}'.format(signal)
    cmd = __detect_os() + arguments
    out = __salt__['cmd.run_all'](cmd)

    # A non-zero return code means fail
    if out['retcode'] and out['stderr']:
        ret = out['stderr'].strip()
    # 'nginxctl configtest' returns 'Syntax OK' to stderr
    elif out['stderr']:
        ret = out['stderr'].strip()
    elif out['stdout']:
        ret = out['stdout'].strip()
    # No output for something like: nginxctl graceful
    else:
        ret = 'Command: "{0}" completed successfully!'.format(cmd)
    return ret
