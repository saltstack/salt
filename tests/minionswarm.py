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
import getpass

import salt.utils.files
import salt.utils.yaml
import support.runtests

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
    "3006.1",
    "3006.5",
    "3006.9",
    "3007.1",
]

def parse():
    """
    Parse the cli options
    """
    guidance = (
    	"\n\n   To execute salt commands against minionswarm you must include the configuration\n"
    	"   file using the -c option. For commands such as salt, salt-key, salt-cp,\n"
    	"   and salt-run use -c <temp-dir>/master. For example, when using the\n"
    	"   default for --temp-dir, the configuration directory would be\n"
    	"   /tmp/sroot/master. If the master runs on a different machine you\n"
    	"   must execute the command on that machine using the master config file\n"
    	"   there. For the salt-call command, which is a minion side\n"
    	"   command, use -c <tmp-dir>/<name>-<minion number>. For example to\n"
    	"   execute salt-call on the first minion using the default values for\n"
    	"   temp-dir and name use -c /tmp/sroot/minion-0. The commands salt-api,\n"
    	"   salt-cloud, salt-extend, salt-master, salt-minion, salt-proxy,\n"
    	"   salt-ssh, salt-syndic and spm are not supported."
    )
    usage = "usage: python %prog [options]" + guidance
    parser = optparse.OptionParser(usage)
    parser.add_option(
        "-m",
        "--minions",
        dest="minions",
        default=5,
        type="int",
        help="The number of minions to make (default = 5)",
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
        default="localhost",
        help="The location of the salt master that this swarm will serve. (default = localhost) "
             "The standard port used by daemon masters is 4506. Masters can be specified using "
             "<IP address>:<port>. For example, 192.168.1.2:4506",
    )
    parser.add_option(
        "--name",
        "-n",
        dest="name",
        default="minion",
        help="Give the minions an alternative id prefix, this is used "
            "when minions from many systems are being aggregated onto "
            "a single master. (default = minion)",
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
        help="A comma delimited list of modules to enable. (default = None)",
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
        default="/tmp/sroot",
        help="Place temporary files/directories here, (default = /tmp/sroot)",
    )
    parser.add_option(
        "--no-clean",
        action="store_true",
        default=False,
        help="Don't cleanup temporary files/directories. "
             "If specified, you must manually recursively delete "
             "the swarm root (see --temp-dir) before running "
             "minionswarm again, e.g., using the default swarm "
             "root, rm -fr /tmp/srooot",
    )
    parser.add_option(
        "--root-dir",
        dest="root_dir",
        default=None,
        help="Override the minion root_dir config. (default = None)",
    )
    parser.add_option(
        "--transport",
        dest="transport",
        default="zeromq",
        help="Declare which transport to use, (default = zeromq). Currently, "
             "tcp/TLS and ws/TLS are not supported, since they require the "
             "establishment of a certificate infrastructure and use of PKI "
             "keys manaaged by that infrastructure."
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
        help="Pass in a configuration directory containing base configuration. "
             "If a configuration directory is specified, at a minimum, it must "
             "have a master and minion configuration file and these files "
             "must not be empty. For example, each could have a user: <username> "
             "entry."
    )
    parser.add_option(
        "--open-mode",
        dest="open_mode",
        default=True,
        help="Turn off authentication at the Master. Default is True to align "
             "this version of minionswarm with previous version."
    )
    parser.add_option("-u", "--user", default=support.runtests.this_user())

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
        username = getpass.getuser()
        for path in self.confs:
            cmd = "salt-minion -c {} --user={} --pid-file {}".format(path, username, f"{path}.pid")
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
            data.update({"pki_dir": minion_pkidir})
        elif self.opts["transport"] == "tcp":
            data.update({"transport": "tcp"})

        if self.opts["root_dir"]:
            data.update({"root_dir": self.opts["root_dir"]})

        path = os.path.join(dpath, "minion")

        if self.opts["keep"]:
            keep = self.opts["keep"].split(",")
            modpath = os.path.join(os.path.dirname(salt.__file__), "modules")
            fn_prefixes = (fn_.partition(".")[0] for fn_ in os.listdir(modpath))
            ignore = [fn_prefix for fn_prefix in fn_prefixes if fn_prefix not in keep]
            data.update({"disable_modules": ignore})

        if self.opts["rand_os"]:
            data["grains"]["os"] = random.choice(OSES)
        if self.opts["rand_ver"]:
            data["grains"]["saltversion"] = random.choice(VERS)
        if self.opts["rand_machine_id"]:
            try:
                minion_id_encode = minion_id.encode(encoding="utf-8", errors="strict")
                data["grains"]["machine_id"] = hashlib.md5(minion_id_encode).hexdigest()
            except UnicodeEncodeError:
                print("\n'minion id contains illegal character. Shutting down.")
                sys.exit([1])
            data["grains"]["machine_id"] = hashlib.md5(minion_id_encode).hexdigest()
        if self.opts["rand_uuid"]:
            data["grains"]["uuid"] = str(uuid.uuid4())

        data = self._update_minion_conf(data)

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)
        self.confs.add(dpath)

    def _update_minion_conf(self, data):  # pylint: disable=W0221
        """
        Modify the minion config to contain cachedir and sock_dir definitions. Unless cachedir and sock_dir
        are modified as indicated, alt-master will think they are /var/cache/salt and /var/run/salt/master,
        respectively, which generally will not exist. Also, specify the extmods directory path and the
        pki/minion directory path.
        """

        cachdir_path = os.path.join(self.swarm_root, "var/cache/salt/minion")
        sock_dir_path = os.path.join(self.swarm_root, "var/run/salt/minion")
        extension_modules_dir_path = os.path.join(self.swarm_root, "var/cache/salt/minion/extmods")
        pki_dir_path = os.path.join(self.swarm_root, "etc/salt/pki/minion")

        try:
            os.makedirs(cachdir_path)
        except FileExistsError:
            # directory already exists
            pass
        try:
            os.makedirs(sock_dir_path)
        except FileExistsError:
            # directory already exists
            pass

        data.update(
            {
                "cachedir": cachdir_path,
                "sock_dir": sock_dir_path,
                "extension_modules" : extension_modules_dir_path,
                "pki_dir": pki_dir_path,
            }
        )
        return data

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
        Do the master start.. Run the master as the user under which minionswarm runs.
	"""

        username = getpass.getuser()
        cmd = "salt-master '--config-dir={}' --user={} --pid-file {}".format(self.conf, username, f"{self.conf}.pid")
        if self.opts["foreground"]:
            cmd += " -l debug &"
        else:
            cmd += " -d &"
        subprocess.call(cmd, shell=True)

    def mkconf(self):  # pylint: disable=W0221
        """
        Make the config file with standard values
        """

        data = {}
        if self.opts["config_dir"]:
            spath = os.path.join(self.opts["config_dir"], "master")
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf)
        head, tail = os.path.split(self.conf)
        if self.opts["transport"] == "tcp":
            data.update({"transport": "tcp"})
        data.update(
            {
                "log_file": os.path.join(self.conf, "master.log"),
                "pki_dir": os.path.join(head, "pki"),
            }
        )
        data.update({"open_mode": self.opts["open_mode"]})

        # TODO Pre-seed keys

        os.makedirs(self.conf)
        path = os.path.join(self.conf, "master")

        data = self._update_master_conf(data)

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)

    def _update_master_conf(self, data):  # pylint: disable=W0221
        """
        Modify the master config to contain cachedir and sock_dir definitions. Unless cachedir and sock_dir
        are modified as indicated, alt-master will think they are /var/cache/salt and /var/run/salt/master,
        respectively, which generally will not exist.
        """

        key_logfile_path = os.path.join(self.swarm_root, "var/log/salt/key")
        cachdir_path = os.path.join(self.swarm_root, "var/cache/salt/master")
        sock_dir_path = os.path.join(self.swarm_root, "var/run/salt/minion")
        sqlite_queue_dir_path = os.path.join(self.swarm_root, "var/cache/salt/master")

        try:
            os.makedirs(cachdir_path)
        except FileExistsError:
            # directory already exists
            pass
        try:
            os.makedirs(sock_dir_path)
        except FileExistsError:
            # directory already exists
            pass

        data.update(
            {
                "key_logfile": key_logfile_path,
                "cachedir": cachdir_path,
                "sock_dir": sock_dir_path,
                "sqlite_queue_dir" : sqlite_queue_dir_path,
            }
        )

        return data

    def shutdown(self):
        """
        Shutdown master
        """

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
