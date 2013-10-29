# -*- coding: utf-8 -*-
'''
Manages configuration files via augeas

This module requires the ``augeas`` Python module.

.. _Augeas: http://augeas.net/

.. warning::

    Minimal installations of Debian and Ubuntu have been seen to have packaging
    bugs with python-augeas, causing the augeas module to fail to import. If
    the minion has the augeas module installed, but the functions in this
    execution module fail to run due to being unavailable, first restart the
    salt-minion service. If the problem persists past that, the following
    command can be run from the master to determine what is causing the import
    to fail:

    .. code-block:: bash

        salt minion-id cmd.run 'python -c "from augeas import Augeas"'

    For affected Debian/Ubuntu hosts, installing ``libpython2.7`` has been
    known to resolve the issue.
'''

# Import python libs
import os

# Make sure augeas python interface is installed
HAS_AUGEAS = False
try:
    from augeas import Augeas
    HAS_AUGEAS = True
except ImportError:
    pass

# Import salt libs
from salt.exceptions import SaltInvocationError


def __virtual__():
    '''
    Only run this module if the augeas python module is installed
    '''
    if HAS_AUGEAS:
        return 'augeas'
    return False


def _recurmatch(path, aug):
    '''
    Recursive generator providing the infrastructure for
    augtools print behaviour.

    This function is based on test_augeas.py from
    Harald Hoyer <harald@redhat.com>  in the python-augeas
    repository
    '''
    if path:
        clean_path = path.rstrip('/*')
        yield (clean_path, aug.get(path))

        for i in aug.match(clean_path + '/*'):
            i = i.replace('!', '\\!')  # escape some dirs
            for _match in _recurmatch(i, aug):
                yield _match


def _lstrip_word(word, prefix):
    '''
    Return a copy of the string after the specified prefix was removed
    from the beginning of the string
    '''

    if str(word).startswith(prefix):
        return str(word)[len(prefix):]
    return word


def get(path, value=''):
    '''
    Get a value for a specific augeas path

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.get /files/etc/hosts/1/ ipaddr
    '''
    aug = Augeas()
    ret = {}

    path = path.rstrip('/')
    if value:
        path += '/{0}'.format(value.strip('/'))

    try:
        _match = aug.match(path)
    except RuntimeError as err:
        return {'error': str(err)}

    if _match:
        ret[path] = aug.get(path)
    else:
        ret[path] = ''  # node does not exist

    return ret


def setvalue(*args):
    '''
    Set a value for a specific augeas path

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue /files/etc/hosts/1/canonical localhost

    This will set the first entry in /etc/hosts to localhost

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue /files/etc/hosts/01/ipaddr 192.168.1.1 \\
                                 /files/etc/hosts/01/canonical test

    Adds a new host to /etc/hosts the ip address 192.168.1.1 and hostname test

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue prefix=/files/etc/sudoers/ \\
                 "spec[user = '%wheel']/user" "%wheel" \\
                 "spec[user = '%wheel']/host_group/host" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]/tag" 'PASSWD' \\
                 "spec[user = '%wheel']/host_group/command[2]" '/usr/bin/apt-get' \\
                 "spec[user = '%wheel']/host_group/command[2]/tag" NOPASSWD

    Ensures that the following line is present in /etc/sudoers::

        %wheel ALL = PASSWD : ALL , NOPASSWD : /usr/bin/apt-get , /usr/bin/aptitude
    '''
    aug = Augeas()
    ret = {'retval': False}

    tuples = filter(lambda x: not str(x).startswith('prefix='), args)
    prefix = filter(lambda x: str(x).startswith('prefix='), args)
    if prefix:
        if len(prefix) > 1:
            raise SaltInvocationError(
                'Only one \'prefix=\' value is permitted'
            )
        else:
            prefix = prefix[0].split('=', 1)[1]

    if len(tuples) % 2 != 0:
        raise SaltInvocationError('Uneven number of path/value arguments')

    tuple_iter = iter(tuples)
    for path, value in zip(tuple_iter, tuple_iter):
        target_path = path
        if prefix:
            target_path = os.path.join(prefix.rstrip('/'), path.lstrip('/'))
        try:
            aug.set(target_path, str(value))
        except ValueError as err:
            ret['error'] = 'Multiple values: {0}'.format(err)

    try:
        aug.save()
        ret['retval'] = True
    except IOError as err:
        ret['error'] = str(err)
    return ret


def match(path, value=''):
    '''
    Get matches for path expression

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.match /files/etc/services/service-name ssh
    '''
    aug = Augeas()
    ret = {}

    try:
        matches = aug.match(path)
    except RuntimeError:
        return ret

    for _match in matches:
        if value and aug.get(_match) == value:
            ret[_match] = value
        elif not value:
            ret[_match] = aug.get(_match)
    return ret


def remove(path):
    '''
    Get matches for path expression

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.remove /files/etc/sysctl.conf/net.ipv4.conf.all.log_martians
    '''
    aug = Augeas()
    ret = {'retval': False}
    try:
        count = aug.remove(path)
        aug.save()
        if count == -1:
            ret['error'] = 'Invalid node'
        else:
            ret['retval'] = True
    except (RuntimeError, IOError) as err:
        ret['error'] = str(err)

    ret['count'] = count

    return ret


def ls(path):  # pylint: disable=C0103
    '''
    List the direct children of a node

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.ls /files/etc/passwd
    '''
    def _match(path):
        ''' Internal match function '''
        try:
            matches = aug.match(path)
        except RuntimeError:
            return {}

        ret = {}
        for _ma in matches:
            ret[_ma] = aug.get(_ma)
        return ret

    aug = Augeas()

    path = path.rstrip('/') + '/'
    match_path = path + '*'

    matches = _match(match_path)
    ret = {}

    for key, value in matches.iteritems():
        name = _lstrip_word(key, path)
        if _match(key + '/*'):
            ret[name + '/'] = value  # has sub nodes, e.g. directory
        else:
            ret[name] = value
    return ret


def tree(path):
    '''
    Returns recursively the complete tree of a node

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.tree /files/etc/
    '''
    aug = Augeas()

    path = path.rstrip('/') + '/'
    match_path = path
    return dict([i for i in _recurmatch(match_path, aug)])
