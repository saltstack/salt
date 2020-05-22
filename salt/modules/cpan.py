# -*- coding: utf-8 -*-
'''
Manage Perl modules using CPAN

.. versionadded:: 2015.5.0
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import os.path
# Import python libs
from ast import literal_eval

# Import salt libs
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandNotFoundError

log = logging.getLogger(__name__)

default_env = {
    # Use the default answer for prompted configuration options
    'PERL_MM_USE_DEFAULT': '1'
}

# Don't shadow built-ins.
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    return True


def _get_cpan_bin(bin_env=None):
    '''
    Locate the cpan binary, with 'bin_env' as the executable itself,
    or from searching conventional filesystem locations
    '''
    if not bin_env:
        log.debug('cpan: Using cpan from system')
        return salt.utils.path.which('cpan')
    elif os.access(bin_env, os.X_OK) and os.path.isfile(bin_env):
        # If cpan is not part of the path, check if it exists in bin_env
        return os.path.normpath(bin_env)

    # If none of the above assignments resulted in a path, throw an error
    raise CommandNotFoundError('Make sure `{}` is installed and in the PATH'.format(
                                bin_env if bin_env else 'cpan'))


def version(bin_env=None):
    '''
    Returns the version of cpan.  sed ``bin_env`` to specify the path to
    a specific virtualenv and get the cpan version in that virtualenv.

    If unable to detect the cpan version, returns ``None``.

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.version
    '''
    return show('CPAN', bin_env=bin_env).get('installed version', None)


def install(module,
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
    # Get the state of the package before the install operations
    log.debug('logging works!')
    old_info = show(module, bin_env=bin_env)

    # Initialize the standard return information for this function
    ret = {
        'error': None,
        'old': None,
        'new': None
    }

    # Build command based on function arguments
    cmd = [_get_cpan_bin(bin_env)]

    if force:
        cmd.append('-f')

    if mirror:
        # cpan accepts a single comma-separated string, but we prefer
        # a list from state files,  Allow both.
        cmd.append('-M')
        if isinstance(mirror, list):
            mirror = ','.join(mirror)
        cmd.extend(['-M', mirror])

    if notest:
        cmd.append('-T')

    if module:
        cmd.append('-i')
        cmd.append(module)

    # Run the cpan install command
    cmd_ret = __salt__['cmd.run_all'](cmd, env=default_env)

    # Report an error if the return code was anything but zero
    if cmd_ret.get('retcode', None):
        ret['error'] = cmd_ret['stderr']

    new_info = show(module)

    if not new_info:
        ret['error'] = 'Could not install module {}'.format(module)

    if 'error' in new_info:
        ret['error'] = new_info['error']

    # Remove values that are identical, only report changes
    for k in old_info.copy().keys():
        if old_info.get(k) == new_info.get(k, None):
            old_info.pop(k)
            new_info.pop(k)

    ret['old'] = old_info
    ret['new'] = new_info

    return ret


def remove(module, details=False):
    '''
    Attempt to remove a Perl module that was installed from CPAN. Because the
    ``cpan`` command doesn't actually support 'uninstall'-like functionality,
    this function will attempt to do what it can, with what it has from CPAN.

    Until this function is declared stable, USE AT YOUR OWN RISK!

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.remove Old::Package
    '''
    ret = {
        'error': None,
        'old': None,
        'new': None
    }

    info = show(module)
    ret['error'] = info.get('error', None)

    cpan_version = info.get(' version', None)
    if (cpan_version is None) or ('not installed' in cpan_version):
        log.debug('Module "{}" already removed, no changes made'.format(module))
    else:
        mod_pathfile = module.replace('::', '/') + '.pm'
        ins_path = info['installed file'].replace(mod_pathfile, '')

        rm_details = {}
        if 'cpan build dirs' in info:
            log.warning('No CPAN data available to use for uninstalling')

        files = []
        for build_dir in info['cpan build dirs']:
            # Check if the build directory exists, if not then skip
            if not os.path.isdir(build_dir):
                log.warning(
                    'Could not find CPAN build dir: {}'.format(build_dir))
                continue

            # If the manifest is moving then skip
            contents = os.listdir(build_dir)
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
                log.trace('Removing %s', file_)
                continue
            if __salt__['file.remove'](file_):
                rm_details[file_] = 'removed'
            else:
                rm_details[file_] = 'unable to remove'

        new_info = show(module)

        if details:
            ret['details'] = rm_details

        # Only report changes, remove values that are the same before and after
        for k in info.copy().keys():
            if info.get(k) == new_info[k]:
                info.pop(k)
                new_info.pop(k, None)

        ret['old'] = info
        ret['new'] = new_info

    return ret


def list_(bin_env=None):
    '''
    List installed Perl modules, and the version installed

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.list
    '''
    ret = {}
    cmd = [_get_cpan_bin(bin_env), '-l']
    out = __salt__['cmd.run_all'](cmd, env=default_env).get('stdout', '')
    for line in out.splitlines():
        comps = line.split()
        # If there is text not related to the list we want, it will have
        # more than 2 words
        if len(comps) == 2:
            ret[comps[0]] = comps[1]
    return ret


def show(module, bin_env=None):
    '''
    Show information about a specific Perl module

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.show Template::Alloy
    '''
    ret = {'name': module}

    # This section parses out details from CPAN, if possible
    cmd = [_get_cpan_bin(bin_env)]
    cmd.extend(['-D', module])
    out = __salt__['cmd.run_all'](cmd, env=default_env).get('stdout', '')
    parse = False
    info = []
    for line in out.splitlines():
        # Once the dashes appear we are looking at the module info
        if line.startswith('-' * 20):
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
        ret.update({'error': 'Could not find package {}'.format(module)})
        return ret

    ret['installed version'] = None
    ret['description'] = info[0].strip()
    ret['cpan file'] = info[1].strip()
    if info[2].strip():
        ret['installed file'] = info[2].strip()
    else:
        ret['installed file'] = None
    comps = info[3].split(':')
    if len(comps) > 1:
        ret['installed version'] = comps[1].strip()
    comps = info[4].split(':')
    comps = comps[1].split()
    ret['cpan version'] = comps[0].strip()
    ret['author name'] = info[5].strip()
    ret['author email'] = info[6].strip()

    # Check and see if there are cpan build directories
    cfg = config(bin_env)
    build_dir = cfg.get('build_dir', None)
    if build_dir is not None:
        ret['cpan build dirs'] = []
        builds = []
        if os.path.exists(build_dir):
            builds = os.listdir(build_dir)
        else:
            ret.update({'comment': '\'{}\' is not a path'.format(build_dir)})
        pfile = module.replace('::', '-')
        for file_ in builds:
            if file_.startswith(pfile):
                ret['cpan build dirs'].append(os.path.join(build_dir, file_))
    return ret


def config(bin_env=None):
    '''
    Return a dict of CPAN configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' cpan.config
    '''
    cmd = [_get_cpan_bin(bin_env), '-J']
    out = __salt__['cmd.run_all'](cmd, env=default_env).get('stdout', '')
    # Format the output like a python dictionary
    out = out.replace('=>', ':')
    # Remove all whitespaces
    out = ''.join(out.split())

    # Do not try and parse an empty configuration file
    if not out:
        return dict()

    # The conf file will occasionally return the keyword "undef" on some systems
    out = out.replace(':undef', ':None')
    # Remove everything before '{' and after '}'
    out = out[out.find('{'):out.rfind('}') + 1]
    try:
        return literal_eval(out)
    except Exception as e:
        # Give the full output string to help with debugging
        raise Exception(repr(e) + out)
