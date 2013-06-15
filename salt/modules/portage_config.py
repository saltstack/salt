from os.path import isdir, exists
from os import mkdir, rename, remove, walk
from shutil import copy, rmtree

HAS_PORTAGE = False

# Import third party libs
try:
    import portage
    HAS_PORTAGE = True
except ImportError:
    import sys
    if isdir('/usr/lib/portage/pym'):
        try:
            # In a virtualenv, the portage python path needs to be manually added
            sys.path.insert(0, '/usr/lib/portage/pym')
            import portage
            HAS_PORTAGE = True
        except ImportError:
            pass

def __virtual__():
    '''
    Confirm this module is on a Gentoo based system.
    '''
    return 'portage_config' if (HAS_PORTAGE and __grains__['os'] == 'Gentoo') else False

base_path = '/etc/portage/package.{0}'
supported_confs = ('accept_keywords', 'env', 'license', 'mask', 'properties', 'unmask', 'use')

def _porttree():
    return portage.db[portage.root]['porttree']

def _p_to_cp(p):
    '''
    Convert a package name or a DEPEND atom to category/package format.
    Raises an exception if program name is ambigous.
    '''
    ret = _porttree().dbapi.xmatch("match-all", p)
    if ret:
        return portage.dep_getkey('=' + ret[0])
    return None

def enforce_nice_config():
    '''
    Enforce a nice tree structure for /etc/portage/package.* configuration files.

    CLI Example::

        salt '*' portage_config.enforce_nice_config
    '''
    _convert_all_package_confs_to_dir()
    _order_all_package_confs()

def _convert_all_package_confs_to_dir():
    '''
    Convert all /etc/portage/package.* configuration files to directories.
    '''
    for conf_file in supported_confs:
        _package_conf_file_to_dir(conf_file)

def _order_all_package_confs():
    '''
    Place all entries in /etc/portage/package.* config dirs in the correct file.
    '''
    for conf_file in supported_confs:
        _package_conf_ordering(conf_file)
    _unify_keywords()

def _unify_keywords():
    '''
    Merge /etc/portage/package.keywords and /etc/portage/package.accept_keywords.
    '''
    old_path = base_path.format('keywords')
    new_path = base_path.format('accept_keywords')
    if exists(old_path):
        if isdir(old_path):
            for triplet in walk(old_path):
                for file_name in triplet[2]:
                    file_path = '{0}/{1}'.format(triplet[0], file_name)
                    fh = open(file_path)
                    for line in fh:
                        if line.strip():
                            append_to_package_conf('accept_keywords', string=line)
            rmtree(old_path)
        else:
            fh = open(old_path)
            for line in fh:
                if line.strip():
                    append_to_package_conf('accept_keywords', string=line)
            remove(old_path)

def _package_conf_file_to_dir(file_name):
    '''
    Convert a config file to a config directory.
    '''
    if file_name in supported_confs:
        path = base_path.format(file_name)
        if exists(path):
            if isdir(path):
                return False
            else:
                rename(path, path + '.tmpbak')
                mkdir(path, 0755)
                f = open(path + '.tmpbak')
                for line in f:
                    append_to_package_conf(file_name, string=line.strip())
                f.close()
                remove(path + '.tmpbak')
                return True
        else:
            mkdir(path, 0755)
            return True

def _package_conf_ordering(conf, clean=True, keep_backup=False):
    '''
    Move entries in the correct file.
    '''
    if conf in supported_confs:
        rearrange = []
        path = base_path.format(conf)

        backup_files = []

        for triplet in walk(path):
            for file_name in triplet[2]:
                file_path = '{0}/{1}'.format(triplet[0], file_name)
                cp = triplet[0][len(path)+1:] + '/' + file_name

                copy(file_path, file_path + '.bak')
                backup_files.append(file_path + '.bak')

                if cp[0] == '/' or cp.split('/') > 2:
                    rearrange.extend(list(open(file_path)))
                    remove(file_path)
                else:
                    file_handler = open(file_path, 'r+')
                    new_contents = ''
                    for line in file_handler:
                        try:
                            atom = line.strip().split()[0]
                        except IndexError:
                            new_contents += line
                        else:
                            if atom[0] == '#' or portage.dep_getkey(atom) == cp:
                                new_contents += line
                            else:
                                rearrange.append(line.strip())
                    if len(new_contents) == 0:
                        file_handler.close()
                        remove(file_path)
                    else:
                        file_handler.seek(0)
                        file_handler.truncate(len(new_contents))
                        file_handler.write(new_contents)
                        file_handler.close()

        for line in rearrange:
            append_to_package_conf(conf, string=line)

        if not keep_backup:
            for bfile in backup_files:
                try:
                    remove(bfile)
                except OSError:
                    pass

        if clean:
            for triplet in walk(path):
                if len(triplet[1]) == 0 and len(triplet[2]) == 0 and triplet[0] != path:
                    rmtree(triplet[0])

def _merge_flags(*args):
    '''
    Merges multiple lists of flags removing duplicates and resolving conflicts giving priority to lasts lists.
    '''
    tmp = portage.flatten(args)
    flags = {}
    for flag in tmp:
        if flag[0] == '-':
            flags[flag[1:]] = False
        else:
            flags[flag] = True
    tmp = []
    for k, v in flags.iteritems():
        if v:
            tmp.append(k)
        else:
            tmp.append('-' + k)
    tmp.sort(cmp=lambda x, y: cmp(x.lstrip('-'), y.lstrip('-'))) # just aesthetic, can be commented for a small perfomance boost
    return tmp

def append_to_package_conf(conf, atom='', flags=None, string='', overwrite=False):
    '''
    Append a string or a list of flags for a given package or DEPEND atom to a given configuration file.

    CLI Example::

        salt '*' portage_config.append_to_package_conf use string="app-admin/salt ldap -libvirt"
        salt '*' portage_config.append_to_package_conf use atom="> = app-admin/salt-0.14.1" flags="['ldap', '-libvirt']"
    '''
    if flags is None:
        flags = []
    if conf in supported_confs:
        if not string:
            if atom.find('/') == -1:
                atom = _p_to_cp(atom)
                if not atom:
                    return
            string = '{0} {1}'.format(atom, ' '.join(flags))
            new_flags = flags
        else:
            atom = string.strip().split()[0]
            new_flags = portage.dep.strip_empty(string.strip().split(' '))[1:]
            if atom.find('/') == -1:
                atom = _p_to_cp(atom)
                string = '{0} {1}'.format(atom, ' '.join(new_flags))
                if not atom:
                    return

        to_delete_if_empty = []
        if '-~ARCH' in new_flags:
            new_flags.remove('-~ARCH')
            to_delete_if_empty.append(atom)

        if '~ARCH' in new_flags:
            new_flags.remove('~ARCH')
            append_to_package_conf(conf, string=atom, overwrite=overwrite)
            if not new_flags:
                return

        new_flags.sort(cmp=lambda x, y: cmp(x.lstrip('-'), y.lstrip('-'))) # just aesthetic, can be commented for a small perfomance boost

        package_file = _p_to_cp(atom)
        if not package_file:
            return

        psplit = package_file.split('/')
        if len(psplit) == 2:
            pdir = base_path.format(conf) + '/' + psplit[0]
            if not exists(pdir):
                mkdir(pdir, 0755)

        complete_file_path = base_path.format(conf) + '/' + package_file

        try:
            copy(complete_file_path, complete_file_path + '.bak')
        except IOError:
            pass

        try:
            file_handler = open(complete_file_path, 'r+')
        except IOError:
            file_handler = open(complete_file_path, 'w+')

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
                    old_flags = portage.dep.strip_empty(l_strip.split(' '))[1:]
                    if conf == 'accept_keywords' and not old_flags:
                        new_contents += l
                        if not new_flags:
                            added = True
                            break
                        continue
                    merged_flags = _merge_flags(new_flags, old_flags)
                    if merged_flags:
                        new_contents += '{0} {1}\n'.format(atom, ' '.join(merged_flags))
                    else:
                        new_contents += '{0}\n'.format(atom)
                    added = True
        if not added:
            new_contents += string.strip() + '\n'
        file_handler.seek(0)
        file_handler.truncate(len(new_contents))
        file_handler.write(new_contents)
        file_handler.close()
        try:
            rmtree(complete_file_path + '.bak')
        except OSError:
            pass

def append_use_flags(atom, uses=None, overwrite=False):
    '''
    Append a list of use flags for a given package or DEPEND atom

    CLI Example::

        salt '*' portage_config.append_use_flags "app-admin/salt[ldap, -libvirt]"
        salt '*' portage_config.append_use_flags "> = app-admin/salt-0.14.1" "['ldap', '-libvirt']"
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
    Warning: This only works if the configuration files tree is in the correct format (the one enforced by enforce_nice_config)

    CLI Example::

        salt '*' portage_config.get_flags_from_package_conf license salt
    '''
    if conf in supported_confs:
        package_file = '{0}/{1}'.format(base_path.format(conf), _p_to_cp(atom))
        if atom.find('/') == -1:
            atom = _p_to_cp(atom)
        match_list = set(_porttree().dbapi.xmatch("match-all", atom))
        flags = []
        try:
            file_handler = open(package_file)
        except IOError:
            return []
        else:
            for line in file_handler:
                line = line.strip()
                line_package = line.split()[0]
                line_list = _porttree().dbapi.xmatch("match-all", line_package)
                if match_list.issubset(line_list):
                    f_tmp = portage.dep.strip_empty(line.strip().split()[1:])
                    if f_tmp:
                        flags.extend(f_tmp)
                    else:
                        flags.append('~ARCH')
            return _merge_flags(flags)

def has_flag(conf, atom, flag):
    '''
    Verify if the given package or DEPEND atom has the given flag.
    Warning: This only works if the configuration files tree is in the correct format (the one enforced by enforce_nice_config)

    CLI Example::

        salt '*' portage_config.has_flag license salt Apache-2.0
    '''
    if flag in get_flags_from_package_conf(conf, atom):
        return True
    return False

def get_missing_flags(conf, atom, flags):
    '''
    Find out which of the given flags are currently not set.
    CLI Example::

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
    Warning: This only works if the configuration files tree is in the correct format (the one enforced by enforce_nice_config)

    CLI Example::

        salt '*' portage_config.has_use salt libvirt
    '''
    return has_flag('use', atom, use)

def is_present(conf, atom):
    '''
    Tell if a given package or DEPEND atom is present in the configuration files tree.
    Warning: This only works if the configuration files tree is in the correct format (the one enforced by enforce_nice_config)

    CLI Example::

        salt '*' portage_config.is_present unmask salt
    '''
    if conf in supported_confs:
        package_file = '{0}/{1}'.format(base_path.format(conf), _p_to_cp(atom))
        match_list = set(_porttree().dbapi.xmatch("match-all", atom))
        flags = []
        try:
            file_handler = open(package_file)
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
