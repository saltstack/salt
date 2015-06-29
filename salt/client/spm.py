# -*- coding: utf-8 -*-
'''
This module provides the point of entry to SPM, the Salt Package Manager

.. versionadded:: Beryllium
'''
# Import Python libs
from __future__ import absolute_import
import os
import yaml
import tarfile
import shutil
import msgpack
import sqlite3
import datetime
import hashlib
import logging

# Import Salt libs
import salt.config
import salt.utils
import salt.utils.http as http
import salt.syspaths as syspaths

# Get logging started
log = logging.getLogger(__name__)


class SPMClient(object):
    '''
    Provide an SPM Client
    '''
    def __init__(self, opts=None):
        if not opts:
            opts = salt.config.client_config(
                os.environ.get(
                    'SALT_MASTER_CONFIG',
                    os.path.join(syspaths.CONFIG_DIR, 'master')
                )
            )
        self.opts = opts

    def run(self, args):
        '''
        Run the SPM command
        '''
        command = args[0]
        if command == 'install':
            self._install(args)
        elif command == 'local_install':
            self._local_install(args)
        elif command == 'remove':
            self._remove(args)
        elif command == 'build':
            self._build(args)
        elif command == 'update_repo':
            self._download_repo_metadata()
        elif command == 'create_repo':
            self._create_repo(args)

    def _local_install(self, args):
        '''
        Install a package from a file
        '''
        if len(args) < 2:
            log.error('A package file must be specified')
            return False

        package_file = args[1]

        self._init_db()
        out_path = self.opts['file_roots']['base'][0]
        comps = package_file.split('-')
        comps = '-'.join(comps[:-2]).split('/')
        name = comps[-1]
        log.debug('Locally installing package {0} to {1}'.format(package_file, out_path))

        if not os.path.exists(package_file):
            log.error('File {0} not found'.format(package_file))
            return False

        if not os.path.exists(out_path):
            os.mkdir(out_path)

        sqlite3.enable_callback_tracebacks(True)
        conn = sqlite3.connect(self.opts['spm_db'], isolation_level=None)
        cur = conn.cursor()
        formula_tar = tarfile.open(package_file, 'r:bz2')
        formula_ref = formula_tar.extractfile('{0}/FORMULA'.format(name))
        formula_def = yaml.safe_load(formula_ref)

        for field in ('version', 'release', 'summary', 'description'):
            if field not in formula_def:
                log.error('Invalid package: the {0} was not found'.format(field))
                return False

        conn.execute('INSERT INTO packages VALUES (?, ?, ?, ?, ?, ?)', (
            name,
            formula_def['version'],
            formula_def['release'],
            datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
            formula_def['summary'],
            formula_def['description'],
        ))
        pkg_files = formula_tar.getmembers()
        for member in pkg_files:
            file_ref = formula_tar.extractfile(member)
            if member.isdir():
                digest = ''
            else:
                file_hash = hashlib.sha1()
                file_hash.update(file_ref.read())
                digest = file_hash.hexdigest()
            formula_tar.extract(member, out_path)
            conn.execute('INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                name,
                '{0}/{1}'.format(out_path, member.path),
                member.size,
                member.mode,
                digest,
                member.devmajor,
                member.devminor,
                member.linkname,
                member.linkpath,
                member.uname,
                member.gname,
                member.mtime
            ))
        formula_tar.close()
        conn.close()

    def _traverse_repos(self, callback):
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
                    callback(repo, repo_data[repo])

    def _download_repo_metadata(self):
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
                response = http.query(
                    '{0}/SPM-METADATA'.format(dl_path),
                )
                metadata = response.get('dict', {})
            cache_path = '{0}/{1}.p'.format(
                self.opts['spm_cache_dir'],
                repo
            )

            with salt.utils.fopen(cache_path, 'w') as cph:
                msgpack.dump(metadata, cph)

        self._traverse_repos(_update_metadata)

    def _get_repo_metadata(self):
        '''
        Return cached repo metadata
        '''
        metadata = {}

        def _read_metadata(repo, repo_info):
            cache_path = '{0}/{1}.p'.format(
                self.opts['spm_cache_dir'],
                repo
            )

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
            log.error('A path to a directory must be specified')
            return False

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
                repo_metadata[spm_name] = formula_conf.copy()
                repo_metadata[spm_name]['filename'] = spm_file

        metadata_filename = '{0}/SPM-METADATA'.format(repo_path)
        with salt.utils.fopen(metadata_filename, 'w') as mfh:
            yaml.dump(repo_metadata, mfh, indent=4, canonical=False, default_flow_style=False)

        log.debug('Wrote {0}'.format(metadata_filename))

    def _install(self, args):
        '''
        Install a package from a repo
        '''
        if len(args) < 2:
            log.error('A package must be specified')
            return False

        package = args[1]

        log.debug('Installing package {0}'.format(package))
        repo_metadata = self._get_repo_metadata()
        for repo in repo_metadata:
            repo_info = repo_metadata[repo]
            if package in repo_metadata[repo]['packages']:
                cache_path = '{0}/{1}'.format(
                    self.opts['spm_cache_dir'],
                    repo
                )
                dl_path = '{0}/{1}'.format(repo_info['info']['url'], repo_info['packages'][package]['filename'])
                out_file = '{0}/{1}'.format(cache_path, repo_info['packages'][package]['filename'])
                if not os.path.exists(cache_path):
                    os.makedirs(cache_path)

                if dl_path.startswith('file://'):
                    dl_path = dl_path.replace('file://', '')
                    shutil.copyfile(dl_path, out_file)
                else:
                    http.query(dl_path, text_out=out_file)

                self._local_install(out_file)
                return

    def _remove(self, args):
        '''
        Remove a package
        '''
        if len(args) < 2:
            log.error('A package must be specified')
            return False

        package = args[1]
        log.debug('Removing package {0}'.format(package))

        if not os.path.exists(self.opts['spm_db']):
            log.error('No database at {0}, cannot remove {1}'.format(self.opts['spm_db'], package))
            return

        # Look at local repo index
        sqlite3.enable_callback_tracebacks(True)
        conn = sqlite3.connect(self.opts['spm_db'], isolation_level=None)
        cur = conn.cursor()

        data = conn.execute('SELECT * FROM packages WHERE package=?', (package, ))
        if not data.fetchone():
            log.error('Package {0} not installed'.format(package))
            return

        # Find files that have not changed and remove them
        data = conn.execute('SELECT path, sum FROM files WHERE package=?', (package, ))
        dirs = []
        for filerow in data.fetchall():
            if os.path.isdir(filerow[0]):
                dirs.append(filerow[0])
                continue
            with salt.utils.fopen(filerow[0], 'r') as fh_:
                file_hash = hashlib.sha1()
                file_hash.update(fh_.read())
                digest = file_hash.hexdigest()
                if filerow[1] == digest:
                    log.trace('Removing file {0}'.format(filerow[0]))
                    os.remove(filerow[0])
                else:
                    log.trace('Not removing file {0}'.format(filerow[0]))
                conn.execute('DELETE FROM files WHERE path=?', (filerow[0], ))

        # Clean up directories
        for dir_ in sorted(dirs, reverse=True):
            conn.execute('DELETE FROM files WHERE path=?', (dir_, ))
            try:
                log.trace('Removing directory {0}'.format(dir_))
                os.rmdir(dir_)
            except OSError:
                # Leave directories in place that still have files in them
                log.trace('Cannot remove directory {0}, probably not empty'.format(dir_))

        conn.execute('DELETE FROM packages WHERE package=?', (package, ))

    def _build(self, args):
        '''
        Build a package
        '''
        if len(args) < 2:
            log.error('A path to a formula must be specified')
            return False

        self.abspath = args[1]
        comps = self.abspath.split('/')
        self.relpath = comps[-1]

        formula_path = '{0}/FORMULA'.format(self.abspath)
        formula_conf = {}
        if os.path.exists(formula_path):
            with salt.utils.fopen(formula_path) as fp_:
                formula_conf = yaml.safe_load(fp_)
        else:
            log.debug('File not found')
            return False

        for field in ('version', 'release', 'summary', 'description'):
            if field not in formula_conf:
                log.error('Invalid package: a {0} must be defined'.format(field))
                return False

        out_path = '{0}/{1}-{2}-{3}.spm'.format(
            self.opts['spm_build_dir'],
            formula_conf['name'],
            formula_conf['version'],
            formula_conf['release'],
        )

        if not os.path.exists(self.opts['spm_build_dir']):
            os.mkdir(self.opts['spm_build_dir'])

        formula_tar = tarfile.open(out_path, 'w:bz2')
        formula_tar.add(self.abspath, formula_conf['name'], exclude=self._exclude)
        formula_tar.close()

        log.debug(formula_path)
        return formula_path

    def _exclude(self, name):
        '''
        Exclude based on opts
        '''
        for item in self.opts['spm_build_exclude']:
            exclude_name = '{0}/{1}'.format(self.abspath, item)
            if name.startswith(exclude_name):
                return True
        return False

    def _init_db(self):
        '''
        Initialize the package database
        '''
        if not os.path.exists(self.opts['spm_db']):
            log.debug('Creating new package database at {0}'.format(self.opts['spm_db']))
            conn = sqlite3.connect(self.opts['spm_db'], isolation_level=None)
            cur = conn.cursor()
            conn.execute('''CREATE TABLE packages (
                package text,
                version text,
                release text,
                installed text,
                summary text,
                description text
            )''')
            conn.execute('''CREATE TABLE files (
                package text,
                path text,
                size real,
                mode text,
                sum text,
                major text,
                minor text,
                linkname text,
                linkpath text,
                uname text,
                gname text,
                mtime text
            )''')
            conn.close()
