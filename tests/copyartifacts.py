import argparse
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
        config = yaml.load(subprocess.check_output(['bundle', 'exec', 'kitchen', 'diagnose', self.instance]))
        instance = config['instances'][self.instance]['state_file']
        transport = paramiko.Transport((instance['hostname'], instance['port']))
        pkey = paramiko.rsakey.RSAKey(filename=instance['ssh_key'])
        transport.connect(username=instance['username'], pkey=pkey)
        return paramiko.SFTPClient.from_transport(transport)

    def download(self):
        for remote, local in self.artifacts:
            if remote.endswith('/'):
                for fxml in self.client.listdir(remote):
                    print(os.path.join(remote, fxml))
                    print(os.path.join(local, os.path.basename(fxml)))
                    self.client.get(os.path.join(remote, fxml), os.path.join(local, os.path.basename(fxml)))
            else:
                self.client.get(fxml, os.path.join([local, os.path.basename(fxml)]))

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
