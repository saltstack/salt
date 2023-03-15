"""
Script for copying back xml junit files from tests
"""

import argparse  # pylint: disable=minimum-python-version
import os
import subprocess

import paramiko

import salt.utils.yaml


class DownloadArtifacts:
    def __init__(self, instance, artifacts):
        self.instance = instance
        self.artifacts = artifacts
        self.transport = self.setup_transport()
        self.sftpclient = paramiko.SFTPClient.from_transport(self.transport)

    def setup_transport(self):
        # pylint: disable=minimum-python-version
        config = salt.utils.yaml.safe_load(
            subprocess.check_output(
                ["bundle", "exec", "kitchen", "diagnose", self.instance]
            )
        )
        # pylint: enable=minimum-python-version
        state = config["instances"][self.instance]["state_file"]
        tport = config["instances"][self.instance]["transport"]
        transport = paramiko.Transport(
            (state["hostname"], state.get("port", tport.get("port", 22)))
        )
        pkey = paramiko.rsakey.RSAKey(
            filename=state.get("ssh_key", tport.get("ssh_key", "~/.ssh/id_rsa"))
        )
        transport.connect(
            username=state.get("username", tport.get("username", "root")), pkey=pkey
        )
        return transport

    def _set_permissions(self):
        """
        Make sure all xml files are readable by the world so that anyone can grab them
        """
        for remote, _ in self.artifacts:
            self.transport.open_session().exec_command(
                "sudo chmod -R +r {}".format(remote)
            )

    def download(self):
        self._set_permissions()
        for remote, local in self.artifacts:
            if remote.endswith("/"):
                for fxml in self.sftpclient.listdir(remote):
                    self._do_download(
                        os.path.join(remote, fxml),
                        os.path.join(local, os.path.basename(fxml)),
                    )
            else:
                self._do_download(remote, os.path.join(local, os.path.basename(remote)))

    def _do_download(self, remote, local):
        print("Copying from {} to {}".format(remote, local))
        try:
            self.sftpclient.get(remote, local)
        except OSError:
            print("Failed to copy: {}".format(remote))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jenkins Artifact Download Helper")
    parser.add_argument(
        "--instance",
        required=True,
        action="store",
        help="Instance on Test Kitchen to pull from",
    )
    parser.add_argument(
        "--download-artifacts",
        dest="artifacts",
        nargs=2,
        action="append",
        metavar=("REMOTE_PATH", "LOCAL_PATH"),
        help="Download remote artifacts",
    )
    args = parser.parse_args()
    downloader = DownloadArtifacts(args.instance, args.artifacts)
    downloader.download()
