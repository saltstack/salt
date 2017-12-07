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
import hashlib
import logging
import sys
try:
    import pwd
    import grp
except ImportError:
    pass

# Import Salt libs
import salt.client
import salt.config
import salt.loader
import salt.cache
import salt.syspaths as syspaths
from salt.ext import six
from salt.ext.six import string_types
from salt.ext.six.moves import input
from salt.ext.six.moves import filter
from salt.template import compile_template
import salt.utils.files
import salt.utils.http as http
import salt.utils.platform
import salt.utils.win_functions
from salt.utils.yamldumper import SafeOrderedDumper

# Get logging started
log = logging.getLogger(__name__)

FILE_TYPES = (u'c', u'd', u'g', u'l', u'r', u's', u'm')
# c: config file
# d: documentation file
# g: ghost file (i.e. the file contents are not included in the package payload)
# l: license file
# r: readme file
# s: SLS file
# m: Salt module


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
                os.path.join(syspaths.CONFIG_DIR, u'spm')
            )
        self.opts = opts
        self.db_prov = self.opts.get(u'spm_db_provider', u'sqlite3')
        self.files_prov = self.opts.get(u'spm_files_provider', u'local')
        self._prep_pkgdb()
        self._prep_pkgfiles()
        self._init()

    def _prep_pkgdb(self):
        self.pkgdb = salt.loader.pkgdb(self.opts)

    def _prep_pkgfiles(self):
        self.pkgfiles = salt.loader.pkgfiles(self.opts)

    def _init(self):
        self.db_conn = self._pkgdb_fun(u'init')
        self.files_conn = self._pkgfiles_fun(u'init')

    def run(self, args):
        '''
        Run the SPM command
        '''
        command = args[0]
        try:
            if command == u'install':
                self._install(args)
            elif command == u'local':
                self._local(args)
            elif command == u'repo':
                self._repo(args)
            elif command == u'remove':
                self._remove(args)
            elif command == u'build':
                self._build(args)
            elif command == u'update_repo':
                self._download_repo_metadata(args)
            elif command == u'create_repo':
                self._create_repo(args)
            elif command == u'files':
                self._list_files(args)
            elif command == u'info':
                self._info(args)
            elif command == u'list':
                self._list(args)
            else:
                raise SPMInvocationError(u'Invalid command \'{0}\''.format(command))
        except SPMException as exc:
            self.ui.error(str(exc))

    def _pkgdb_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgdb, self.db_prov), func)(*args, **kwargs)
        except AttributeError:
            return self.pkgdb[u'{0}.{1}'.format(self.db_prov, func)](*args, **kwargs)

    def _pkgfiles_fun(self, func, *args, **kwargs):
        try:
            return getattr(getattr(self.pkgfiles, self.files_prov), func)(*args, **kwargs)
        except AttributeError:
            return self.pkgfiles[u'{0}.{1}'.format(self.files_prov, func)](*args, **kwargs)

    def _list(self, args):
        '''
        Process local commands
        '''
        args.pop(0)
        command = args[0]
        if command == u'packages':
            self._list_packages(args)
        elif command == u'files':
            self._list_files(args)
        elif command == u'repos':
            self._repo_list(args)
        else:
            raise SPMInvocationError(u'Invalid list command \'{0}\''.format(command))

    def _local(self, args):
        '''
        Process local commands
        '''
        args.pop(0)
        command = args[0]
        if command == u'install':
            self._local_install(args)
        elif command == u'files':
            self._local_list_files(args)
        elif command == u'info':
            self._local_info(args)
        else:
            raise SPMInvocationError(u'Invalid local command \'{0}\''.format(command))

    def _repo(self, args):
        '''
        Process repo commands
        '''
        args.pop(0)
        command = args[0]
        if command == u'list':
            self._repo_list(args)
        elif command == u'packages':
            self._repo_packages(args)
        elif command == u'search':
            self._repo_packages(args, search=True)
        elif command == u'update':
            self._download_repo_metadata(args)
        elif command == u'create':
            self._create_repo(args)
        else:
            raise SPMInvocationError(u'Invalid repo command \'{0}\''.format(command))

    def _repo_packages(self, args, search=False):
        '''
        List packages for one or more configured repos
        '''
        packages = []
        repo_metadata = self._get_repo_metadata()
        for repo in repo_metadata:
            for pkg in repo_metadata[repo][u'packages']:
                if args[1] in pkg:
                    version = repo_metadata[repo][u'packages'][pkg][u'info'][u'version']
                    release = repo_metadata[repo][u'packages'][pkg][u'info'][u'release']
                    packages.append((pkg, version, release, repo))
        for pkg in sorted(packages):
            self.ui.status(
                u'{0}\t{1}-{2}\t{3}'.format(pkg[0], pkg[1], pkg[2], pkg[3])
            )
        return packages

    def _repo_list(self, args):
        '''
        List configured repos

        This can be called either as a ``repo`` command or a ``list`` command
        '''
        repo_metadata = self._get_repo_metadata()
        for repo in repo_metadata:
            self.ui.status(repo)

    def _install(self, args):
        '''
        Install a package from a repo
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package must be specified')

        caller_opts = self.opts.copy()
        caller_opts[u'file_client'] = u'local'
        self.caller = salt.client.Caller(mopts=caller_opts)
        self.client = salt.client.get_local_client(self.opts[u'conf_file'])
        cache = salt.cache.Cache(self.opts)

        packages = args[1:]
        file_map = {}
        optional = []
        recommended = []
        to_install = []
        for pkg in packages:
            if pkg.endswith(u'.spm'):
                if self._pkgfiles_fun(u'path_exists', pkg):
                    comps = pkg.split(u'-')
                    comps = u'-'.join(comps[:-2]).split(u'/')
                    pkg_name = comps[-1]

                    formula_tar = tarfile.open(pkg, u'r:bz2')
                    formula_ref = formula_tar.extractfile(u'{0}/FORMULA'.format(pkg_name))
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
                    raise SPMInvocationError(u'Package file {0} not found'.format(pkg))
            else:
                to_, op_, re_ = self._check_all_deps(pkg_name=pkg)
                to_install.extend(to_)
                optional.extend(op_)
                recommended.extend(re_)

        optional = set(filter(len, optional))
        if optional:
            self.ui.status(u'The following dependencies are optional:\n\t{0}\n'.format(
                u'\n\t'.join(optional)
            ))
        recommended = set(filter(len, recommended))
        if recommended:
            self.ui.status(u'The following dependencies are recommended:\n\t{0}\n'.format(
                u'\n\t'.join(recommended)
            ))

        to_install = set(filter(len, to_install))
        msg = u'Installing packages:\n\t{0}\n'.format(u'\n\t'.join(to_install))
        if not self.opts[u'assume_yes']:
            self.ui.confirm(msg)

        repo_metadata = self._get_repo_metadata()

        dl_list = {}
        for package in to_install:
            if package in file_map:
                self._install_indv_pkg(package, file_map[package])
            else:
                for repo in repo_metadata:
                    repo_info = repo_metadata[repo]
                    if package in repo_info[u'packages']:
                        dl_package = False
                        repo_ver = repo_info[u'packages'][package][u'info'][u'version']
                        repo_rel = repo_info[u'packages'][package][u'info'][u'release']
                        repo_url = repo_info[u'info'][u'url']
                        if package in dl_list:
                            # Check package version, replace if newer version
                            if repo_ver == dl_list[package][u'version']:
                                # Version is the same, check release
                                if repo_rel > dl_list[package][u'release']:
                                    dl_package = True
                                elif repo_rel == dl_list[package][u'release']:
                                    # Version and release are the same, give
                                    # preference to local (file://) repos
                                    if dl_list[package][u'source'].startswith(u'file://'):
                                        if not repo_url.startswith(u'file://'):
                                            dl_package = True
                            elif repo_ver > dl_list[package][u'version']:
                                dl_package = True
                        else:
                            dl_package = True

                        if dl_package is True:
                            # Put together download directory
                            cache_path = os.path.join(
                                self.opts[u'spm_cache_dir'],
                                repo
                            )

                            # Put together download paths
                            dl_url = u'{0}/{1}'.format(
                                repo_info[u'info'][u'url'],
                                repo_info[u'packages'][package][u'filename']
                            )
                            out_file = os.path.join(
                                cache_path,
                                repo_info[u'packages'][package][u'filename']
                            )
                            dl_list[package] = {
                                u'version': repo_ver,
                                u'release': repo_rel,
                                u'source': dl_url,
                                u'dest_dir': cache_path,
                                u'dest_file': out_file,
                            }

        for package in dl_list:
            dl_url = dl_list[package][u'source']
            cache_path = dl_list[package][u'dest_dir']
            out_file = dl_list[package][u'dest_file']

            # Make sure download directory exists
            if not os.path.exists(cache_path):
                os.makedirs(cache_path)

            # Download the package
            if dl_url.startswith(u'file://'):
                dl_url = dl_url.replace(u'file://', u'')
                shutil.copyfile(dl_url, out_file)
            else:
                with salt.utils.files.fopen(out_file, u'w') as outf:
                    outf.write(self._query_http(dl_url, repo_info[u'info']))

        # First we download everything, then we install
        for package in dl_list:
            out_file = dl_list[package][u'dest_file']
            # Kick off the install
            self._install_indv_pkg(package, out_file)
        return

    def _local_install(self, args, pkg_name=None):
        '''
        Install a package from a file
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package file must be specified')

        self._install(args)

    def _check_all_deps(self, pkg_name=None, pkg_file=None, formula_def=None):
        '''
        Starting with one package, check all packages for dependencies
        '''
        if pkg_file and not os.path.exists(pkg_file):
            raise SPMInvocationError(u'Package file {0} not found'.format(pkg_file))

        self.repo_metadata = self._get_repo_metadata()
        if not formula_def:
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo][u'packages'], dict):
                    continue
                if pkg_name in self.repo_metadata[repo][u'packages']:
                    formula_def = self.repo_metadata[repo][u'packages'][pkg_name][u'info']

        if not formula_def:
            raise SPMInvocationError(u'Unable to read formula for {0}'.format(pkg_name))

        # Check to see if the package is already installed
        pkg_info = self._pkgdb_fun(u'info', pkg_name, self.db_conn)
        pkgs_to_install = []
        if pkg_info is None or self.opts[u'force']:
            pkgs_to_install.append(pkg_name)
        elif pkg_info is not None and not self.opts[u'force']:
            raise SPMPackageError(
                u'Package {0} already installed, not installing again'.format(formula_def[u'name'])
            )

        optional_install = []
        recommended_install = []
        if u'dependencies' in formula_def or u'optional' in formula_def or u'recommended' in formula_def:
            self.avail_pkgs = {}
            for repo in self.repo_metadata:
                if not isinstance(self.repo_metadata[repo][u'packages'], dict):
                    continue
                for pkg in self.repo_metadata[repo][u'packages']:
                    self.avail_pkgs[pkg] = repo

            needs, unavail, optional, recommended = self._resolve_deps(formula_def)

            if len(unavail) > 0:
                raise SPMPackageError(
                    u'Cannot install {0}, the following dependencies are needed:\n\n{1}'.format(
                        formula_def[u'name'], u'\n'.join(unavail))
                )

            if optional:
                optional_install.extend(optional)
                for dep_pkg in optional:
                    pkg_info = self._pkgdb_fun(u'info', formula_def[u'name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = u'{0} [Installed]'.format(dep_pkg)
                    optional_install.append(msg)

            if recommended:
                recommended_install.extend(recommended)
                for dep_pkg in recommended:
                    pkg_info = self._pkgdb_fun(u'info', formula_def[u'name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = u'{0} [Installed]'.format(dep_pkg)
                    recommended_install.append(msg)

            if needs:
                pkgs_to_install.extend(needs)
                for dep_pkg in needs:
                    pkg_info = self._pkgdb_fun(u'info', formula_def[u'name'])
                    msg = dep_pkg
                    if isinstance(pkg_info, dict):
                        msg = u'{0} [Installed]'.format(dep_pkg)

        return pkgs_to_install, optional_install, recommended_install

    def _install_indv_pkg(self, pkg_name, pkg_file):
        '''
        Install one individual package
        '''
        self.ui.status(u'... installing {0}'.format(pkg_name))
        formula_tar = tarfile.open(pkg_file, u'r:bz2')
        formula_ref = formula_tar.extractfile(u'{0}/FORMULA'.format(pkg_name))
        formula_def = yaml.safe_load(formula_ref)

        for field in (u'version', u'release', u'summary', u'description'):
            if field not in formula_def:
                raise SPMPackageError(u'Invalid package: the {0} was not found'.format(field))

        pkg_files = formula_tar.getmembers()

        # First pass: check for files that already exist
        existing_files = self._pkgfiles_fun(u'check_existing', pkg_name, pkg_files, formula_def)

        if existing_files and not self.opts[u'force']:
            raise SPMPackageError(u'Not installing {0} due to existing files:\n\n{1}'.format(
                pkg_name, u'\n'.join(existing_files))
            )

        # We've decided to install
        self._pkgdb_fun(u'register_pkg', pkg_name, formula_def, self.db_conn)

        # Run the pre_local_state script, if present
        if u'pre_local_state' in formula_def:
            high_data = self._render(formula_def[u'pre_local_state'], formula_def)
            ret = self.caller.cmd(u'state.high', data=high_data)
        if u'pre_tgt_state' in formula_def:
            log.debug(u'Executing pre_tgt_state script')
            high_data = self._render(formula_def[u'pre_tgt_state'][u'data'], formula_def)
            tgt = formula_def[u'pre_tgt_state'][u'tgt']
            ret = self.client.run_job(
                tgt=formula_def[u'pre_tgt_state'][u'tgt'],
                fun=u'state.high',
                tgt_type=formula_def[u'pre_tgt_state'].get(u'tgt_type', u'glob'),
                timout=self.opts[u'timeout'],
                data=high_data,
            )

        # No defaults for this in config.py; default to the current running
        # user and group
        if salt.utils.platform.is_windows():
            uname = gname = salt.utils.win_functions.get_current_user()
            uname_sid = salt.utils.win_functions.get_sid_from_name(uname)
            uid = self.opts.get(u'spm_uid', uname_sid)
            gid = self.opts.get(u'spm_gid', uname_sid)
        else:
            uid = self.opts.get(u'spm_uid', os.getuid())
            gid = self.opts.get(u'spm_gid', os.getgid())
            uname = pwd.getpwuid(uid)[0]
            gname = grp.getgrgid(gid)[0]

        # Second pass: install the files
        for member in pkg_files:
            member.uid = uid
            member.gid = gid
            member.uname = uname
            member.gname = gname

            out_path = self._pkgfiles_fun(u'install_file',
                                          pkg_name,
                                          formula_tar,
                                          member,
                                          formula_def,
                                          self.files_conn)
            if out_path is not False:
                if member.isdir():
                    digest = u''
                else:
                    self._verbose(u'Installing file {0} to {1}'.format(member.name, out_path), log.trace)
                    file_hash = hashlib.sha1()
                    digest = self._pkgfiles_fun(u'hash_file',
                                                os.path.join(out_path, member.name),
                                                file_hash,
                                                self.files_conn)
                self._pkgdb_fun(u'register_file',
                                pkg_name,
                                member,
                                out_path,
                                digest,
                                self.db_conn)

        # Run the post_local_state script, if present
        if u'post_local_state' in formula_def:
            log.debug(u'Executing post_local_state script')
            high_data = self._render(formula_def[u'post_local_state'], formula_def)
            self.caller.cmd(u'state.high', data=high_data)
        if u'post_tgt_state' in formula_def:
            log.debug(u'Executing post_tgt_state script')
            high_data = self._render(formula_def[u'post_tgt_state'][u'data'], formula_def)
            tgt = formula_def[u'post_tgt_state'][u'tgt']
            ret = self.client.run_job(
                tgt=formula_def[u'post_tgt_state'][u'tgt'],
                fun=u'state.high',
                tgt_type=formula_def[u'post_tgt_state'].get(u'tgt_type', u'glob'),
                timout=self.opts[u'timeout'],
                data=high_data,
            )

        formula_tar.close()

    def _resolve_deps(self, formula_def):
        '''
        Return a list of packages which need to be installed, to resolve all
        dependencies
        '''
        pkg_info = self.pkgdb[u'{0}.info'.format(self.db_prov)](formula_def[u'name'])
        if not isinstance(pkg_info, dict):
            pkg_info = {}

        can_has = {}
        cant_has = []
        if u'dependencies' in formula_def and formula_def[u'dependencies'] is None:
            formula_def[u'dependencies'] = u''
        for dep in formula_def.get(u'dependencies', u'').split(u','):
            dep = dep.strip()
            if not dep:
                continue
            if self.pkgdb[u'{0}.info'.format(self.db_prov)](dep):
                continue

            if dep in self.avail_pkgs:
                can_has[dep] = self.avail_pkgs[dep]
            else:
                cant_has.append(dep)

        optional = formula_def.get(u'optional', u'').split(u',')
        recommended = formula_def.get(u'recommended', u'').split(u',')

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
            repo_packages = repo_contents.get(u'packages', {})
            dep_formula = repo_packages.get(dep, {}).get(u'info', {})

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
        if os.path.exists(self.opts[u'spm_repos_config']):
            repo_files.append(self.opts[u'spm_repos_config'])

        for (dirpath, dirnames, filenames) in os.walk(u'{0}.d'.format(self.opts[u'spm_repos_config'])):
            for repo_file in filenames:
                if not repo_file.endswith(u'.repo'):
                    continue
                repo_files.append(repo_file)

        for repo_file in repo_files:
            repo_path = u'{0}.d/{1}'.format(self.opts[u'spm_repos_config'], repo_file)
            with salt.utils.files.fopen(repo_path) as rph:
                repo_data = yaml.safe_load(rph)
                for repo in repo_data:
                    if repo_data[repo].get(u'enabled', True) is False:
                        continue
                    if repo_name is not None and repo != repo_name:
                        continue
                    callback(repo, repo_data[repo])

    def _query_http(self, dl_path, repo_info):
        '''
        Download files via http
        '''
        query = None
        response = None

        try:
            if u'username' in repo_info:
                try:
                    if u'password' in repo_info:
                        query = http.query(
                            dl_path, text=True,
                            username=repo_info[u'username'],
                            password=repo_info[u'password']
                        )
                    else:
                        raise SPMException(u'Auth defined, but password is not set for username: \'{0}\''
                                           .format(repo_info[u'username']))
                except SPMException as exc:
                    self.ui.error(str(exc))
            else:
                query = http.query(dl_path, text=True)
        except SPMException as exc:
            self.ui.error(str(exc))

        try:
            if query:
                if u'SPM-METADATA' in dl_path:
                    response = yaml.safe_load(query.get(u'text', u'{}'))
                else:
                    response = query.get(u'text')
            else:
                raise SPMException(u'Response is empty, please check for Errors above.')
        except SPMException as exc:
            self.ui.error(str(exc))

        return response

    def _download_repo_metadata(self, args):
        '''
        Connect to all repos and download metadata
        '''
        cache = salt.cache.Cache(self.opts, self.opts[u'spm_cache_dir'])

        def _update_metadata(repo, repo_info):
            dl_path = u'{0}/SPM-METADATA'.format(repo_info[u'url'])
            if dl_path.startswith(u'file://'):
                dl_path = dl_path.replace(u'file://', u'')
                with salt.utils.files.fopen(dl_path, u'r') as rpm:
                    metadata = yaml.safe_load(rpm)
            else:
                metadata = self._query_http(dl_path, repo_info)

            cache.store(u'.', repo, metadata)

        repo_name = args[1] if len(args) > 1 else None
        self._traverse_repos(_update_metadata, repo_name)

    def _get_repo_metadata(self):
        '''
        Return cached repo metadata
        '''
        cache = salt.cache.Cache(self.opts, self.opts[u'spm_cache_dir'])
        metadata = {}

        def _read_metadata(repo, repo_info):
            if cache.updated(u'.', repo) is None:
                log.warn(u'Updating repo metadata')
                self._download_repo_metadata({})

            metadata[repo] = {
                u'info': repo_info,
                u'packages': cache.fetch(u'.', repo),
            }

        self._traverse_repos(_read_metadata)
        return metadata

    def _create_repo(self, args):
        '''
        Scan a directory and create an SPM-METADATA file which describes
        all of the SPM files in that directory.
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A path to a directory must be specified')

        if args[1] == u'.':
            repo_path = os.getcwdu()
        else:
            repo_path = args[1]

        old_files = []
        repo_metadata = {}
        for (dirpath, dirnames, filenames) in os.walk(repo_path):
            for spm_file in filenames:
                if not spm_file.endswith(u'.spm'):
                    continue
                spm_path = u'{0}/{1}'.format(repo_path, spm_file)
                if not tarfile.is_tarfile(spm_path):
                    continue
                comps = spm_file.split(u'-')
                spm_name = u'-'.join(comps[:-2])
                spm_fh = tarfile.open(spm_path, u'r:bz2')
                formula_handle = spm_fh.extractfile(u'{0}/FORMULA'.format(spm_name))
                formula_conf = yaml.safe_load(formula_handle.read())

                use_formula = True
                if spm_name in repo_metadata:
                    # This package is already in the repo; use the latest
                    cur_info = repo_metadata[spm_name][u'info']
                    new_info = formula_conf
                    if int(new_info[u'version']) == int(cur_info[u'version']):
                        # Version is the same, check release
                        if int(new_info[u'release']) < int(cur_info[u'release']):
                            # This is an old release; don't use it
                            use_formula = False
                    elif int(new_info[u'version']) < int(cur_info[u'version']):
                        # This is an old version; don't use it
                        use_formula = False

                    if use_formula is True:
                        # Ignore/archive/delete the old version
                        log.debug(
                            u'%s %s-%s had been added, but %s-%s will replace it',
                            spm_name,
                            cur_info[u'version'],
                            cur_info[u'release'],
                            new_info[u'version'],
                            new_info[u'release'],
                        )
                        old_files.append(repo_metadata[spm_name][u'filename'])
                    else:
                        # Ignore/archive/delete the new version
                        log.debug(
                            u'%s %s-%s has been found, but is older than %s-%s',
                            spm_name,
                            new_info[u'version'],
                            new_info[u'release'],
                            cur_info[u'version'],
                            cur_info[u'release'],
                        )
                        old_files.append(spm_file)

                if use_formula is True:
                    log.debug(
                        u'adding %s-%s-%s to the repo',
                        formula_conf[u'name'],
                        formula_conf[u'version'],
                        formula_conf[u'release'],
                    )
                    repo_metadata[spm_name] = {
                        u'info': formula_conf.copy(),
                    }
                    repo_metadata[spm_name][u'filename'] = spm_file

        metadata_filename = u'{0}/SPM-METADATA'.format(repo_path)
        with salt.utils.files.fopen(metadata_filename, u'w') as mfh:
            yaml.dump(
                repo_metadata,
                mfh,
                indent=4,
                canonical=False,
                default_flow_style=False,
                Dumper=SafeOrderedDumper
            )

        log.debug(u'Wrote %s', metadata_filename)

        for file_ in old_files:
            if self.opts[u'spm_repo_dups'] == u'ignore':
                # ignore old packages, but still only add the latest
                log.debug(u'%s will be left in the directory', file_)
            elif self.opts[u'spm_repo_dups'] == u'archive':
                # spm_repo_archive_path is where old packages are moved
                if not os.path.exists(u'./archive'):
                    try:
                        os.makedirs(u'./archive')
                        log.debug(u'%s has been archived', file_)
                    except IOError:
                        log.error(u'Unable to create archive directory')
                try:
                    shutil.move(file_, u'./archive')
                except (IOError, OSError):
                    log.error(u'Unable to archive %s', file_)
            elif self.opts[u'spm_repo_dups'] == u'delete':
                # delete old packages from the repo
                try:
                    os.remove(file_)
                    log.debug(u'%s has been deleted', file_)
                except IOError:
                    log.error(u'Unable to delete %s', file_)
                except OSError:
                    # The file has already been deleted
                    pass

    def _remove(self, args):
        '''
        Remove a package
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package must be specified')

        packages = args[1:]
        msg = u'Removing packages:\n\t{0}'.format(u'\n\t'.join(packages))

        if not self.opts[u'assume_yes']:
            self.ui.confirm(msg)

        for package in packages:
            self.ui.status(u'... removing {0}'.format(package))

            if not self._pkgdb_fun(u'db_exists', self.opts[u'spm_db']):
                raise SPMDatabaseError(u'No database at {0}, cannot remove {1}'.format(self.opts[u'spm_db'], package))

            # Look at local repo index
            pkg_info = self._pkgdb_fun(u'info', package, self.db_conn)
            if pkg_info is None:
                raise SPMInvocationError(u'Package {0} not installed'.format(package))

            # Find files that have not changed and remove them
            files = self._pkgdb_fun(u'list_files', package, self.db_conn)
            dirs = []
            for filerow in files:
                if self._pkgfiles_fun(u'path_isdir', filerow[0]):
                    dirs.append(filerow[0])
                    continue
                file_hash = hashlib.sha1()
                digest = self._pkgfiles_fun(u'hash_file', filerow[0], file_hash, self.files_conn)
                if filerow[1] == digest:
                    self._verbose(u'Removing file {0}'.format(filerow[0]), log.trace)
                    self._pkgfiles_fun(u'remove_file', filerow[0], self.files_conn)
                else:
                    self._verbose(u'Not removing file {0}'.format(filerow[0]), log.trace)
                self._pkgdb_fun(u'unregister_file', filerow[0], package, self.db_conn)

            # Clean up directories
            for dir_ in sorted(dirs, reverse=True):
                self._pkgdb_fun(u'unregister_file', dir_, package, self.db_conn)
                try:
                    self._verbose(u'Removing directory {0}'.format(dir_), log.trace)
                    os.rmdir(dir_)
                except OSError:
                    # Leave directories in place that still have files in them
                    self._verbose(u'Cannot remove directory {0}, probably not empty'.format(dir_), log.trace)

            self._pkgdb_fun(u'unregister_pkg', package, self.db_conn)

    def _verbose(self, msg, level=log.debug):
        '''
        Display verbose information
        '''
        if self.opts.get(u'verbose', False) is True:
            self.ui.status(msg)
        level(msg)

    def _local_info(self, args):
        '''
        List info for a package file
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package filename must be specified')

        pkg_file = args[1]

        if not os.path.exists(pkg_file):
            raise SPMInvocationError(u'Package file {0} not found'.format(pkg_file))

        comps = pkg_file.split(u'-')
        comps = u'-'.join(comps[:-2]).split(u'/')
        name = comps[-1]

        formula_tar = tarfile.open(pkg_file, u'r:bz2')
        formula_ref = formula_tar.extractfile(u'{0}/FORMULA'.format(name))
        formula_def = yaml.safe_load(formula_ref)

        self.ui.status(self._get_info(formula_def))

    def _info(self, args):
        '''
        List info for a package
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package must be specified')

        package = args[1]

        pkg_info = self._pkgdb_fun(u'info', package, self.db_conn)
        if pkg_info is None:
            raise SPMPackageError(u'package {0} not installed'.format(package))
        self.ui.status(self._get_info(pkg_info))

    def _get_info(self, formula_def):
        '''
        Get package info
        '''
        fields = (
            u'name',
            u'os',
            u'os_family',
            u'release',
            u'version',
            u'dependencies',
            u'os_dependencies',
            u'os_family_dependencies',
            u'summary',
            u'description',
        )
        for item in fields:
            if item not in formula_def:
                formula_def[item] = u'None'

        if u'installed' not in formula_def:
            formula_def[u'installed'] = u'Not installed'

        return (u'Name: {name}\n'
                u'Version: {version}\n'
                u'Release: {release}\n'
                u'Install Date: {installed}\n'
                u'Supported OSes: {os}\n'
                u'Supported OS families: {os_family}\n'
                u'Dependencies: {dependencies}\n'
                u'OS Dependencies: {os_dependencies}\n'
                u'OS Family Dependencies: {os_family_dependencies}\n'
                u'Summary: {summary}\n'
                u'Description:\n'
                u'{description}').format(**formula_def)

    def _local_list_files(self, args):
        '''
        List files for a package file
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package filename must be specified')

        pkg_file = args[1]
        if not os.path.exists(pkg_file):
            raise SPMPackageError(u'Package file {0} not found'.format(pkg_file))
        formula_tar = tarfile.open(pkg_file, u'r:bz2')
        pkg_files = formula_tar.getmembers()

        for member in pkg_files:
            self.ui.status(member.name)

    def _list_packages(self, args):
        '''
        List files for an installed package
        '''
        packages = self._pkgdb_fun(u'list_packages', self.db_conn)
        for package in packages:
            if self.opts[u'verbose']:
                status_msg = u','.join(package)
            else:
                status_msg = package[0]
            self.ui.status(status_msg)

    def _list_files(self, args):
        '''
        List files for an installed package
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A package name must be specified')

        package = args[-1]

        files = self._pkgdb_fun(u'list_files', package, self.db_conn)
        if files is None:
            raise SPMPackageError(u'package {0} not installed'.format(package))
        else:
            for file_ in files:
                if self.opts[u'verbose']:
                    status_msg = u','.join(file_)
                else:
                    status_msg = file_[0]
                self.ui.status(status_msg)

    def _build(self, args):
        '''
        Build a package
        '''
        if len(args) < 2:
            raise SPMInvocationError(u'A path to a formula must be specified')

        self.abspath = args[1].rstrip(u'/')
        comps = self.abspath.split(u'/')
        self.relpath = comps[-1]

        formula_path = u'{0}/FORMULA'.format(self.abspath)
        if not os.path.exists(formula_path):
            raise SPMPackageError(u'Formula file {0} not found'.format(formula_path))
        with salt.utils.files.fopen(formula_path) as fp_:
            formula_conf = yaml.safe_load(fp_)

        for field in (u'name', u'version', u'release', u'summary', u'description'):
            if field not in formula_conf:
                raise SPMPackageError(u'Invalid package: a {0} must be defined'.format(field))

        out_path = u'{0}/{1}-{2}-{3}.spm'.format(
            self.opts[u'spm_build_dir'],
            formula_conf[u'name'],
            formula_conf[u'version'],
            formula_conf[u'release'],
        )

        if not os.path.exists(self.opts[u'spm_build_dir']):
            os.mkdir(self.opts[u'spm_build_dir'])

        self.formula_conf = formula_conf

        formula_tar = tarfile.open(out_path, u'w:bz2')

        if u'files' in formula_conf:
            # This allows files to be added to the SPM file in a specific order.
            # It also allows for files to be tagged as a certain type, as with
            # RPM files. This tag is ignored here, but is used when installing
            # the SPM file.
            if isinstance(formula_conf[u'files'], list):
                formula_dir = tarfile.TarInfo(formula_conf[u'name'])
                formula_dir.type = tarfile.DIRTYPE
                formula_tar.addfile(formula_dir)
                for file_ in formula_conf[u'files']:
                    for ftype in FILE_TYPES:
                        if file_.startswith(u'{0}|'.format(ftype)):
                            file_ = file_.lstrip(u'{0}|'.format(ftype))
                    formula_tar.add(
                        os.path.join(os.getcwd(), file_),
                        os.path.join(formula_conf[u'name'], file_),
                    )
        else:
            # If no files are specified, then the whole directory will be added.
            try:
                formula_tar.add(formula_path, formula_conf[u'name'], filter=self._exclude)
                formula_tar.add(self.abspath, formula_conf[u'name'], filter=self._exclude)
            except TypeError:
                formula_tar.add(formula_path, formula_conf[u'name'], exclude=self._exclude)
                formula_tar.add(self.abspath, formula_conf[u'name'], exclude=self._exclude)
        formula_tar.close()

        self.ui.status(u'Built package {0}'.format(out_path))

    def _exclude(self, member):
        '''
        Exclude based on opts
        '''
        if isinstance(member, string_types):
            return None

        for item in self.opts[u'spm_build_exclude']:
            if member.name.startswith(u'{0}/{1}'.format(self.formula_conf[u'name'], item)):
                return None
            elif member.name.startswith(u'{0}/{1}'.format(self.abspath, item)):
                return None
        return member

    def _render(self, data, formula_def):
        '''
        Render a [pre|post]_local_state or [pre|post]_tgt_state script
        '''
        # FORMULA can contain a renderer option
        renderer = formula_def.get(u'renderer', self.opts.get(u'renderer', u'yaml_jinja'))
        rend = salt.loader.render(self.opts, {})
        blacklist = self.opts.get(u'renderer_blacklist')
        whitelist = self.opts.get(u'renderer_whitelist')
        template_vars = formula_def.copy()
        template_vars[u'opts'] = self.opts.copy()
        return compile_template(
            u':string:',
            rend,
            renderer,
            blacklist,
            whitelist,
            input_data=data,
            **template_vars
        )


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
        res = input(u'Proceed? [N/y] ')
        if not res.lower().startswith(u'y'):
            raise SPMOperationCanceled(u'canceled')
