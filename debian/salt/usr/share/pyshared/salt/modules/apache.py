'''
Support for Apache
'''

import subprocess

def __detect_os():
    '''
    Apache commands and paths differ depending on packaging
    '''
    httpd = 'CentOS Scientific RedHat Fedora'
    apache2 = 'Ubuntu'
    if httpd.count(__grains__['os']):
        return 'apachectl'
    elif apache2.count(__grains__['os']):
        return 'apache2ctl'
    else:
        return 'apachectl'

def version():
    '''
    Return server version from apachectl -v

    CLI Example:
    salt '*' apache.version
    '''
    cmd = __detect_os() + ' -v'
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    ret = out[0].split(': ')
    return ret[1]

def fullversion():
    '''
    Return server version from apachectl -V

    CLI Example:
    salt '*' apache.fullversion
    '''
    cmd = __detect_os() + ' -V'
    ret = {}
    ret['compiled_with'] = []
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        if ': ' in line:
            comps = line.split(': ')
            ret[comps[0].strip().lower().replace(' ', '_')] = comps[1].strip()
        elif ' -D' in line:
            cw = line.strip(' -D ')
            ret['compiled_with'].append(cw)
    return ret

def modules():
    '''
    Return list of static and shared modules from apachectl -M

    CLI Example:
    salt '*' apache.modules
    '''
    cmd = __detect_os() + ' -M'
    ret = {}
    ret['static'] = []
    ret['shared'] = []
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        comps = line.split()
        if '(static)' in line:
            ret['static'].append(comps[0])
        if '(shared)' in line:
            ret['shared'].append(comps[0])
    return ret

def servermods():
    '''
    Return list of modules compiled into the server (apachectl -l)

    CLI Example:
    salt '*' apache.servermods
    '''
    cmd = __detect_os() + ' -l'
    ret = []
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        if '.c' in line:
            ret.append(line.strip())
    return ret

def directives():
    '''
    Return list of directives together with expected arguments
    and places where the directive is valid (apachectl -L)

    CLI Example:
    salt '*' apache.directives
    '''
    cmd = __detect_os() + ' -L'
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    out = out.replace('\n\t', '\t')
    for line in out.split('\n'):
        if not line.count(' '):
            continue
        comps = line.split('\t')
        desc = '\n'.join(comps[1:])
        ret[comps[0]] = desc
    return ret

def vhosts():
    '''
    Show the settings as parsed from the config file (currently
    only shows the virtualhost settings). (apachectl -S)
    Because each additional virtual host adds to the execution
    time, this command may require a long timeout be specified.

    CLI Example:
    salt -t 10 '*' apache.vhosts
    '''
    cmd = __detect_os() + ' -S'
    ret = {}
    namevhost = ''
    out = __salt__['cmd.run'](cmd)
    for line in out.split('\n'):
        if not line.count(' '):
            continue
        comps = line.split()
        if 'is a NameVirtualHost' in line:
            namevhost = comps[0]
            ret[namevhost] = {}
        else:
            if comps[0] == 'default':
                ret[namevhost]['default'] = {}
                ret[namevhost]['default']['vhost'] = comps[2]
                ret[namevhost]['default']['conf'] = comps[3].replace('(', '').replace(')', '')
            if comps[0] == 'port':
                ret[namevhost][comps[3]] = {}
                ret[namevhost][comps[3]]['vhost'] = comps[3]
                ret[namevhost][comps[3]]['conf'] = comps[4].replace('(', '').replace(')', '')
                ret[namevhost][comps[3]]['port'] = comps[1]
    return ret

def signal(signal = None):
    '''
    Signals httpd to start, restart, or stop.

    CLI Example:
    salt '*' apache.signal restart
    '''
    valid_signals = 'start stop restart graceful graceful-stop'
    if not valid_signals.count(signal):
        return
    cmd = __detect_os() + ' -k %s' % signal
    out = __salt__['cmd.run'](cmd)
