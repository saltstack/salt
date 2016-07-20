# -*- coding: utf-8 -*-
'''
Support for Apache

.. note::
    The functions in here are generic functions designed to work with
    all implementations of Apache. Debian-specific functions have been moved into
    deb_apache.py, but will still load under the ``apache`` namespace when a
    Debian-based system is detected.
'''

# Import python libs
from __future__ import absolute_import, generators, print_function, with_statement
import re
import logging

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module
import salt.ext.six as six
from salt.ext.six.moves import cStringIO
from salt.ext.six.moves.urllib.error import URLError
from salt.ext.six.moves.urllib.request import (
        HTTPBasicAuthHandler as _HTTPBasicAuthHandler,
        HTTPDigestAuthHandler as _HTTPDigestAuthHandler,
        urlopen as _urlopen,
        build_opener as _build_opener,
        install_opener as _install_opener
)
# pylint: enable=import-error,no-name-in-module

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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
    # TODO: Add pillar support for the apachectl location
    os_family = __grains__['os_family']
    if os_family == 'RedHat':
        return 'apachectl'
    elif os_family == 'Debian' or os_family == 'Suse':
        return 'apache2ctl'
    else:
        return 'apachectl'


def version():
    '''
    Return server version (``apachectl -v``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.version
    '''
    cmd = '{0} -v'.format(_detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[1]


def fullversion():
    '''
    Return server version (``apachectl -V``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.fullversion
    '''
    cmd = '{0} -V'.format(_detect_os())
    ret = {}
    ret['compiled_with'] = []
    out = __salt__['cmd.run'](cmd).splitlines()
    # Example
    #  -D APR_HAS_MMAP
    define_re = re.compile(r'^\s+-D\s+')
    for line in out:
        if ': ' in line:
            comps = line.split(': ')
            if not comps:
                continue
            ret[comps[0].strip().lower().replace(' ', '_')] = comps[1].strip()
        elif ' -D' in line:
            cwith = define_re.sub('', line)
            ret['compiled_with'].append(cwith)
    return ret


def modules():
    '''
    Return list of static and shared modules (``apachectl -M``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.modules
    '''
    cmd = '{0} -M'.format(_detect_os())
    ret = {}
    ret['static'] = []
    ret['shared'] = []
    out = __salt__['cmd.run'](cmd).splitlines()
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
    Return list of modules compiled into the server (``apachectl -l``)

    CLI Example:

    .. code-block:: bash

        salt '*' apache.servermods
    '''
    cmd = '{0} -l'.format(_detect_os())
    ret = []
    out = __salt__['cmd.run'](cmd).splitlines()
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

    CLI Example:

    .. code-block:: bash

        salt '*' apache.directives
    '''
    cmd = '{0} -L'.format(_detect_os())
    ret = {}
    out = __salt__['cmd.run'](cmd)
    out = out.replace('\n\t', '\t')
    for line in out.splitlines():
        if not line:
            continue
        comps = line.split('\t')
        desc = '\n'.join(comps[1:])
        ret[comps[0]] = desc
    return ret


def vhosts():
    '''
    Show the settings as parsed from the config file (currently
    only shows the virtualhost settings) (``apachectl -S``).
    Because each additional virtual host adds to the execution
    time, this command may require a long timeout be specified
    by using ``-t 10``.

    CLI Example:

    .. code-block:: bash

        salt -t 10 '*' apache.vhosts
    '''
    cmd = '{0} -S'.format(_detect_os())
    ret = {}
    namevhost = ''
    out = __salt__['cmd.run'](cmd)
    for line in out.splitlines():
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
                ret[namevhost]['default']['conf'] = re.sub(
                    r'\(|\)',
                    '',
                    comps[3]
                )
            if comps[0] == 'port':
                ret[namevhost][comps[3]] = {}
                ret[namevhost][comps[3]]['vhost'] = comps[3]
                ret[namevhost][comps[3]]['conf'] = re.sub(
                    r'\(|\)',
                    '',
                    comps[4]
                )
                ret[namevhost][comps[3]]['port'] = comps[1]
    return ret


def signal(signal=None):
    '''
    Signals httpd to start, restart, or stop.

    CLI Example:

    .. code-block:: bash

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


def useradd(pwfile, user, password, opts=''):
    '''
    Add HTTP user using the ``htpasswd`` command. If the ``htpasswd`` file does not
    exist, it will be created. Valid options that can be passed are:

    .. code-block:: text

        n  Don't update file; display results on stdout.
        m  Force MD5 hashing of the password (default).
        d  Force CRYPT(3) hashing of the password.
        p  Do not hash the password (plaintext).
        s  Force SHA1 hashing of the password.

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' apache.useradd /etc/httpd/htpasswd larry badpass opts=ns
    '''
    return __salt__['webutil.useradd'](pwfile, user, password, opts)


def userdel(pwfile, user):
    '''
    Delete HTTP user from the specified ``htpasswd`` file.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.userdel /etc/httpd/htpasswd larry
    '''
    return __salt__['webutil.userdel'](pwfile, user)


def server_status(profile='default'):
    '''
    Get Information from the Apache server-status handler

    .. note::

        The server-status handler is disabled by default.
        In order for this function to work it needs to be enabled.
        See http://httpd.apache.org/docs/2.2/mod/mod_status.html

    The following configuration needs to exists in pillar/grains.
    Each entry nested in ``apache.server-status`` is a profile of a vhost/server.
    This would give support for multiple apache servers/vhosts.

    .. code-block:: yaml

        apache.server-status:
          default:
            url: http://localhost/server-status
            user: someuser
            pass: password
            realm: 'authentication realm for digest passwords'
            timeout: 5

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.server_status
        salt '*' apache.server_status other-profile
    '''
    ret = {
        'Scoreboard': {
            '_': 0,
            'S': 0,
            'R': 0,
            'W': 0,
            'K': 0,
            'D': 0,
            'C': 0,
            'L': 0,
            'G': 0,
            'I': 0,
            '.': 0,
        },
    }

    # Get configuration from pillar
    url = __salt__['config.get'](
        'apache.server-status:{0}:url'.format(profile),
        'http://localhost/server-status'
    )
    user = __salt__['config.get'](
        'apache.server-status:{0}:user'.format(profile),
        ''
    )
    passwd = __salt__['config.get'](
        'apache.server-status:{0}:pass'.format(profile),
        ''
    )
    realm = __salt__['config.get'](
        'apache.server-status:{0}:realm'.format(profile),
        ''
    )
    timeout = __salt__['config.get'](
        'apache.server-status:{0}:timeout'.format(profile),
        5
    )

    # create authentication handler if configuration exists
    if user and passwd:
        basic = _HTTPBasicAuthHandler()
        basic.add_password(realm=realm, uri=url, user=user, passwd=passwd)
        digest = _HTTPDigestAuthHandler()
        digest.add_password(realm=realm, uri=url, user=user, passwd=passwd)
        _install_opener(_build_opener(basic, digest))

    # get http data
    url += '?auto'
    try:
        response = _urlopen(url, timeout=timeout).read().splitlines()
    except URLError:
        return 'error'

    # parse the data
    for line in response:
        splt = line.split(':', 1)
        splt[0] = splt[0].strip()
        splt[1] = splt[1].strip()

        if splt[0] == 'Scoreboard':
            for c in splt[1]:
                ret['Scoreboard'][c] += 1
        else:
            if splt[1].isdigit():
                ret[splt[0]] = int(splt[1])
            else:
                ret[splt[0]] = float(splt[1])

    # return the good stuff
    return ret


def _parse_config(conf, slot=None):
    ret = cStringIO()
    if isinstance(conf, str):
        if slot:
            print('{0} {1}'.format(slot, conf), file=ret, end='')
        else:
            print('{0}'.format(conf), file=ret, end='')
    elif isinstance(conf, list):
        print('{0} {1}'.format(str(slot), ' '.join(conf)), file=ret, end='')
    elif isinstance(conf, dict):
        print('<{0} {1}>'.format(
            slot,
            _parse_config(conf['this'])),
            file=ret
        )
        del conf['this']
        for key, value in six.iteritems(conf):
            if isinstance(value, str):
                print('{0} {1}'.format(key, value), file=ret)
            elif isinstance(value, list):
                print('{0} {1}'.format(key, ' '.join(value)), file=ret)
            elif isinstance(value, dict):
                print(_parse_config(value, key), file=ret)
        print('</{0}>'.format(slot), file=ret, end='')

    ret.seek(0)
    return ret.read()


def config(name, config, edit=True):
    '''
    Create VirtualHost configuration files

    name
        File for the virtual host
    config
        VirtualHost configurations

    .. note::

        This function is not meant to be used from the command line.
        Config is meant to be an ordered dict of all of the apache configs.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.config /etc/httpd/conf.d/ports.conf config="[{'Listen': '22'}]"
    '''

    for entry in config:
        key = next(six.iterkeys(entry))
        configs = _parse_config(entry[key], key)
        if edit:
            with salt.utils.fopen(name, 'w') as configfile:
                configfile.write('# This file is managed by saltstack.\n')
                configfile.write(configs)
    return configs
