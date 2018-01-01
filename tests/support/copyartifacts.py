# -*- coding: utf-8 -*-
'''
Script for copying back xml junit files from tests
'''
from __future__ import absolute_import, print_function
import argparse  # pylint: disable=minimum-python-version
import os
import paramiko
import subprocess
import yaml


class DownloadArtifacts(object):
    def __init__(self, instance, artifacts):
        self.instance = instance
        self.artifacts = artifacts
        self.client = self.setup_transport()

    def setup_transport(self):
        # pylint: disable=minimum-python-version
        config = yaml.load(subprocess.check_output(['bundle', 'exec', 'kitchen', 'diagnose', self.instance]))
        # pylint: enable=minimum-python-version
        state = config['instances'][self.instance]['state_file']
        tport = config['instances'][self.instance]['transport']
        transport = paramiko.Transport((
            state['hostname'],
            state.get('port', tport.get('port', 22))
        ))
        pkey = paramiko.rsakey.RSAKey(
            filename=state.get('ssh_key', tport.get('ssh_key', '~/.ssh/id_rsa'))
        )
        transport.connect(
            username=state.get('username', tport.get('username', 'root')),
            pkey=pkey
        )
        return paramiko.SFTPClient.from_transport(transport)

    def download(self):
        for remote, local in self.artifacts:
            if remote.endswith('/'):
                for fxml in self.client.listdir(remote):
                    self._do_download(os.path.join(remote, fxml), os.path.join(local, os.path.basename(fxml)))
            else:
                self._do_download(remote, os.path.join(local, os.path.basename(remote)))

    def _do_download(self, remote, local):
        print('Copying from {0} to {1}'.format(remote, local))
        self.client.get(remote, local)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Jenkins Artifact Download Helper')
    parser.add_argument(
        '--instance',
        required=True,
        action='store',
        help='Instance on Test Kitchen to pull from',
    )
    parser.add_argument(
        '--download-artifacts',
        dest='artifacts',
        nargs=2,
        action='append',
        metavar=('REMOTE_PATH', 'LOCAL_PATH'),
        help='Download remote artifacts',
    )
    args = parser.parse_args()
    downloader = DownloadArtifacts(args.instance, args.artifacts)
    downloader.download()
