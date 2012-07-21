'''
Support for poudriere
'''
import os
import logging

import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Module load on freebsd only and if poudriere installed
    '''
    if __grains__['os'] == 'FreeBSD' and salt.utils.which('poudriere'):
        return 'poudriere'
    else:
        return False


def _config_file():
    '''
    Return the config file location to use
    '''
    if 'poudriere.config' in __opts__:
        return __opts__['poudriere.config']
    elif 'poudriere.config' in __pillar__:
        return __pillar__['poudriere.config']
    return '/usr/local/etc/poudriere.conf'


def _config_dir():
    '''
    Return the configuration directory to use
    '''
    if 'poudriere.config' in __opts__:
        return __opts__['poudriere.config_dir']
    elif 'poudriere.config' in __pillar__:
        return __pillar__['poudriere.config_dir']
    return '/usr/local/etc/poudriere.d'


def _check_config_exists(config_file=None):
    '''
    Verify the config file is present
    '''
    if config_file is None:
        config_file = _config_file()
    if not os.path.isfile(config_file):
        return False
    return True


def is_jail(name):
    '''
    Return True if jail exists False if not

    CLI Example::

        salt '*' poudriere.is_jail <jail name>
    '''
    jails = list_jails()
    for jail in jails:
        if jail.split()[0] == name:
            return True
    return False


def make_pkgng_aware(jname):
    '''
    Make jail ``jname`` pkgng aware

    CLI Example::

        salt '*' poudriere.make_pkgng_aware <jail name>
    '''
    ret = {'changes': {}}
    cdir = _config_dir()
    # ensure cdir is there
    if not os.path.isdir(cdir):
        os.makedirs(cdir)
        if os.path.isdir(cdir):
            ret['changes'] = 'Created poudriere make file dir {0}'.format(cdir)
        else:
            return 'Could not create or find required directory {0}'.format(
                    cdir)

    # Added args to file
    cmd = 'echo "WITH_PKGNG=yes" > {0}-make.conf'.format(
            os.path.join(cdir,jname))

    __salt__['cmd.run'](cmd)

    if os.path.isfile(os.path.join(cdir,jname) + '-make.conf'):
        ret['changes'] = 'Created {0}'.format(
                os.path.join(cdir, '{0}-make.conf'.format(janme))
                )
        return ret
    else:
        return 'Looks like file {0} could not be created'.format(
                os.path.join(cdir,jname + '-make.conf')
                )


def parse_config(config_file=None):
    '''
    Returns a dict of poudriere main configuration defintions

    CLI Example::

        salt '*' poudriere.parse_config
    '''
    if config_file is None:
        config_file = _config_file()
    ret = {}
    if _check_config_exists(config_file):
        with open(config_file) as f:
            for line in f.readlines():
                k, y = line.split('=')
                ret[k] = y
        return ret
    else:
        return 'Could not find {0} on file system'.format(config_file)


def version():
    '''
    Return poudriere version

    CLI Example::

        salt '*' poudriere.version
    '''
    cmd = "poudriere version"
    return __salt__['cmd.run'](cmd)


def list_jails():
    '''
    Return a list of current jails managed by poudriere

    CLI Example::

        salt '*' poudriere.list_jails
    '''
    _check_config_exists()
    cmd = 'poudriere jails -l'
    res = __salt__['cmd.run'](cmd)
    return res.split('\n')


def list_ports():
    '''
    Return a list of current port trees managed by poudriere

    CLI Example::

        salt '*' poudriere.list_ports
    '''
    _check_config_exists()
    cmd = 'poudriere ports -l'
    res = __salt__['cmd.run'](cmd).split('\n')
    return res


def create_jail(name, arch, version="9.0-RELEASE"):
    '''
    Creates a new poudriere jail if one does not exist

    *NOTE* creating a new jail will take some time the master is not hanging

    CLI Example::
        salt '*' poudriere.create_jail 90amd64 amd64
    '''
    # Config file must be on system to create a poudriere jail
    _check_config_exists()

    # Check if the jail is there
    if is_jail(name):
        return '{0} already exists'.format(name)

    cmd = 'poudriere jails -c -j {0} -v {1} -a {2}'.format(name,version,arch)
    __salt__['cmd.run'](cmd)

    # Make jail pkgng aware
    make_pkgng_aware(name)

    # Make sure the jail was created
    if is_jail(name):
        return 'Created jail {0}'.format(name)

    return 'Issue creating jail {0}'.format(name)


def delete_jail(name):
    '''
    Deletes poudriere jail with `name`

    CLI Example::

        salt '*' poudriere.delete_jail 90amd64
    '''
    if is_jail(name):
        cmd = 'poudriere jail -d -j {0}'.format(name)
        __salt__['cmd.run'](cmd)

        # Make sure jail is gone
        if is_jail(name):
            return 'Looks like there was an issue deleteing jail \
            {0}'.format(name)
    else:
        # Could not find jail.
        return 'Looks like jail {0} has not been created'.format(name)

    # clean up pkgng make info in config dir
    make_file = os.path.join(_config_dir(), '{0}-make.conf'.format(name))
    if os.path.isfile(make_file):
        try:
            os.remove(make_file)
        except (IOError, OSError):
            return ('Deleted jail "{0}" but was unable to remove jail make '
                    'file').format(name)
        cmd = 'rm -f {0}'.format(make_file)
        __salt__['cmd.run'](cmd)

    return 'Deleted jail {0}'.format(name)


def create_ports_tree():
    '''
    Not working need to run portfetch non interactive
    '''
    _check_config_exists()
    cmd =  'poudriere ports -c'
    ret = __salt__['cmd.run'](cmd)
    return ret


def bulk_build(jail, pkg_file, keep=False):
    '''
    Run bulk build on poudriere server.

    Return number of pkg builds, failures, and errors, on error dump to cli

    CLI Example::

        salt -N buildbox_group poudriere.bulk_build 90amd64 /root/pkg_list

    '''
    # make sure `pkg file` and jail is on file system
    if not os.path.isfile(pkg_file):
        return 'Could not find file {0} on filesystem'.format(pkg_file)
    if not is_jail(jail):
        return 'Could not find jail {0}'.format(jail)

    # Generate command
    if keep:
        cmd = 'poudriere bulk -k -f {0} -j {1}'.format(pkg_file, jail)
    else:
        cmd = 'poudriere bulk -f {0} -j {1}'.format(pkg_file, jail)

    # Bulk build this can take some time, depending on pkg_file ... hours
    res = __salt__['cmd.run'](cmd)
    lines = res.split('\n')
    for line in lines:
        if "packages built" in line:
            return line
    return ('There may have been an issue building packages dumping output: '
            '{0}').format(res)

