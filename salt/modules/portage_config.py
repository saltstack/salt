# -*- coding: utf-8 -*-
'''
Configure ``portage(5)``
'''

# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import salt libs
import salt.utils

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import portage
    HAS_PORTAGE = True
except ImportError:
    HAS_PORTAGE = False
    import sys
    if os.path.isdir('/usr/lib/portage/pym'):
        try:
            # In a virtualenv, the portage python path needs to be manually
            # added
            sys.path.insert(0, '/usr/lib/portage/pym')
            import portage
            HAS_PORTAGE = True
        except ImportError:
            pass
# pylint: enable=import-error


BASE_PATH = '/etc/portage/package.{0}'
SUPPORTED_CONFS = ('accept_keywords', 'env', 'license', 'mask', 'properties',
                   'unmask', 'use')


def __virtual__():
    '''
    Confirm this module is on a Gentoo based system.
    '''
    if HAS_PORTAGE and __grains__['os'] == 'Gentoo':
        return 'portage_config'
    return False


def _get_portage():
    '''
    portage module must be reloaded or it can't catch the changes
    in portage.* which had been added after when the module was loaded
    '''
    return reload(portage)


def _porttree():
    return portage.db[portage.root]['porttree']


def _p_to_cp(p):
    '''
    Convert a package name or a DEPEND atom to category/package format.
    Raises an exception if program name is ambiguous.
    '''
    ret = _porttree().dbapi.xmatch("match-all", p)
    if ret:
        return portage.cpv_getkey(ret[0])
    return None


def _get_cpv(cp, installed=True):
    '''
    add version to category/package
    @cp - name of package in format category/name
    @installed - boolean value, if False, function returns cpv
    for latest available package
    '''
    if installed:
        return _get_portage().db[portage.root]['vartree'].dep_bestmatch(cp)
    else:
        return _porttree().dep_bestmatch(cp)


def enforce_nice_config():
    '''
    Enforce a nice tree structure for /etc/portage/package.* configuration
    files.

    .. seealso::
       :py:func:`salt.modules.ebuild.ex_mod_init`
         for information on automatically running this when pkg is used.


    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.enforce_nice_config
    '''
    _convert_all_package_confs_to_dir()
    _order_all_package_confs()


def _convert_all_package_confs_to_dir():
    '''
    Convert all /etc/portage/package.* configuration files to directories.
    '''
    for conf_file in SUPPORTED_CONFS:
        _package_conf_file_to_dir(conf_file)


def _order_all_package_confs():
    '''
    Place all entries in /etc/portage/package.* config dirs in the correct
    file.
    '''
    for conf_file in SUPPORTED_CONFS:
        _package_conf_ordering(conf_file)
    _unify_keywords()


def _unify_keywords():
    '''
    Merge /etc/portage/package.keywords and
    /etc/portage/package.accept_keywords.
    '''
    old_path = BASE_PATH.format('keywords')
    if os.path.exists(old_path):
        if os.path.isdir(old_path):
            for triplet in os.walk(old_path):
                for file_name in triplet[2]:
                    file_path = '{0}/{1}'.format(triplet[0], file_name)
                    with salt.utils.fopen(file_path) as fh_:
                        for line in fh_:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                append_to_package_conf(
                                    'accept_keywords', string=line)
            shutil.rmtree(old_path)
        else:
            with salt.utils.fopen(old_path) as fh_:
                for line in fh_:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        append_to_package_conf('accept_keywords', string=line)
            os.remove(old_path)


def _package_conf_file_to_dir(file_name):
    '''
    Convert a config file to a config directory.
    '''
    if file_name in SUPPORTED_CONFS:
        path = BASE_PATH.format(file_name)
        if os.path.exists(path):
            if os.path.isdir(path):
                return False
            else:
                os.rename(path, path + '.tmpbak')
                os.mkdir(path, 0o755)
                with salt.utils.fopen(path + '.tmpbak') as fh_:
                    for line in fh_:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            append_to_package_conf(file_name, string=line)
                os.remove(path + '.tmpbak')
                return True
        else:
            os.mkdir(path, 0o755)
            return True


def _package_conf_ordering(conf, clean=True, keep_backup=False):
    '''
    Move entries in the correct file.
    '''
    if conf in SUPPORTED_CONFS:
        rearrange = []
        path = BASE_PATH.format(conf)

        backup_files = []

        for triplet in os.walk(path):
            for file_name in triplet[2]:
                file_path = '{0}/{1}'.format(triplet[0], file_name)
                cp = triplet[0][len(path) + 1:] + '/' + file_name

                shutil.copy(file_path, file_path + '.bak')
                backup_files.append(file_path + '.bak')

                if cp[0] == '/' or cp.split('/') > 2:
                    rearrange.extend(list(salt.utils.fopen(file_path)))
                    os.remove(file_path)
                else:
                    new_contents = ''
                    with salt.utils.fopen(file_path, 'r+') as file_handler:
                        for line in file_handler:
                            try:
                                atom = line.strip().split()[0]
                            except IndexError:
                                new_contents += line
                            else:
                                if atom[0] == '#' or \
                                        portage.dep_getkey(atom) == cp:
                                    new_contents += line
                                else:
                                    rearrange.append(line.strip())
                        if len(new_contents) != 0:
                            file_handler.seek(0)
                            file_handler.truncate(len(new_contents))
                            file_handler.write(new_contents)

                    if len(new_contents) == 0:
                        os.remove(file_path)

        for line in rearrange:
            append_to_package_conf(conf, string=line)

        if not keep_backup:
            for bfile in backup_files:
                try:
                    os.remove(bfile)
                except OSError:
                    pass

        if clean:
            for triplet in os.walk(path):
                if len(triplet[1]) == 0 and len(triplet[2]) == 0 and \
                        triplet[0] != path:
                    shutil.rmtree(triplet[0])


def _check_accept_keywords(approved, flag):
    '''check compatibility of accept_keywords'''
    if flag in approved:
        return False
    elif (flag.startswith('~') and flag[1:] in approved) \
            or ('~'+flag in approved):
        return False
    else:
        return True


def _merge_flags(new_flags, old_flags=None, conf='any'):
    '''
    Merges multiple lists of flags removing duplicates and resolving conflicts
    giving priority to lasts lists.
    '''
    if not old_flags:
        old_flags = []
    args = [old_flags, new_flags]
    if conf == 'accept_keywords':
        tmp = new_flags + \
            [i for i in old_flags if _check_accept_keywords(new_flags, i)]
    else:
        tmp = portage.flatten(args)
    flags = {}
    for flag in tmp:
        if flag[0] == '-':
            flags[flag[1:]] = False
        else:
            flags[flag] = True
    tmp = []
    for key, val in six.iteritems(flags):
        if val:
            tmp.append(key)
        else:
            tmp.append('-' + key)

    # Next sort is just aesthetic, can be commented for a small performance
    # boost
    tmp.sort(cmp=lambda x, y: cmp(x.lstrip('-'), y.lstrip('-')))
    return tmp


def append_to_package_conf(conf, atom='', flags=None, string='', overwrite=False):
    '''
    Append a string or a list of flags for a given package or DEPEND atom to a
    given configuration file.

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.append_to_package_conf use string="app-admin/salt ldap -libvirt"
        salt '*' portage_config.append_to_package_conf use atom="> = app-admin/salt-0.14.1" flags="['ldap', '-libvirt']"
    '''
    if flags is None:
        flags = []
    if conf in SUPPORTED_CONFS:
        if not string:
            if '/' not in atom:
                atom = _p_to_cp(atom)
                if not atom:
                    return
            string = '{0} {1}'.format(atom, ' '.join(flags))
            new_flags = list(flags)
        else:
            atom = string.strip().split()[0]
            new_flags = [flag for flag in string.strip().split(' ') if flag][1:]
            if '/' not in atom:
                atom = _p_to_cp(atom)
                string = '{0} {1}'.format(atom, ' '.join(new_flags))
                if not atom:
                    return

        to_delete_if_empty = []
        if conf == 'accept_keywords':
            if '-~ARCH' in new_flags:
                new_flags.remove('-~ARCH')
                to_delete_if_empty.append(atom)

            if '~ARCH' in new_flags:
                new_flags.remove('~ARCH')
                append_to_package_conf(conf, string=atom, overwrite=overwrite)
                if not new_flags:
                    return

        # Next sort is just aesthetic, can be commented for a small performance
        # boost
        new_flags.sort(cmp=lambda x, y: cmp(x.lstrip('-'), y.lstrip('-')))

        package_file = _p_to_cp(atom)
        if not package_file:
            return

        psplit = package_file.split('/')
        if len(psplit) == 2:
            pdir = BASE_PATH.format(conf) + '/' + psplit[0]
            if not os.path.exists(pdir):
                os.mkdir(pdir, 0o755)

        complete_file_path = BASE_PATH.format(conf) + '/' + package_file

        try:
            shutil.copy(complete_file_path, complete_file_path + '.bak')
        except IOError:
            pass

        try:
            file_handler = salt.utils.fopen(complete_file_path, 'r+')
        except IOError:
            file_handler = salt.utils.fopen(complete_file_path, 'w+')

        new_contents = ''
        added = False

        for l in file_handler:
            l_strip = l.strip()
            if l_strip == '':
                new_contents += '\n'
            elif l_strip[0] == '#':
                new_contents += l
            elif l_strip.split()[0] == atom:
                if l_strip in to_delete_if_empty:
                    continue
                if overwrite:
                    new_contents += string.strip() + '\n'
                    added = True
                else:
                    old_flags = [flag for flag in l_strip.split(' ') if flag][1:]
                    if conf == 'accept_keywords':
                        if not old_flags:
                            new_contents += l
                            if not new_flags:
                                added = True
                            continue
                        elif not new_flags:
                            continue
                    merged_flags = _merge_flags(new_flags, old_flags, conf)
                    if merged_flags:
                        new_contents += '{0} {1}\n'.format(
                            atom, ' '.join(merged_flags))
                    else:
                        new_contents += '{0}\n'.format(atom)
                    added = True
            else:
                new_contents += l
        if not added:
            new_contents += string.strip() + '\n'
        file_handler.seek(0)
        file_handler.truncate(len(new_contents))
        file_handler.write(new_contents)
        file_handler.close()
        try:
            os.remove(complete_file_path + '.bak')
        except OSError:
            pass


def append_use_flags(atom, uses=None, overwrite=False):
    '''
    Append a list of use flags for a given package or DEPEND atom

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.append_use_flags "app-admin/salt[ldap, -libvirt]"
        salt '*' portage_config.append_use_flags ">=app-admin/salt-0.14.1" "['ldap', '-libvirt']"
    '''
    if not uses:
        uses = portage.dep.dep_getusedeps(atom)
    if len(uses) == 0:
        return
    atom = atom[:atom.rfind('[')]
    append_to_package_conf('use', atom=atom, flags=uses, overwrite=overwrite)


def get_flags_from_package_conf(conf, atom):
    '''
    Get flags for a given package or DEPEND atom.
    Warning: This only works if the configuration files tree is in the correct
    format (the one enforced by enforce_nice_config)

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.get_flags_from_package_conf license salt
    '''
    if conf in SUPPORTED_CONFS:
        package_file = '{0}/{1}'.format(BASE_PATH.format(conf), _p_to_cp(atom))
        if '/' not in atom:
            atom = _p_to_cp(atom)
        try:
            match_list = set(_porttree().dbapi.xmatch("match-all", atom))
        except AttributeError:
            return []
        flags = []
        try:
            file_handler = salt.utils.fopen(package_file)
        except IOError:
            return []
        else:
            for line in file_handler:
                line = line.strip()
                line_package = line.split()[0]
                line_list = _porttree().dbapi.xmatch("match-all", line_package)
                if match_list.issubset(line_list):
                    f_tmp = [flag for flag in line.strip().split(' ') if flag][1:]
                    if f_tmp:
                        flags.extend(f_tmp)
                    else:
                        flags.append('~ARCH')
            return _merge_flags(flags)


def has_flag(conf, atom, flag):
    '''
    Verify if the given package or DEPEND atom has the given flag.
    Warning: This only works if the configuration files tree is in the correct
    format (the one enforced by enforce_nice_config)

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.has_flag license salt Apache-2.0
    '''
    if flag in get_flags_from_package_conf(conf, atom):
        return True
    return False


def get_missing_flags(conf, atom, flags):
    '''
    Find out which of the given flags are currently not set.
    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.get_missing_flags use salt "['ldap', '-libvirt', 'openssl']"
    '''
    new_flags = []
    for flag in flags:
        if not has_flag(conf, atom, flag):
            new_flags.append(flag)
    return new_flags


def has_use(atom, use):
    '''
    Verify if the given package or DEPEND atom has the given use flag.
    Warning: This only works if the configuration files tree is in the correct
    format (the one enforced by enforce_nice_config)

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.has_use salt libvirt
    '''
    return has_flag('use', atom, use)


def is_present(conf, atom):
    '''
    Tell if a given package or DEPEND atom is present in the configuration
    files tree.
    Warning: This only works if the configuration files tree is in the correct
    format (the one enforced by enforce_nice_config)

    CLI Example:

    .. code-block:: bash

        salt '*' portage_config.is_present unmask salt
    '''
    if conf in SUPPORTED_CONFS:
        package_file = '{0}/{1}'.format(BASE_PATH.format(conf), _p_to_cp(atom))
        match_list = set(_porttree().dbapi.xmatch("match-all", atom))
        try:
            file_handler = salt.utils.fopen(package_file)
        except IOError:
            return False
        else:
            for line in file_handler:
                line = line.strip()
                line_package = line.split()[0]
                line_list = _porttree().dbapi.xmatch("match-all", line_package)
                if match_list.issubset(line_list):
                    return True
            return False


def get_iuse(cp):
    '''
    .. versionadded:: 2015.8.0

    Gets the current IUSE flags from the tree.

    @type: cpv: string
    @param cpv: cat/pkg
    @rtype list
    @returns [] or the list of IUSE flags
    '''
    cpv = _get_cpv(cp)
    try:
        # aux_get might return dupes, so run them through set() to remove them
        dirty_flags = _porttree().dbapi.aux_get(cpv, ["IUSE"])[0].split()
        return list(set(dirty_flags))
    except Exception as e:
        return []


def get_installed_use(cp, use="USE"):
    '''
    .. versionadded:: 2015.8.0

    Gets the installed USE flags from the VARDB.

    @type: cp: string
    @param cp: cat/pkg
    @type use: string
    @param use: 1 of ["USE", "PKGUSE"]
    @rtype list
    @returns [] or the list of IUSE flags
    '''
    portage = _get_portage()
    cpv = _get_cpv(cp)
    return portage.db[portage.root]["vartree"].dbapi.aux_get(cpv, [use])[0].split()


def filter_flags(use, use_expand_hidden, usemasked, useforced):
    '''
    .. versionadded:: 2015.8.0

    Filter function to remove hidden or otherwise not normally
    visible USE flags from a list.

    @type use: list
    @param use: the USE flag list to be filtered.
    @type use_expand_hidden: list
    @param  use_expand_hidden: list of flags hidden.
    @type usemasked: list
    @param usemasked: list of masked USE flags.
    @type useforced: list
    @param useforced: the forced USE flags.
    @rtype: list
    @return the filtered USE flags.
    '''
    portage = _get_portage()
    # clean out some environment flags, since they will most probably
    # be confusing for the user
    for f in use_expand_hidden:
        f = f.lower()+ "_"
        for x in use:
            if f in x:
                use.remove(x)
    # clean out any arch's
    archlist = portage.settings["PORTAGE_ARCHLIST"].split()
    for a in use[:]:
        if a in archlist:
            use.remove(a)
    # dbl check if any from usemasked  or useforced are still there
    masked = usemasked + useforced
    for a in use[:]:
        if a in masked:
            use.remove(a)
    return use


def get_all_cpv_use(cp):
    '''
    .. versionadded:: 2015.8.0

    Uses portage to determine final USE flags and settings for an emerge.

    @type cp: string
    @param cp: eg cat/pkg
    @rtype: lists
    @return  use, use_expand_hidden, usemask, useforce
    '''
    cpv = _get_cpv(cp)
    portage = _get_portage()
    use = None
    _porttree().dbapi.settings.unlock()
    try:
        _porttree().dbapi.settings.setcpv(cpv, mydb=portage.portdb)
        use = portage.settings['PORTAGE_USE'].split()
        use_expand_hidden = portage.settings["USE_EXPAND_HIDDEN"].split()
        usemask = list(_porttree().dbapi.settings.usemask)
        useforce = list(_porttree().dbapi.settings.useforce)
    except KeyError:
        _porttree().dbapi.settings.reset()
        _porttree().dbapi.settings.lock()
        return [], [], [], []
    # reset cpv filter
    _porttree().dbapi.settings.reset()
    _porttree().dbapi.settings.lock()
    return use, use_expand_hidden, usemask, useforce


def get_cleared_flags(cp):
    '''
    .. versionadded:: 2015.8.0

    Uses portage for compare use flags which is used for installing package
    and use flags which now exist int /etc/portage/package.use/

    @type cp: string
    @param cp: eg cat/pkg
    @rtype: tuple
    @rparam: tuple with two lists - list of used flags and
    list of flags which will be used
    '''
    cpv = _get_cpv(cp)
    final_use, use_expand_hidden, usemasked, useforced = get_all_cpv_use(cpv)
    inst_flags = filter_flags(get_installed_use(cpv), use_expand_hidden,
                                usemasked, useforced)
    final_flags = filter_flags(final_use, use_expand_hidden,
                                usemasked, useforced)
    return inst_flags, final_flags


def is_changed_uses(cp):
    '''
    .. versionadded:: 2015.8.0

    Uses portage for determine if the use flags of installed package
    is compatible with use flags in portage configs.

    @type cp: string
    @param cp: eg cat/pkg
    '''
    cpv = _get_cpv(cp)
    i_flags, conf_flags = get_cleared_flags(cpv)
    for i in i_flags:
        try:
            conf_flags.remove(i)
        except ValueError:
            return True
    return True if conf_flags else False
