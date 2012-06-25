'''
Support for Apache
'''

import re
import salt.utils

__outputter__ = {
    'signal': 'txt',
}


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    cmd = _detect_os()
    if salt.utils.which(cmd):
        return 'apache'
    return False


def _detect_os():
    '''
    Apache commands and paths differ depending on packaging
    '''
    httpd = ('CentOS', 'Scientific', 'RedHat', 'Fedora', 'Arch')
    apache2 = ('Ubuntu', 'Debian',)
    if __grains__['os'] in httpd:
        return 'apachectl'
    elif __grains__['os'] in apache2:
        return 'apache2ctl'
    else:
        return 'apachectl'


def version():
    '''
    Return server version from apachectl -v

    CLI Example::

        salt '*' apache.version
    '''
    cmd = _detect_os() + ' -v'
    out = __salt__['cmd.run'](cmd).split('\n')
    ret = out[0].split(': ')
    return ret[1]


def fullversion():
    '''
    Return server version from apachectl -V

    CLI Example::

        salt '*' apache.fullversion
    '''
    cmd = _detect_os() + ' -V'
    ret = {}
    ret['compiled_with'] = []
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if ': ' in line:
            comps = line.split(': ')
            if not comps:
                continue
            ret[comps[0].strip().lower().replace(' ', '_')] = comps[1].strip()
        elif ' -D' in line:
            cw = line.strip(' -D ')
            ret['compiled_with'].append(cw)
    return ret


def modules():
    '''
    Return list of static and shared modules from apachectl -M

    CLI Example::

        salt '*' apache.modules
    '''
    cmd = _detect_os() + ' -M'
    ret = {}
    ret['static'] = []
    ret['shared'] = []
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        comps = line.split()
        if not comps:
            continue
        if '(static)' in line:
            ret['static'].append(comps[0])
        if '(shared)' in line:
            ret['shared'].append(comps[0])
    return ret


def servermods():
    '''
    Return list of modules compiled into the server (apachectl -l)

    CLI Example::

        salt '*' apache.servermods
    '''
    cmd = _detect_os() + ' -l'
    ret = []
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if not line:
            continue
        if '.c' in line:
            ret.append(line.strip())
    return ret


def directives():
    '''
    Return list of directives together with expected arguments
    and places where the directive is valid (``apachectl -L``)

    CLI Example::

        salt '*' apache.directives
    '''
    cmd = _detect_os() + ' -L'
    ret = {}
    out = __salt__['cmd.run'](cmd)
    out = out.replace('\n\t', '\t')
    for line in out.split('\n'):
        if not line:
            continue
        comps = line.split('\t')
        desc = '\n'.join(comps[1:])
        ret[comps[0]] = desc
    return ret


def vhosts():
    '''
    Show the settings as parsed from the config file (currently
    only shows the virtualhost settings). (``apachectl -S``)
    Because each additional virtual host adds to the execution
    time, this command may require a long timeout be specified.

    CLI Example::

        salt -t 10 '*' apache.vhosts
    '''
    cmd = _detect_os() + ' -S'
    ret = {}
    namevhost = ''
    out = __salt__['cmd.run'](cmd)
    for line in out.split('\n'):
        if not line:
            continue
        comps = line.split()
        if 'is a NameVirtualHost' in line:
            namevhost = comps[0]
            ret[namevhost] = {}
        else:
            if comps[0] == 'default':
                ret[namevhost]['default'] = {}
                ret[namevhost]['default']['vhost'] = comps[2]
                ret[namevhost]['default']['conf'] = re.sub(r'\(|\)', '', comps[3])
            if comps[0] == 'port':
                ret[namevhost][comps[3]] = {}
                ret[namevhost][comps[3]]['vhost'] = comps[3]
                ret[namevhost][comps[3]]['conf'] = re.sub(r'\(|\)', '', comps[4])
                ret[namevhost][comps[3]]['port'] = comps[1]
    return ret


def signal(signal=None):
    '''
    Signals httpd to start, restart, or stop.

    CLI Example::

        salt '*' apache.signal restart
    '''
    no_extra_args = ('configtest', 'status', 'fullstatus')
    valid_signals = ('start', 'stop', 'restart', 'graceful', 'graceful-stop')

    if signal not in valid_signals and signal not in no_extra_args:
        return
    # Make sure you use the right arguments
    if signal in valid_signals:
        arguments = ' -k {0}'.format(signal)
    else:
        arguments = ' {0}'.format(signal)
    cmd = _detect_os() + arguments
    out = __salt__['cmd.run_all'](cmd)

    # A non-zero return code means fail
    if out['retcode'] and out['stderr']:
        ret = out['stderr'].strip()
    # 'apachectl configtest' returns 'Syntax OK' to stderr
    elif out['stderr']:
        ret = out['stderr'].strip()
    elif out['stdout']:
        ret = out['stdout'].strip()
    # No output for something like: apachectl graceful
    else:
        ret = 'Command: "{0}" completed successfully!'.format(cmd)
    return ret
