'''
Support for Debconf
'''

# Import python libs
import os
import re

# Import salt libs
import salt.utils


def _unpack_lines(out):
    '''
    Unpack the debconf lines
    '''
    rexp = ('(?ms)'
            '^(?P<package>[^#]\S+)[\t ]+'
            '(?P<question>\S+)[\t ]+'
            '(?P<type>\S+)[\t ]+'
            '(?P<value>[^\n]*)$')
    lines = re.findall(rexp, out)
    return lines


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    return 'debconf' if __grains__['os'] in ['Debian', 'Ubuntu'] else False


def get_selections(fetchempty=True):
    '''
    Answers to debconf questions for all packages in the following format::

        {'package': [['question', 'type', 'value'], ...]}

    CLI Example::

        salt '*' debconf.get_selections
    '''
    selections = {}
    cmd = 'debconf-get-selections'

    out = __salt__['cmd.run_stdout'](cmd)

    lines = _unpack_lines(out)

    for line in lines:
        package, question, type, value = line
        if fetchempty or value:
            (selections
                .setdefault(package, [])
                .append([question, type, value]))

    return selections


def show(name):
    '''
    Answers to debconf questions for a package in the following format::

        [['question', 'type', 'value'], ...]

    If debconf doesn't know about a package, we return None.

    CLI Example::

        salt '*' debconf.show <package name>
    '''
    selections = get_selections()

    result = selections.get(name)
    return result

def _set_file(path):
    '''
    Execute the set selections command for debconf
    '''
    cmd = 'debconf-set-selections {0}'.format(path)

    __salt__['cmd.run_stdout'](cmd)

def set(package, question, type, value, *extra):
    '''
    Set answers to debconf questions for a package.

    CLI Example::

        salt '*' debconf.set <package> <question> <type> <value> [<value> ...]
    '''

    if extra:
        value = ' '.join((value,) + tuple(extra))

    fd_, fname = salt.utils.mkstemp(prefix="salt-", close_fd=False)

    line = "{0} {1} {2} {3}".format(package, question, type, value)
    os.write(fd_, line)
    os.close(fd_)

    _set_file(fname)

    os.unlink(fname)

    return True

def set_file(path):
    '''
    Set answers to debconf questions from a file.

    CLI Example::

        salt '*' debconf.set_file salt://pathto/pkg.selections
    '''

    r = False

    path = __salt__['cp.cache_file'](path)
    if path:
        _set_file(path)
        r = True

    return r
