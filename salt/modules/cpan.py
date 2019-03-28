# -*- coding: utf-8 -*-
'''
Manage Perl modules using CPAN

.. versionadded:: 2015.5.0
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
from ast import literal_eval
import os
import os.path
import logging

# Import salt libs
import salt.utils.files
import salt.utils.path

log = logging.getLogger(__name__)

# Don't shadow built-ins.
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only work on supported POSIX-like systems
    '''
    if salt.utils.path.which('cpan'):
        return True
    return (False, 'Unable to locate cpan. Make sure it is installed and in the PATH.')


def _get_cpan_bin(bin_env):
    """
    Locate the cpan binary, with 'bin_env' as the executable itself,
    or from searching conventional filesystem locations
    """
    if not bin_env:
        log.debug('cpan: Using cpan from system')
        return [salt.utils.path.which('cpan')]

    if os.access(bin_env, os.X_OK) and os.path.isfile(bin_env):
        return os.path.normpath(bin_env)
    else:
        return salt.utils.path.which(bin_env)


def version(bin_env=None):
    '''
    Returns the version of cpan.  sed ``bin_env`` to specify the path to
    a specific virtualenv and get the cpan version in that virtualenv.

    If unable to detect the cpan version, returns ``None``.

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.version
    '''
    return show("CPAN").get("installed version", None)


def install(module=None,
            bin_env=None,
            force=None,
            mirror=None,
            notest=None,
            ):
    '''
    Install a Perl module from CPAN

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.install Template::Alloy
    '''
    old_info = show(module)

    cmd = _get_cpan_bin(bin_env)

    if force:
        cmd.append('-f')

    if mirror:
        # cpan accepts a single comma-separated string, but we prefer
        # a list from state files,  Allow both.
        cmd.extend(['-M', mirror if isinstance(mirror, str) else ','.join(mirror)])

    if notest:
        cmd.append('-T')

    if module:
        cmd.append('-i')
        cmd.append(module)
    else:
        # Funky things happen if we don't have a module to install
        return dict()

    #'cpan -i {0}'.format(module)
    ret = __salt__['cmd.run_all'](cmd)

    if ret.get("retcode", None):
        return {'error': ret['stderr']}

    new_info = show(module)

    if 'error' in new_info:
        return {
            'error': new_info['error']
        }

    if not new_info:
        return {
            'error': 'Could not install module {}'.format(module)
        }

    for k in old_info.copy().keys():
        if old_info.get(k) == new_info[k]:
            old_info.pop(k)
            new_info.pop(k)

    if old_info or new_info:
        return {'old': old_info, 'new': new_info}
    else:
        return dict()



def remove(module, details=False):
    '''
    Attempt to remove a Perl module that was installed from CPAN. Because the
    ``cpan`` command doesn't actually support "uninstall"-like functionality,
    this function will attempt to do what it can, with what it has from CPAN.

    Until this function is declared stable, USE AT YOUR OWN RISK!

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.remove Old::Package
    '''
    info = show(module)
    if 'error' in info:
        return {
            'error': info['error']
        }

    version = info.get('installed version', None)
    if 'not installed' in version or version is None:
        log.debug("Module '{}' already removed, no changes made".format(module))
        return dict()

    mod_pathfile = module.replace('::', '/') + '.pm'
    ins_path = info['installed file'].replace(mod_pathfile, '')

    rm_details = {}
    if 'cpan build dirs' in info:
        log.warning('No CPAN data available to use for uninstalling')

    files = []
    for build_dir in info['cpan build dirs']:
        try:
            contents = os.listdir(build_dir)
        except Exception as e:
            log.warning(e)
            continue
        if 'MANIFEST' not in contents:
            continue
        mfile = os.path.join(build_dir, 'MANIFEST')
        with salt.utils.files.fopen(mfile, 'r') as fh_:
            for line in fh_.readlines():
                line = salt.utils.stringutils.to_unicode(line)
                if line.startswith('lib/'):
                    files.append(line.replace('lib/', ins_path).strip())

    for file_ in files:
        if file_ in rm_details:
            continue
        log.trace('Removing %s', file_)
        if __salt__['file.remove'](file_):
            rm_details[file_] = 'removed'
        else:
            rm_details[file_] = 'unable to remove'

    new_info = show(module)

    ret = dict()
    if details:
        ret['details'] = rm_details

    for k in info.copy().keys():
        if info.get(k) == new_info[k]:
            info.pop(k)
            new_info.pop(k)

    if info or new_info:
        ret['old'] = info
        ret['new'] = new_info

    return ret


def list_():
    '''
    List installed Perl modules, and the version installed

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.list
    '''
    ret = {}
    cmd = [_get_cpan_bin('cpan'), '-l']
    out = __salt__['cmd.run'](cmd)
    for line in out.splitlines():
        comps = line.split()
        # If there is text not related to the list we want, it will have
        # more than 2 words
        if len(comps) == 2:
            ret[comps[0]] = comps[1]
    return ret


def show(module):
    '''
    Show information about a specific Perl module

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.show Template::Alloy
    '''
    ret = {'name': module}

    # This section parses out details from CPAN, if possible
    cmd = [_get_cpan_bin('cpan')]
    cmd.extend(['-D', module])
    out = __salt__['cmd.run'](cmd)
    parse = False
    info = []
    for line in out.splitlines():
        # Once the dashes appear we are looking at the module info
        if line.startswith('-'*20):
            parse = True
            continue
        if not parse:
            continue
        info.append(line)

    if len(info) == 6:
        # If the module is not installed, we'll be short a line
        info.insert(2, '')
    if len(info) < 6:
        # This must not be a real package
        ret['error'] = 'Could not find package {}'.format(module)
        return ret

    ret['description'] = info[0].strip()
    ret['cpan file'] = info[1].strip()
    if info[2].strip():
        ret['installed file'] = info[2].strip()
    else:
        ret['installed file'] = None
    comps = info[3].split(':')
    if len(comps) > 1:
        ret['installed version'] = comps[1].strip()
    if 'installed version' not in ret or not ret['installed version']:
        ret['installed version'] = None
    comps = info[4].split(':')
    comps = comps[1].split()
    ret['cpan version'] = comps[0].strip()
    ret['author name'] = info[5].strip()
    ret['author email'] = info[6].strip()

    # Check and see if there are cpan build directories
    cfg = config()
    build_dir = cfg.get('build_dir', None)
    if build_dir is not None:
        ret['cpan build dirs'] = []
        try:
            builds = os.listdir(build_dir)
        except FileNotFoundError as e:
            return {'error': str(e)}
        pfile = module.replace('::', '-')
        for file_ in builds:
            if file_.startswith(pfile):
                ret['cpan build dirs'].append(os.path.join(build_dir, file_))

    return ret


def config():
    '''
    Return a dict of CPAN configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.config
    '''
    cmd = [_get_cpan_bin('cpan'), '-J']
    # Format the output like a python dictionary
    out = __salt__['cmd.run'](cmd).replace('=>', ':').replace("\n", "")
    # Remove everything before '{' and after '}'
    out = out[out.find('{'):out.rfind('}') + 1]
    return literal_eval(out)

