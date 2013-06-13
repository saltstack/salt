'''
Support for nzbget
'''

# Import salt libs
import salt.utils

__func_alias__ = {
    'list_': 'list'
}

def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    cmd = 'nzbget'
    if salt.utils.which(cmd):
        return 'nzbget'
    return False


def version():
    '''
    Return version from nzbget -v.

    CLI Example::

        salt '*' nzbget.version
    '''
    cmd = 'nzbget -v'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return {'version': ret[1]}


def serverversion():
    '''
    Return server version from nzbget -V.
    Default user is root.

    CLI Example::

        salt '*' nzbget.serverversion moe
    '''
    cmd = 'ps aux | grep "nzbget -D" | grep -v grep | cut -d " " -f 1'
    user = __salt__['cmd.run'](cmd)
    if not user:
        return 'Server not running'
    cmd = 'nzbget -V -c ~' + user + '/.nzbget | grep "server returned"'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return {'user': user,
            'version': ret[1], }


def start(user=None):
    '''
    Start nzbget as a daemon using -D option
    Default user is root.

    CLI Example::

        salt '*' nzbget.start
    '''
    cmd = 'nzbget -D'
    if user:
        cmd = 'su - ' + user + ' -c "' + cmd + '"'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def stop(user=None):
    '''
    Stop nzbget daemon using -Q option.
    Default user is root.

    CLI Example::

        salt '*' nzbget.stop curly
    '''
    cmd = 'nzbget -Q'
    if user:
        cmd = 'su - ' + user + ' -c "' + cmd + '"'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def list_(user=None):
    '''
    Return list of active downloads using nzbget -L.
    Default user is root.

    CLI Example::

        salt '*' nzbget.list larry
    '''
    ret = {}
    inqueue = ''
    queuelist = []
    cmd = 'nzbget -L'
    if user:
        cmd = cmd + ' -c ~' + user + '/.nzbget'
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if 'Queue List' in line:
            inqueue = 1
        if '----------' in line:
            if inqueue == 1:
                inqueue = 2
            else:
                inqueue = ''
            continue
        if inqueue:
            queuelist.append(line)
            continue
        if ': ' not in line:
            continue
        comps = line.split(': ')
        ret[comps[0]] = comps[1]
    if queuelist:
        ret['Queue List'] = queuelist
    return ret


def pause(user=None):
    '''
    Pause nzbget daemon using -P option.
    Default user is root.

    CLI Example::

        salt '*' nzbget.pause shemp
    '''
    cmd = 'nzbget -P'
    if user:
        cmd = cmd + ' -c ~' + user + '/.nzbget'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def unpause(user=None):
    '''
    Unpause nzbget daemon using -U option.
    Default user is root.

    CLI Example::

        salt '*' nzbget.unpause shemp
    '''
    cmd = 'nzbget -U'
    if user:
        cmd = cmd + ' -c ~' + user + '/.nzbget'
    out = __salt__['cmd.run'](cmd).splitlines()
    return out
