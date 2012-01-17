'''
Support for nginx
'''

__outputter__ = {
    'signal': 'txt',
}

def version():
    '''
    Return server version from nginx -v

    CLI Example::

        salt '*' nginx.version
    '''
    cmd = 'nginx -v'
    out = __salt__['cmd.run'](cmd).split('\n')
    ret = out[0].split(': ')
    return ret[2]

def signal(signal=None):
    '''
    Signals httpd to start, restart, or stop.

    CLI Example::

        salt '*' nginx.signal reload
    '''
    valid_signals = ('reopen', 'stop', 'quit', 'reload')

    if signal not in valid_signals:
        return

    # Make sure you use the right arguments
    if signal in valid_signals:
        arguments = ' -s {0}'.format(signal)
    else:
        arguments = ' {0}'.format(signal)
    cmd = 'nginx' + arguments
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
