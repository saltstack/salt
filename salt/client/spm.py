# -*- coding: utf-8 -*-
'''
This module provides the point of entry to SPM, the Salt Package Manager

.. versionadded:: Beryllium
'''
from __future__ import absolute_import
# Import Python libs
import os
import yaml
import tarfile
import tempfile
import shutil
import msgpack

# Import Salt libs
import salt.config
import salt.utils
import salt.utils.http as http
import salt.syspaths as syspaths


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
            self._install(args[1])
        elif command == 'local_install':
            self._local_install(args[1])
        elif command == 'remove':
            self._remove(args)
        elif command == 'build':
            self._build(args)
        elif command == 'update_repo':
            self._download_repo_metadata()
        elif command == 'create_repo':
            self._create_repo(args)

    def _local_install(self, package_file):
        '''
        Install a package from a file
        '''
        out_path = self.opts['file_roots']['base'][0]
        print('Locally installing package {0} to {1}'.format(package_file, out_path))

        if not os.path.exists(package_file):
            print('File not found')
            return False

        if not os.path.exists(out_path):
            os.mkdir(out_path)

        formula_tar = tarfile.open(package_file, 'r:bz2')
        formula_tar.extractall(out_path)
        formula_tar.close()
        # Save file list and checksums in local repo index (msgpack)

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
            dl_path = '{0}/SPM-METADATA.yml'.format(repo_info['url'])
            if dl_path.startswith('file://'):
                dl_path = dl_path.replace('file://', '')
                with salt.utils.fopen(dl_path, 'r') as rpm:
                    metadata = yaml.safe_load(rpm)
            else:
                response = http.query(
                    '{0}/SPM-MANIFEST.yml'.format(dl_path),
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
        Scan a directory and create an SPM-METADATA.yml file which describes
        all of the SPM files in that directory.
        '''
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
                formula_handle = spm_fh.extractfile('{0}/FORMULA.yml'.format(spm_name))
                formula_conf = yaml.safe_load(formula_handle.read())
                repo_metadata[spm_name] = formula_conf.copy()
                repo_metadata[spm_name]['filename'] = spm_file

        metadata_filename = '{0}/SPM-METADATA.yml'.format(repo_path)
        with salt.utils.fopen(metadata_filename, 'w') as mfh:
            yaml.dump(repo_metadata, mfh, indent=4, canonical=False, default_flow_style=False)

        print('Wrote {0}'.format(metadata_filename))

    def _install(self, package):
        '''
        Install a package from a repo
        '''
        print('Installing package {0}'.format(package))
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
        package = args[1]
        print('Removing package {0}'.format(package))
        # Look at local repo index
        # Find files that have not changed and remove them
        # Leave directories in place that still have files in them

    def _build(self, args):
        '''
        Build a package
        '''
        self.abspath = args[1]
        comps = self.abspath.split('/')
        self.relpath = comps[-1]

        formula_path = '{0}/FORMULA.yml'.format(self.abspath)
        formula_conf = {}
        if os.path.exists(formula_path):
            with salt.utils.fopen(formula_path) as fp_:
                formula_conf = yaml.safe_load(fp_)
        else:
            print('File not found')
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

        print(formula_path)
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
