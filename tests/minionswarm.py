#!/usr/bin/env python

"""
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
"""
# pylint: disable=resource-leakage

import hashlib
import optparse  # pylint: disable=deprecated-module
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import salt
import salt.utils.files
import salt.utils.yaml
import tests.support.runtests

OSES = [
    "Arch",
    "Ubuntu",
    "Debian",
    "CentOS",
    "Fedora",
    "Gentoo",
    "AIX",
    "Solaris",
]
VERS = [
    "2014.1.6",
    "2014.7.4",
    "2015.5.5",
    "2015.8.0",
]


def parse():
    """
    Parse the cli options
    """
    parser = optparse.OptionParser()
    parser.add_option(
        "-m",
        "--minions",
        dest="minions",
        default=5,
        type="int",
        help="The number of minions to make",
    )
    parser.add_option(
        "-M",
        action="store_true",
        dest="master_too",
        default=False,
        help="Run a local master and tell the minions to connect to it",
    )
    parser.add_option(
        "--master",
        dest="master",
        default="salt",
        help="The location of the salt master that this swarm will serve",
    )
    parser.add_option(
        "--name",
        "-n",
        dest="name",
        default="ms",
        help=(
            "Give the minions an alternative id prefix, this is used "
            "when minions from many systems are being aggregated onto "
            "a single master"
        ),
    )
    parser.add_option(
        "--rand-os",
        dest="rand_os",
        default=False,
        action="store_true",
        help="Each Minion claims a different os grain",
    )
    parser.add_option(
        "--rand-ver",
        dest="rand_ver",
        default=False,
        action="store_true",
        help="Each Minion claims a different version grain",
    )
    parser.add_option(
        "--rand-machine-id",
        dest="rand_machine_id",
        default=False,
        action="store_true",
        help="Each Minion claims a different machine id grain",
    )
    parser.add_option(
        "--rand-uuid",
        dest="rand_uuid",
        default=False,
        action="store_true",
        help="Each Minion claims a different UUID grain",
    )
    parser.add_option(
        "-k",
        "--keep-modules",
        dest="keep",
        default="",
        help="A comma delimited list of modules to enable",
    )
    parser.add_option(
        "-f",
        "--foreground",
        dest="foreground",
        default=False,
        action="store_true",
        help="Run the minions with debug output of the swarm going to the terminal",
    )
    parser.add_option(
        "--temp-dir",
        dest="temp_dir",
        default=None,
        help="Place temporary files/directories here",
    )
    parser.add_option(
        "--no-clean",
        action="store_true",
        default=False,
        help="Don't cleanup temporary files/directories",
    )
    parser.add_option(
        "--root-dir",
        dest="root_dir",
        default=None,
        help="Override the minion root_dir config",
    )
    parser.add_option(
        "--transport",
        dest="transport",
        default="zeromq",
        help="Declare which transport to use, default is zeromq",
    )
    parser.add_option(
        "--start-delay",
        dest="start_delay",
        default=0.0,
        type="float",
        help="Seconds to wait between minion starts",
    )
    parser.add_option(
        "-c",
        "--config-dir",
        default="",
        help="Pass in a configuration directory containing base configuration.",
    )
    parser.add_option("-u", "--user", default=tests.support.runtests.this_user())

    options, _args = parser.parse_args()

    opts = {}

    for key, val in options.__dict__.items():
        opts[key] = val

    return opts


class Swarm:
    """
    Create a swarm of minions
    """

    def __init__(self, opts):
        self.opts = opts

        # If given a temp_dir, use it for temporary files
        if opts["temp_dir"]:
            self.swarm_root = opts["temp_dir"]
        else:
            # If given a root_dir, keep the tmp files there as well
            if opts["root_dir"]:
                tmpdir = os.path.join(opts["root_dir"], "tmp")
            else:
                tmpdir = opts["root_dir"]
            self.swarm_root = tempfile.mkdtemp(
                prefix="mswarm-root", suffix=".d", dir=tmpdir
            )

        if self.opts["transport"] == "zeromq":
            self.pki = self._pki_dir()
        self.zfill = len(str(self.opts["minions"]))

        self.confs = set()

        random.seed(0)

    def _pki_dir(self):
        """
        Create the shared pki directory
        """
        path = os.path.join(self.swarm_root, "pki")
        if not os.path.exists(path):
            os.makedirs(path)

            print(f"Creating shared pki keys for the swarm on: {path}")
            subprocess.call(
                "salt-key -c {0} --gen-keys minion --gen-keys-dir {0} "
                "--log-file {1} --user {2}".format(
                    path,
                    os.path.join(path, "keys.log"),
                    self.opts["user"],
                ),
                shell=True,
            )
            print("Keys generated")
        return path

    def start(self):
        """
        Start the magic!!
        """
        if self.opts["master_too"]:
            master_swarm = MasterSwarm(self.opts)
            master_swarm.start()
        minions = MinionSwarm(self.opts)
        minions.start_minions()
        print("Starting minions...")
        # self.start_minions()
        print("All {} minions have started.".format(self.opts["minions"]))
        print("Waiting for CTRL-C to properly shutdown minions...")
        while True:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print("\nShutting down minions")
                self.clean_configs()
                break

    def shutdown(self):
        """
        Tear it all down
        """
        print("Killing any remaining running minions")
        subprocess.call('pkill -KILL -f "python.*salt-minion"', shell=True)
        if self.opts["master_too"]:
            print("Killing any remaining masters")
            subprocess.call('pkill -KILL -f "python.*salt-master"', shell=True)
        if not self.opts["no_clean"]:
            print("Remove ALL related temp files/directories")
            shutil.rmtree(self.swarm_root)
        print("Done")

    def clean_configs(self):
        """
        Clean up the config files
        """
        for path in self.confs:
            pidfile = f"{path}.pid"
            try:
                try:
                    with salt.utils.files.fopen(pidfile) as fp_:
                        pid = int(fp_.read().strip())
                    os.kill(pid, signal.SIGTERM)
                except ValueError:
                    pass
                if os.path.exists(pidfile):
                    os.remove(pidfile)
                if not self.opts["no_clean"]:
                    shutil.rmtree(path)
            except OSError:
                pass


class MinionSwarm(Swarm):
    """
    Create minions
    """

    def start_minions(self):
        """
        Iterate over the config files and start up the minions
        """
        self.prep_configs()
        for path in self.confs:
            cmd = "salt-minion -c {} --pid-file {}".format(path, f"{path}.pid")
            if self.opts["foreground"]:
                cmd += " -l debug &"
            else:
                cmd += " -d &"
            subprocess.call(cmd, shell=True)
            time.sleep(self.opts["start_delay"])

    def mkconf(self, idx):
        """
        Create a config file for a single minion
        """
        data = {}
        if self.opts["config_dir"]:
            spath = os.path.join(self.opts["config_dir"], "minion")
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf) or {}
        minion_id = "{}-{}".format(self.opts["name"], str(idx).zfill(self.zfill))

        dpath = os.path.join(self.swarm_root, minion_id)
        if not os.path.exists(dpath):
            os.makedirs(dpath)

        data.update(
            {
                "id": minion_id,
                "user": self.opts["user"],
                "cachedir": os.path.join(dpath, "cache"),
                "master": self.opts["master"],
                "log_file": os.path.join(dpath, "minion.log"),
                "grains": {},
            }
        )

        if self.opts["transport"] == "zeromq":
            minion_pkidir = os.path.join(dpath, "pki")
            if not os.path.exists(minion_pkidir):
                os.makedirs(minion_pkidir)
                minion_pem = os.path.join(self.pki, "minion.pem")
                minion_pub = os.path.join(self.pki, "minion.pub")
                shutil.copy(minion_pem, minion_pkidir)
                shutil.copy(minion_pub, minion_pkidir)
            data["pki_dir"] = minion_pkidir
        elif self.opts["transport"] == "tcp":
            data["transport"] = "tcp"

        if self.opts["root_dir"]:
            data["root_dir"] = self.opts["root_dir"]

        path = os.path.join(dpath, "minion")

        if self.opts["keep"]:
            keep = self.opts["keep"].split(",")
            modpath = os.path.join(os.path.dirname(salt.__file__), "modules")
            fn_prefixes = (fn_.partition(".")[0] for fn_ in os.listdir(modpath))
            ignore = [fn_prefix for fn_prefix in fn_prefixes if fn_prefix not in keep]
            data["disable_modules"] = ignore

        if self.opts["rand_os"]:
            data["grains"]["os"] = random.choice(OSES)
        if self.opts["rand_ver"]:
            data["grains"]["saltversion"] = random.choice(VERS)
        if self.opts["rand_machine_id"]:
            data["grains"]["machine_id"] = hashlib.md5(minion_id).hexdigest()
        if self.opts["rand_uuid"]:
            data["grains"]["uuid"] = str(uuid.uuid4())

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)
        self.confs.add(dpath)

    def prep_configs(self):
        """
        Prepare the confs set
        """
        for idx in range(self.opts["minions"]):
            self.mkconf(idx)


class MasterSwarm(Swarm):
    """
    Create one or more masters
    """

    def __init__(self, opts):
        super().__init__(opts)
        self.conf = os.path.join(self.swarm_root, "master")

    def start(self):
        """
        Prep the master start and fire it off
        """
        # sys.stdout for no newline
        sys.stdout.write("Generating master config...")
        self.mkconf()
        print("done")

        sys.stdout.write("Starting master...")
        self.start_master()
        print("done")

    def start_master(self):
        """
        Do the master start
        """
        cmd = "salt-master -c {} --pid-file {}".format(self.conf, f"{self.conf}.pid")
        if self.opts["foreground"]:
            cmd += " -l debug &"
        else:
            cmd += " -d &"
        subprocess.call(cmd, shell=True)

    def mkconf(self):  # pylint: disable=W0221
        """
        Make a master config and write it'
        """
        data = {}
        if self.opts["config_dir"]:
            spath = os.path.join(self.opts["config_dir"], "master")
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf)
        data.update(
            {
                "log_file": os.path.join(self.conf, "master.log"),
                "open_mode": True,  # TODO Pre-seed keys
            }
        )

        os.makedirs(self.conf)
        path = os.path.join(self.conf, "master")

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)

    def shutdown(self):
        print("Killing master")
        subprocess.call('pkill -KILL -f "python.*salt-master"', shell=True)
        print("Master killed")


# pylint: disable=C0103
if __name__ == "__main__":
    swarm = Swarm(parse())
    try:
        swarm.start()
    finally:
        swarm.shutdown()
