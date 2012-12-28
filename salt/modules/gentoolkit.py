'''
Support for Gentoolkit

'''

def __virtual__():
    '''
    Only work on Gentoo systems with gentoolkit installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('revdep-rebuild'):
        return 'gentoolkit'
    return False

def revdep_rebuild(lib=None):
    '''
    Fix up broken reverse dependencies

    lib
        Search for reverse dependencies for a particular library rather
        than every library on the system. It can be a full path to a
        library or basic regular expression.

    CLI Example::

        salt '*' gentoolkit.revdep_rebuild
    '''
    cmd = 'revdep-rebuild --quiet --no-progress'
    if lib is not None:
        cmd += ' --library={0}'.format(lib)
    return __salt__['cmd.retcode'](cmd) == 0
