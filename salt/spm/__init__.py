# -*- coding: utf-8 -*-
'''
This module provides the point of entry to SPM, the Salt Package Manager

.. versionadded:: 2015.8.0
'''

# Import Python libs
from __future__ import absolute_import, print_function
import os
import yaml
import tarfile
import shutil
import msgpack
import datetime
import hashlib
import logging
import pwd
import grp
import sys

# Import Salt libs
import salt.config
import salt.loader
import salt.utils
import salt.utils.http as http
import salt.syspaths as syspaths
import salt.ext.six as six
from salt.ext.six import string_types
from salt.ext.six.moves import input
from salt.ext.six.moves import zip
from salt.ext.six.moves import filter

# Get logging started
log = logging.getLogger(__name__)


class SPMException(Exception):
    '''
    Base class for SPMClient exceptions
    '''


class SPMInvocationError(SPMException):
    '''
    Wrong number of arguments or other usage error
    '''


class SPMPackageError(SPMException):
    '''
    Problem with package file or package installation
    '''


class SPMDatabaseError(SPMException):
    '''
    SPM database not found, etc
    '''


class SPMOperationCanceled(SPMException):
    '''
    SPM install or uninstall was canceled
    '''


class SPMClient(object):
    '''
    Provide an SPM Client
    '''
    def __init__(self, ui, opts=None):  # pylint: disable=W0231
        self.ui = ui
        if not opts:
            opts = salt.config.spm_config(
                os.path.join(syspaths.CONFIG_DIR, 'spm')
            )
        self.opts = opts
        self.db_prov = self.opts.get('spm_db_provider', 'sqlite3')
        self.files_prov = self.opts.get('spm_files_provider', 'local')
        self._prep_pkgdb()
        self._prep_pkgfiles()
        self._init()

    def _prep_pkgdb(self):
        self.pkgdb = salt.loader.pkgdb(self.opts)

    def _prep_pkgfiles(self):
        self.pkgfiles = salt.loader.pkgfiles(self.opts)

    def _init(self):
        self.db_conn = self._pkgdb_fun('init')
        self.files_conn = self._pkgfiles_fun('init')

    def run(self, args):
        '''
        Run the SPM command
        '''
        command = args[0]
        try:
            if command == 'install':
                self._install(args)
            elif command == 'local':
                self._local(args)
            elif command == 'remove':
                self._remove(args)
            elif command == 'build':
                self._build(args)
            elif command == 'update_repo':
                self._download_repo_metadata(args)
            elif command == 'create_repo':
                self._create_repo(args)
            elif command == 'files':
                self._list_files(args)
            elif command == 'info':
                self._info(args)
            else:
                raise SPMInvocationError('Invalid command \'{0}\''.format(command))
        except SPMException as exc:
            self.ui.error(str(exc))

    def _pkgdb_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgdb, self.db_prov), func)(*args, **kwargs)
        except AttributeError:
            return self.pkgdb['{0}.{1}'.format(self.db_prov, func)](*args, **kwargs)

    def _pkgfiles_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgfiles, self.files_prov), func)(*args, **kwargs)
        except AttributeError:
            return self.pkgfiles['{0}.{1}'.format(self.files_prov, func)](*args, **kwargs)

    def _local(self, args):
        '''
        Process local commands
        '''
        args.pop(0)
        command = args[0]
        if command == 'install':
            self._local_install(args)
        elif command == 'files':
            self._local_list_files(args)
        elif command == 'info':
            self._local_info(args)
        else:
            raise SPMInvocationError('Invalid local command \'{0}\''.format(command))

    def _install(self, args):
        '''
        Install a package from a repo
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package must be specified')

        packages = args[1:]
        file_map = {}
        optional = []
        recommended = []
        to_install = []
        for pkg in packages:
            if pkg.endswith('.spm'):
                if self._pkgfiles_fun('path_exists', pkg):
                    comps = pkg.split('-')
                    comps = '-'.join(comps[:-2]).split('/')
                    pkg_name = comps[-1]

                    formula_tar = tarfile.open(pkg, 'r:bz2')
                    formula_ref = formula_tar.extractfile('{0}/FORMULA'.format(pkg_name))
                    formula_def = yaml.safe_load(formula_ref)

                    file_map[pkg_name] = pkg
                    to_, op_, re_ = self._check_all_deps(
                        pkg_name=pkg_name,
                        pkg_file=pkg,
                        formula_def=formula_def
                    )
                    to_install.extend(to_)
                    optional.extend(op_)
                    recommended.extend(re_)
                else:
                    raise SPMInvocationError('Package file {0} not found'.format(pkg))
            else:
                to_, op_, re_ = self._check_all_deps(pkg_name=pkg)
                to_install.extend(to_)
                optional.extend(op_)
                recommended.extend(re_)

        optional = set(filter(len, optional))
        self.ui.status('The following dependencies are optional:\n\t{0}\n'.format(
            '\n\t'.join(optional)
        ))
        recommended = set(filter(len, recommended))
        self.ui.status('The following dependencies are recommended:\n\t{0}\n'.format(
            '\n\t'.join(recommended)
        ))

        to_install = set(filter(len, to_install))
        msg = 'Installing packages:\n\t{0}\n'.format('\n\t'.join(to_install))
        if not self.opts['assume_yes']:
            self.ui.confirm(msg)

        repo_metadata = self._get_repo_metadata()

        for package in to_install:
            if package in file_map:
                self._install_indv_pkg(package, file_map[package])
            else:
                for repo in repo_metadata:
                    repo_info = repo_metadata[repo]
                    if package in repo_metadata[repo]['packages']:
                        cache_path = '{0}/{1}'.format(
                            self.opts['spm_cache_dir'],
                            repo
                        )
                        # Download the package
                        dl_path = '{0}/{1}'.format(
                            repo_info['info']['url'],
                            repo_info['packages'][package]['filename']
                        )
                        out_file = '{0}/{1}'.format(
                            cache_path,
                            repo_info['packages'][package]['filename']
                        )
                        if not os.path.exists(cache_path):
                            os.makedirs(cache_path)

                        if dl_path.startswith('file://'):
                            dl_path = dl_path.replace('file://', '')
                            shutil.copyfile(dl_path, out_file)
                        else:
                            http.query(dl_path, text_out=out_file)

                        # Kick off the install
                        self._install_indv_pkg(package, out_file)
        return

    def _local_install(self, args, pkg_name=None):
        '''
        Install a package from a file
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package file must be specified')

        self._install(args)

    def _check_all_deps(self, pkg_name=None, pkg_file=None, formula_def=None):
        '''
        Starting with one package, check all packages for dependencies
        '''
        if pkg_file and not os.path.exists(pkg_file):
            raise SPMInvocationError('Package file {0} not found'.format(pkg_file))

        self.repo_metadata = self._get_repo_metadata()
        if not formula_def:
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo]['packages'], dict):
                    continue
                if pkg_name in self.repo_metadata[repo]['packages']:
                    formula_def = self.repo_metadata[repo]['packages'][pkg_name]['info']

        if not formula_def:
            raise SPMInvocationError('Unable to read formula for {0}'.format(pkg_name))

        # Check to see if the package is already installed
        pkg_info = self._pkgdb_fun('info', pkg_name, self.db_conn)
        pkgs_to_install = []
        if pkg_info is None or self.opts['force']:
            pkgs_to_install.append(pkg_name)
        elif pkg_info is not None and not self.opts['force']:
            raise SPMPackageError(
                'Package {0} already installed, not installing again'.format(formula_def['name'])
            )

        optional_install = []
        recommended_install = []
        if 'dependencies' in formula_def or 'optional' in formula_def or 'recommended' in formula_def:
            self.avail_pkgs = {}
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo]['packages'], dict):
                    continue
                for pkg in self.repo_metadata[repo]['packages']:
                    self.avail_pkgs[pkg] = repo

            needs, unavail, optional, recommended = self._resolve_deps(formula_def)

            if len(unavail) > 0:
                raise SPMPackageError(
                    'Cannot install {0}, the following dependencies are needed:\n\n{1}'.format(
                        formula_def['name'], '\n'.join(unavail))
                )

            if optional:
                optional_install.extend(optional)
                for dep_pkg in optional:
                    pkg_info = self._pkgdb_fun('info', formula_def['name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = '{0} [Installed]'.format(dep_pkg)
                    optional_install.append(msg)

            if recommended:
                recommended_install.extend(recommended)
                for dep_pkg in recommended:
                    pkg_info = self._pkgdb_fun('info', formula_def['name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = '{0} [Installed]'.format(dep_pkg)
                    recommended_install.append(msg)

            if needs:
                pkgs_to_install.extend(needs)
                for dep_pkg in needs:
                    pkg_info = self._pkgdb_fun('info', formula_def['name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = '{0} [Installed]'.format(dep_pkg)

        return pkgs_to_install, optional_install, recommended_install

    def _install_indv_pkg(self, pkg_name, pkg_file):
        '''
        Install one individual package
        '''
        self.ui.status('... installing {0}'.format(pkg_name))
        formula_tar = tarfile.open(pkg_file, 'r:bz2')
        formula_ref = formula_tar.extractfile('{0}/FORMULA'.format(pkg_name))
        formula_def = yaml.safe_load(formula_ref)

        for field in ('version', 'release', 'summary', 'description'):
            if field not in formula_def:
                raise SPMPackageError('Invalid package: the {0} was not found'.format(field))

        pkg_files = formula_tar.getmembers()
        # First pass: check for files that already exist
        existing_files = self._pkgfiles_fun('check_existing', pkg_name, pkg_files, formula_def)

        if existing_files and not self.opts['force']:
            raise SPMPackageError('Not installing {0} due to existing files:\n\n{1}'.format(
                pkg_name, '\n'.join(existing_files))
            )

        # We've decided to install
        self._pkgdb_fun('register_pkg', pkg_name, formula_def, self.db_conn)

        # No defaults for this in config.py; default to the current running
        # user and group
        uid = self.opts.get('spm_uid', os.getuid())
        gid = self.opts.get('spm_gid', os.getgid())
        uname = pwd.getpwuid(uid)[0]
        gname = grp.getgrgid(gid)[0]

        # Second pass: install the files
        for member in pkg_files:
            member.uid = uid
            member.gid = gid
            member.uname = uname
            member.gname = gname

            out_path = self._pkgfiles_fun('install_file',
                                          pkg_name,
                                          formula_tar,
                                          member,
                                          formula_def,
                                          self.files_conn)
            if out_path is not False:
                if member.isdir():
                    digest = ''
                else:
                    self._verbose('Installing file {0} to {1}'.format(member.name, out_path), log.trace)
                    file_hash = hashlib.sha1()
                    digest = self._pkgfiles_fun('hash_file',
                                                os.path.join(out_path, member.name),
                                                file_hash,
                                                self.files_conn)
                self._pkgdb_fun('register_file',
                                pkg_name,
                                member,
                                out_path,
                                digest,
                                self.db_conn)

        formula_tar.close()

    def _resolve_deps(self, formula_def):
        '''
        Return a list of packages which need to be installed, to resolve all
        dependencies
        '''
        pkg_info = self.pkgdb['{0}.info'.format(self.db_prov)](formula_def['name'])
        if not isinstance(pkg_info, dict):
            pkg_info = {}

        can_has = {}
        cant_has = []
        for dep in formula_def.get('dependencies', '').split(','):
            dep = dep.strip()
            if not dep:
                continue
            if self.pkgdb['{0}.info'.format(self.db_prov)](dep):
                continue

            if dep in self.avail_pkgs:
                can_has[dep] = self.avail_pkgs[dep]
            else:
                cant_has.append(dep)

        optional = formula_def.get('optional', '').split(',')
        recommended = formula_def.get('recommended', '').split(',')

        inspected = []
        to_inspect = can_has.copy()
        while len(to_inspect) > 0:
            dep = next(six.iterkeys(to_inspect))
            del to_inspect[dep]

            # Don't try to resolve the same package more than once
            if dep in inspected:
                continue
            inspected.append(dep)

            repo_contents = self.repo_metadata.get(can_has[dep], {})
            repo_packages = repo_contents.get('packages', {})
            dep_formula = repo_packages.get(dep, {}).get('info', {})

            also_can, also_cant, opt_dep, rec_dep = self._resolve_deps(dep_formula)
            can_has.update(also_can)
            cant_has = sorted(set(cant_has + also_cant))
            optional = sorted(set(optional + opt_dep))
            recommended = sorted(set(recommended + rec_dep))

        return can_has, cant_has, optional, recommended

    def _traverse_repos(self, callback, repo_name=None):
        '''
        Traverse through all repo files and apply the functionality provided in
        the callback to them
        '''
        repo_files = []
        if os.path.exists(self.opts['spm_repos_config']):
            repo_files.append(self.opts['spm_repos_config'])

        for (dirpath, dirnames, filenames) in os.walk('{0}.d'.format(self.opts['spm_repos_config'])):
            for repo_file in filenames:
                if not repo_file.endswith('.repo'):
                    continue
                repo_files.append(repo_file)

        if not os.path.exists(self.opts['spm_cache_dir']):
            os.makedirs(self.opts['spm_cache_dir'])

        for repo_file in repo_files:
            repo_path = '{0}.d/{1}'.format(self.opts['spm_repos_config'], repo_file)
            with salt.utils.fopen(repo_path) as rph:
                repo_data = yaml.safe_load(rph)
                for repo in repo_data:
                    if repo_data[repo].get('enabled', True) is False:
                        continue
                    if repo_name is not None and repo != repo_name:
                        continue
                    callback(repo, repo_data[repo])

    def _download_repo_metadata(self, args):
        '''
        Connect to all repos and download metadata
        '''
        def _update_metadata(repo, repo_info):
            dl_path = '{0}/SPM-METADATA'.format(repo_info['url'])
            if dl_path.startswith('file://'):
                dl_path = dl_path.replace('file://', '')
                with salt.utils.fopen(dl_path, 'r') as rpm:
                    metadata = yaml.safe_load(rpm)
            else:
                response = http.query(dl_path, text=True)
                metadata = response.get('text', {})
            cache_path = '{0}/{1}.p'.format(
                self.opts['spm_cache_dir'],
                repo
            )

            with salt.utils.fopen(cache_path, 'w') as cph:
                msgpack.dump(metadata, cph)

        repo_name = args[1] if len(args) > 1 else None
        self._traverse_repos(_update_metadata, repo_name)

    def _get_repo_metadata(self):
        '''
        Return cached repo metadata
        '''
        metadata = {}

        if not os.path.exists(self.opts['spm_cache_dir']):
            os.makedirs(self.opts['spm_cache_dir'])

        def _read_metadata(repo, repo_info):
            cache_path = '{0}/{1}.p'.format(
                self.opts['spm_cache_dir'],
                repo
            )

            if not os.path.exists(cache_path):
                raise SPMPackageError('SPM cache {0} not found'.format(cache_path))

            with salt.utils.fopen(cache_path, 'r') as cph:
                metadata[repo] = {
                    'info': repo_info,
                    'packages': msgpack.load(cph),
                }

        self._traverse_repos(_read_metadata)
        return metadata

    def _create_repo(self, args):
        '''
        Scan a directory and create an SPM-METADATA file which describes
        all of the SPM files in that directory.
        '''
        if len(args) < 2:
            raise SPMInvocationError('A path to a directory must be specified')

        if args[1] == '.':
            repo_path = os.environ['PWD']
        else:
            repo_path = args[1]

        repo_metadata = {}
        for (dirpath, dirnames, filenames) in os.walk(repo_path):
            for spm_file in filenames:
                if not spm_file.endswith('.spm'):
                    continue
                spm_path = '{0}/{1}'.format(repo_path, spm_file)
                if not tarfile.is_tarfile(spm_path):
                    continue
                comps = spm_file.split('-')
                spm_name = '-'.join(comps[:-2])
                spm_fh = tarfile.open(spm_path, 'r:bz2')
                formula_handle = spm_fh.extractfile('{0}/FORMULA'.format(spm_name))
                formula_conf = yaml.safe_load(formula_handle.read())
                repo_metadata[spm_name] = {
                    'info': formula_conf.copy(),
                }
                repo_metadata[spm_name]['filename'] = spm_file

        metadata_filename = '{0}/SPM-METADATA'.format(repo_path)
        with salt.utils.fopen(metadata_filename, 'w') as mfh:
            yaml.dump(repo_metadata, mfh, indent=4, canonical=False, default_flow_style=False)

        log.debug('Wrote {0}'.format(metadata_filename))

    def _remove(self, args):
        '''
        Remove a package
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package must be specified')

        packages = args[1:]
        msg = 'Removing packages:\n\t{0}'.format('\n\t'.join(packages))

        if not self.opts['assume_yes']:
            self.ui.confirm(msg)

        for package in packages:
            self.ui.status('... removing {0}'.format(package))

            if not self._pkgdb_fun('db_exists', self.opts['spm_db']):
                raise SPMDatabaseError('No database at {0}, cannot remove {1}'.format(self.opts['spm_db'], package))

            # Look at local repo index
            pkg_info = self._pkgdb_fun('info', package, self.db_conn)
            if pkg_info is None:
                raise SPMInvocationError('Package {0} not installed'.format(package))

            # Find files that have not changed and remove them
            files = self._pkgdb_fun('list_files', package, self.db_conn)
            dirs = []
            for filerow in files:
                if self._pkgfiles_fun('path_isdir', filerow[0]):
                    dirs.append(filerow[0])
                    continue
                file_hash = hashlib.sha1()
                digest = self._pkgfiles_fun('hash_file', filerow[0], file_hash, self.files_conn)
                if filerow[1] == digest:
                    self._verbose('Removing file {0}'.format(filerow[0]), log.trace)
                    self._pkgfiles_fun('remove_file', filerow[0], self.files_conn)
                else:
                    self._verbose('Not removing file {0}'.format(filerow[0]), log.trace)
                self._pkgdb_fun('unregister_file', filerow[0], package, self.db_conn)

            # Clean up directories
            for dir_ in sorted(dirs, reverse=True):
                self._pkgdb_fun('unregister_file', dir_, package, self.db_conn)
                try:
                    self._verbose('Removing directory {0}'.format(dir_), log.trace)
                    os.rmdir(dir_)
                except OSError:
                    # Leave directories in place that still have files in them
                    self._verbose('Cannot remove directory {0}, probably not empty'.format(dir_), log.trace)

            self._pkgdb_fun('unregister_pkg', package, self.db_conn)

    def _verbose(self, msg, level=log.debug):
        '''
        Display verbose information
        '''
        if self.opts.get('verbose', False) is True:
            self.ui.status(msg)
        level(msg)

    def _local_info(self, args):
        '''
        List info for a package file
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package filename must be specified')

        pkg_file = args[1]

        if not os.path.exists(pkg_file):
            raise SPMInvocationError('Package file {0} not found'.format(pkg_file))

        comps = pkg_file.split('-')
        comps = '-'.join(comps[:-2]).split('/')
        name = comps[-1]

        formula_tar = tarfile.open(pkg_file, 'r:bz2')
        formula_ref = formula_tar.extractfile('{0}/FORMULA'.format(name))
        formula_def = yaml.safe_load(formula_ref)

        self.ui.status(self._get_info(formula_def))

    def _info(self, args):
        '''
        List info for a package
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package must be specified')

        package = args[1]

        pkg_info = self._pkgdb_fun('info', package, self.db_conn)
        if pkg_info is None:
            raise SPMPackageError('package {0} not installed'.format(package))
        self.ui.status(self._get_info(pkg_info))

    def _get_info(self, formula_def):
        '''
        Get package info
        '''
        fields = (
            'name',
            'os',
            'os_family',
            'release',
            'version',
            'dependencies',
            'os_dependencies',
            'os_family_dependencies',
            'summary',
            'description',
        )
        for item in fields:
            if item not in formula_def:
                formula_def[item] = 'None'

        if 'installed' not in formula_def:
            formula_def['installed'] = 'Not installed'

        return ('Name: {name}\n'
                'Version: {version}\n'
                'Release: {release}\n'
                'Install Date: {installed}\n'
                'Supported OSes: {os}\n'
                'Supported OS families: {os_family}\n'
                'Dependencies: {dependencies}\n'
                'OS Dependencies: {os_dependencies}\n'
                'OS Family Dependencies: {os_family_dependencies}\n'
                'Summary: {summary}\n'
                'Description:\n'
                '{description}').format(**formula_def)

    def _local_list_files(self, args):
        '''
        List files for a package file
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package filename must be specified')

        pkg_file = args[1]
        if not os.path.exists(pkg_file):
            raise SPMPackageError('Package file {0} not found'.format(pkg_file))
        formula_tar = tarfile.open(pkg_file, 'r:bz2')
        pkg_files = formula_tar.getmembers()

        for member in pkg_files:
            self.ui.status(member.name)

    def _list_files(self, args):
        '''
        List files for an installed package
        '''
        if len(args) < 2:
            raise SPMInvocationError('A package name must be specified')

        package = args[1]

        files = self._pkgdb_fun('list_files', package, self.db_conn)
        if files is None:
            raise SPMPackageError('package {0} not installed'.format(package))
        else:
            for file_ in files:
                if self.opts['verbose']:
                    status_msg = ','.join(file_)
                else:
                    status_msg = file_[0]
                self.ui.status(status_msg)

    def _build(self, args):
        '''
        Build a package
        '''
        if len(args) < 2:
            raise SPMInvocationError('A path to a formula must be specified')

        self.abspath = args[1].rstrip('/')
        comps = self.abspath.split('/')
        self.relpath = comps[-1]

        formula_path = '{0}/FORMULA'.format(self.abspath)
        if not os.path.exists(formula_path):
            raise SPMPackageError('Formula file {0} not found'.format(formula_path))
        with salt.utils.fopen(formula_path) as fp_:
            formula_conf = yaml.safe_load(fp_)

        for field in ('name', 'version', 'release', 'summary', 'description'):
            if field not in formula_conf:
                raise SPMPackageError('Invalid package: a {0} must be defined'.format(field))

        out_path = '{0}/{1}-{2}-{3}.spm'.format(
            self.opts['spm_build_dir'],
            formula_conf['name'],
            formula_conf['version'],
            formula_conf['release'],
        )

        if not os.path.exists(self.opts['spm_build_dir']):
            os.mkdir(self.opts['spm_build_dir'])

        self.formula_conf = formula_conf

        formula_tar = tarfile.open(out_path, 'w:bz2')

        try:
            formula_tar.add(formula_path, formula_conf['name'], filter=self._exclude)
            formula_tar.add(self.abspath, formula_conf['name'], filter=self._exclude)
        except TypeError:
            formula_tar.add(formula_path, formula_conf['name'], exclude=self._exclude)
            formula_tar.add(self.abspath, formula_conf['name'], exclude=self._exclude)
        formula_tar.close()

        self.ui.status('Built package {0}'.format(out_path))

    def _exclude(self, member):
        '''
        Exclude based on opts
        '''
        if isinstance(member, string_types):
            return None

        for item in self.opts['spm_build_exclude']:
            if member.name.startswith('{0}/{1}'.format(self.formula_conf['name'], item)):
                return None
            elif member.name.startswith('{0}/{1}'.format(self.abspath, item)):
                return None
        return member


class SPMUserInterface(object):
    '''
    Handle user interaction with an SPMClient object
    '''
    def status(self, msg):
        '''
        Report an SPMClient status message
        '''
        raise NotImplementedError()

    def error(self, msg):
        '''
        Report an SPM error message
        '''
        raise NotImplementedError()

    def confirm(self, action):
        '''
        Get confirmation from the user before performing an SPMClient action.
        Return if the action is confirmed, or raise SPMOperationCanceled(<msg>)
        if canceled.
        '''
        raise NotImplementedError()


class SPMCmdlineInterface(SPMUserInterface):
    '''
    Command-line interface to SPMClient
    '''
    def status(self, msg):
        print(msg)

    def error(self, msg):
        print(msg, file=sys.stderr)

    def confirm(self, action):
        print(action)
        res = input('Proceed? [N/y] ')
        if not res.lower().startswith('y'):
            raise SPMOperationCanceled('canceled')
