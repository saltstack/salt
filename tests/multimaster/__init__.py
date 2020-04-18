# -*- coding: utf-8 -*-

"""
Set up the Salt multimaster test suite
"""

# Import Python libs
from __future__ import absolute_import, print_function

import copy
import logging
import os
import shutil
import stat
import sys
import threading
import time
from collections import OrderedDict

import salt.config
import salt.log.setup as salt_log_setup
import salt.utils.path
import salt.utils.platform
from salt.utils.immutabletypes import freeze
from salt.utils.verify import verify_env

# Import Salt libs
from tests.integration import (
    SocketServerRequestHandler,
    TestDaemon,
    TestDaemonStartFailed,
    ThreadedSocketServer,
    get_unused_localhost_port,
)
from tests.support.parser import PNUM, print_header

# Import salt tests support dirs
from tests.support.paths import (
    ENGINES_DIR,
    FILES,
    INTEGRATION_TEST_DIR,
    LOG_HANDLERS_DIR,
    SCRIPT_DIR,
    TMP,
)

# Import salt tests support libs
from tests.support.processes import SaltMaster, SaltMinion, start_daemon
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


SALT_LOG_PORT = get_unused_localhost_port()


class MultimasterTestDaemon(TestDaemon):
    """
    Set up the master and minion daemons, and run related cases
    """

    def __enter__(self):
        """
        Start a master and minion
        """
        # Setup the multiprocessing logging queue listener
        salt_log_setup.setup_multiprocessing_logging_listener(self.mm_master_opts)

        # Set up PATH to mockbin
        self._enter_mockbin()

        self.master_targets = [self.mm_master_opts, self.mm_sub_master_opts]
        self.minion_targets = set(["mm-minion", "mm-sub-minion"])

        if self.parser.options.transport == "zeromq":
            self.start_zeromq_daemons()
        elif self.parser.options.transport == "raet":
            self.start_raet_daemons()
        elif self.parser.options.transport == "tcp":
            self.start_tcp_daemons()

        self.pre_setup_minions()
        self.setup_minions()

        # if getattr(self.parser.options, 'ssh', False):
        # self.prep_ssh()

        self.wait_for_minions(time.time(), self.MINIONS_CONNECT_TIMEOUT)

        if self.parser.options.sysinfo:
            try:
                print_header(
                    "~~~~~~~ Versions Report ",
                    inline=True,
                    width=getattr(self.parser.options, "output_columns", PNUM),
                )
            except TypeError:
                print_header("~~~~~~~ Versions Report ", inline=True)

            print("\n".join(salt.version.versions_report()))

            try:
                print_header(
                    "~~~~~~~ Minion Grains Information ",
                    inline=True,
                    width=getattr(self.parser.options, "output_columns", PNUM),
                )
            except TypeError:
                print_header("~~~~~~~ Minion Grains Information ", inline=True)

            grains = self.client.cmd("minion", "grains.items")

            minion_opts = self.mm_minion_opts.copy()
            minion_opts["color"] = self.parser.options.no_colors is False
            salt.output.display_output(grains, "grains", minion_opts)

        try:
            print_header(
                "=",
                sep="=",
                inline=True,
                width=getattr(self.parser.options, "output_columns", PNUM),
            )
        except TypeError:
            print_header("", sep="=", inline=True)

        try:
            return self
        finally:
            self.post_setup_minions()

    def __exit__(self, type, value, traceback):
        """
        Kill the minion and master processes
        """
        try:
            if hasattr(self.sub_minion_process, "terminate"):
                self.sub_minion_process.terminate()
            else:
                log.error("self.sub_minion_process can't be terminate.")
        except AttributeError:
            pass

        try:
            if hasattr(self.minion_process, "terminate"):
                self.minion_process.terminate()
            else:
                log.error("self.minion_process can't be terminate.")
        except AttributeError:
            pass

        try:
            if hasattr(self.sub_master_process, "terminate"):
                self.sub_master_process.terminate()
            else:
                log.error("self.sub_master_process can't be terminate.")
        except AttributeError:
            pass

        try:
            if hasattr(self.master_process, "terminate"):
                self.master_process.terminate()
            else:
                log.error("self.master_process can't be terminate.")
        except AttributeError:
            pass

        self._exit_mockbin()
        self._exit_ssh()
        # Shutdown the multiprocessing logging queue listener
        salt_log_setup.shutdown_multiprocessing_logging()
        salt_log_setup.shutdown_multiprocessing_logging_listener(daemonizing=True)
        # Shutdown the log server
        self.log_server.shutdown()
        self.log_server.server_close()
        self.log_server_process.join()

    def start_zeromq_daemons(self):
        """
        Fire up the daemons used for zeromq tests
        """
        self.log_server = ThreadedSocketServer(
            ("localhost", SALT_LOG_PORT), SocketServerRequestHandler
        )
        self.log_server_process = threading.Thread(target=self.log_server.serve_forever)
        self.log_server_process.start()
        try:
            sys.stdout.write(
                " * {LIGHT_YELLOW}Starting salt-master ... {ENDC}".format(**self.colors)
            )
            sys.stdout.flush()
            self.master_process = start_daemon(
                daemon_name="salt-master",
                daemon_id=self.mm_master_opts["id"],
                daemon_log_prefix="salt-master/{}".format(self.mm_master_opts["id"]),
                daemon_cli_script_name="master",
                daemon_config=self.mm_master_opts,
                daemon_config_dir=RUNTIME_VARS.TMP_MM_CONF_DIR,
                daemon_class=SaltMaster,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=120,
            )
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_GREEN}Starting salt-master ... STARTED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_RED}Starting salt-master ... FAILED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            raise TestDaemonStartFailed()

        # Clone the master key to sub-master's pki dir
        for keyfile in ("master.pem", "master.pub"):
            shutil.copyfile(
                os.path.join(self.mm_master_opts["pki_dir"], keyfile),
                os.path.join(self.mm_sub_master_opts["pki_dir"], keyfile),
            )

        try:
            sys.stdout.write(
                " * {LIGHT_YELLOW}Starting second salt-master ... {ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            self.sub_master_process = start_daemon(
                daemon_name="sub salt-master",
                daemon_id=self.mm_master_opts["id"],
                daemon_log_prefix="sub-salt-master/{}".format(
                    self.mm_sub_master_opts["id"]
                ),
                daemon_cli_script_name="master",
                daemon_config=self.mm_sub_master_opts,
                daemon_config_dir=RUNTIME_VARS.TMP_MM_SUB_CONF_DIR,
                daemon_class=SaltMaster,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=120,
            )
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_GREEN}Starting second salt-master ... STARTED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_RED}Starting second salt-master ... FAILED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            raise TestDaemonStartFailed()

        try:
            sys.stdout.write(
                " * {LIGHT_YELLOW}Starting salt-minion ... {ENDC}".format(**self.colors)
            )
            sys.stdout.flush()
            self.minion_process = start_daemon(
                daemon_name="salt-minion",
                daemon_id=self.mm_master_opts["id"],
                daemon_log_prefix="salt-minion/{}".format(self.mm_minion_opts["id"]),
                daemon_cli_script_name="minion",
                daemon_config=self.mm_minion_opts,
                daemon_config_dir=RUNTIME_VARS.TMP_MM_CONF_DIR,
                daemon_class=SaltMinion,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=120,
            )
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_GREEN}Starting salt-minion ... STARTED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_RED}Starting salt-minion ... FAILED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            raise TestDaemonStartFailed()

        try:
            sys.stdout.write(
                " * {LIGHT_YELLOW}Starting sub salt-minion ... {ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            self.sub_minion_process = start_daemon(
                daemon_name="sub salt-minion",
                daemon_id=self.mm_master_opts["id"],
                daemon_log_prefix="sub-salt-minion/{}".format(
                    self.mm_sub_minion_opts["id"]
                ),
                daemon_cli_script_name="minion",
                daemon_config=self.mm_sub_minion_opts,
                daemon_config_dir=RUNTIME_VARS.TMP_MM_SUB_CONF_DIR,
                daemon_class=SaltMinion,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=120,
            )
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_GREEN}Starting sub salt-minion ... STARTED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                "\r{0}\r".format(
                    " " * getattr(self.parser.options, "output_columns", PNUM)
                )
            )
            sys.stdout.write(
                " * {LIGHT_RED}Starting sub salt-minion ... FAILED!\n{ENDC}".format(
                    **self.colors
                )
            )
            sys.stdout.flush()
            raise TestDaemonStartFailed()

    start_tcp_daemons = start_zeromq_daemons

    def wait_for_minions(self, start, timeout, sleep=5):
        """
        Ensure all minions and masters (including sub-masters) are connected.
        """
        success = [False] * len(self.master_targets)
        while True:
            for num, client in enumerate(self.clients):
                if success[num]:
                    continue
                try:
                    ret = self.client.run_job("*", "test.ping")
                except salt.exceptions.SaltClientError:
                    ret = None
                if ret and "minions" not in ret:
                    continue
                if ret and sorted(ret["minions"]) == sorted(self.minion_targets):
                    success[num] = True
                    continue
            if all(success):
                break
            if time.time() - start >= timeout:
                raise RuntimeError("Ping Minions Failed")
            time.sleep(sleep)

    @property
    def clients(self):
        """
        Return a local client which will be used for example to ping and sync
        the test minions.

        This client is defined as a class attribute because its creation needs
        to be deferred to a latter stage. If created it on `__enter__` like it
        previously was, it would not receive the master events.
        """
        if "runtime_clients" not in RUNTIME_VARS.RUNTIME_CONFIGS:
            RUNTIME_VARS.RUNTIME_CONFIGS["runtime_clients"] = OrderedDict()

        runtime_clients = RUNTIME_VARS.RUNTIME_CONFIGS["runtime_clients"]
        for mopts in self.master_targets:
            if mopts["id"] in runtime_clients:
                continue
            runtime_clients[mopts["id"]] = salt.client.get_local_client(mopts=mopts)
        return runtime_clients

    @property
    def client(self):
        return self.clients["mm-master"]

    @classmethod
    def transplant_configs(cls, transport="zeromq"):
        os.makedirs(RUNTIME_VARS.TMP_MM_CONF_DIR)
        os.makedirs(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR)
        print(
            " * Transplanting multimaster configuration files to '{0}'".format(
                RUNTIME_VARS.TMP_CONF_DIR
            )
        )
        tests_known_hosts_file = os.path.join(
            RUNTIME_VARS.TMP_CONF_DIR, "salt_ssh_known_hosts"
        )

        # Primary master in multimaster environment
        master_opts = salt.config._read_conf_file(
            os.path.join(RUNTIME_VARS.CONF_DIR, "master")
        )
        master_opts.update(
            salt.config._read_conf_file(
                os.path.join(RUNTIME_VARS.CONF_DIR, "mm_master")
            )
        )
        master_opts["known_hosts_file"] = tests_known_hosts_file
        master_opts["cachedir"] = "cache"
        master_opts["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        master_opts["config_dir"] = RUNTIME_VARS.TMP_MM_CONF_DIR
        master_opts["root_dir"] = os.path.join(TMP, "rootdir-multimaster")
        master_opts["pki_dir"] = "pki"
        file_tree = {
            "root_dir": os.path.join(FILES, "pillar", "base", "file_tree"),
            "follow_dir_links": False,
            "keep_newline": True,
        }
        master_opts["ext_pillar"].append({"file_tree": file_tree})

        # Secondary master in multimaster environment
        sub_master_opts = salt.config._read_conf_file(
            os.path.join(RUNTIME_VARS.CONF_DIR, "master")
        )
        sub_master_opts.update(
            salt.config._read_conf_file(
                os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_master")
            )
        )
        sub_master_opts["known_hosts_file"] = tests_known_hosts_file
        sub_master_opts["cachedir"] = "cache"
        sub_master_opts["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        sub_master_opts["config_dir"] = RUNTIME_VARS.TMP_MM_SUB_CONF_DIR
        sub_master_opts["root_dir"] = os.path.join(TMP, "rootdir-sub-multimaster")
        sub_master_opts["pki_dir"] = "pki"
        sub_master_opts["ext_pillar"].append({"file_tree": copy.deepcopy(file_tree)})

        # Under windows we can't seem to properly create a virtualenv off of another
        # virtualenv, we can on linux but we will still point to the virtualenv binary
        # outside the virtualenv running the test suite, if that's the case.
        try:
            real_prefix = sys.real_prefix
            # The above attribute exists, this is a virtualenv
            if salt.utils.platform.is_windows():
                virtualenv_binary = os.path.join(
                    real_prefix, "Scripts", "virtualenv.exe"
                )
            else:
                # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
                # from within the virtualenv, we don't want that
                path = os.environ.get("PATH")
                if path is not None:
                    path_items = path.split(os.pathsep)
                    for item in path_items[:]:
                        if item.startswith(sys.base_prefix):
                            path_items.remove(item)
                    os.environ["PATH"] = os.pathsep.join(path_items)
                virtualenv_binary = salt.utils.path.which("virtualenv")
                if path is not None:
                    # Restore previous environ PATH
                    os.environ["PATH"] = path
                if not virtualenv_binary.startswith(real_prefix):
                    virtualenv_binary = None
            if virtualenv_binary and not os.path.exists(virtualenv_binary):
                # It doesn't exist?!
                virtualenv_binary = None
        except AttributeError:
            # We're not running inside a virtualenv
            virtualenv_binary = None

        # This minion connects to both masters
        minion_opts = salt.config._read_conf_file(
            os.path.join(RUNTIME_VARS.CONF_DIR, "minion")
        )
        minion_opts.update(
            salt.config._read_conf_file(
                os.path.join(RUNTIME_VARS.CONF_DIR, "mm_minion")
            )
        )
        minion_opts["cachedir"] = "cache"
        minion_opts["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        minion_opts["config_dir"] = RUNTIME_VARS.TMP_MM_CONF_DIR
        minion_opts["root_dir"] = os.path.join(TMP, "rootdir-multimaster")
        minion_opts["pki_dir"] = "pki"
        minion_opts["hosts.file"] = os.path.join(TMP, "rootdir", "hosts")
        minion_opts["aliases.file"] = os.path.join(TMP, "rootdir", "aliases")
        if virtualenv_binary:
            minion_opts["venv_bin"] = virtualenv_binary

        # This sub_minion also connects to both masters
        sub_minion_opts = salt.config._read_conf_file(
            os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
        )
        sub_minion_opts.update(
            salt.config._read_conf_file(
                os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_minion")
            )
        )
        sub_minion_opts["cachedir"] = "cache"
        sub_minion_opts["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        sub_minion_opts["config_dir"] = RUNTIME_VARS.TMP_MM_SUB_CONF_DIR
        sub_minion_opts["root_dir"] = os.path.join(TMP, "rootdir-sub-multimaster")
        sub_minion_opts["pki_dir"] = "pki"
        sub_minion_opts["hosts.file"] = os.path.join(TMP, "rootdir", "hosts")
        sub_minion_opts["aliases.file"] = os.path.join(TMP, "rootdir", "aliases")
        if virtualenv_binary:
            sub_minion_opts["venv_bin"] = virtualenv_binary

        if transport == "raet":
            master_opts["transport"] = "raet"
            master_opts["raet_port"] = 64506
            sub_master_opts["transport"] = "raet"
            sub_master_opts["raet_port"] = 64556
            minion_opts["transport"] = "raet"
            minion_opts["raet_port"] = 64510
            sub_minion_opts["transport"] = "raet"
            sub_minion_opts["raet_port"] = 64520
            # syndic_master_opts['transport'] = 'raet'

        if transport == "tcp":
            master_opts["transport"] = "tcp"
            sub_master_opts["transport"] = "tcp"
            minion_opts["transport"] = "tcp"
            sub_minion_opts["transport"] = "tcp"

        # Set up config options that require internal data
        master_opts["pillar_roots"] = sub_master_opts["pillar_roots"] = {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(FILES, "pillar", "base"),
            ]
        }
        minion_opts["pillar_roots"] = {
            "base": [
                RUNTIME_VARS.TMP_PILLAR_TREE,
                os.path.join(FILES, "pillar", "base"),
            ]
        }
        master_opts["file_roots"] = sub_master_opts["file_roots"] = {
            "base": [
                os.path.join(FILES, "file", "base"),
                # Let's support runtime created files that can be used like:
                #   salt://my-temp-file.txt
                RUNTIME_VARS.TMP_STATE_TREE,
            ],
            # Alternate root to test __env__ choices
            "prod": [
                os.path.join(FILES, "file", "prod"),
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
            ],
        }
        minion_opts["file_roots"] = {
            "base": [
                os.path.join(FILES, "file", "base"),
                # Let's support runtime created files that can be used like:
                #   salt://my-temp-file.txt
                RUNTIME_VARS.TMP_STATE_TREE,
            ],
            # Alternate root to test __env__ choices
            "prod": [
                os.path.join(FILES, "file", "prod"),
                RUNTIME_VARS.TMP_PRODENV_STATE_TREE,
            ],
        }
        master_opts.setdefault("reactor", []).append(
            {"salt/minion/*/start": [os.path.join(FILES, "reactor-sync-minion.sls")]}
        )
        for opts_dict in (master_opts, sub_master_opts):
            if "ext_pillar" not in opts_dict:
                opts_dict["ext_pillar"] = []
            if salt.utils.platform.is_windows():
                opts_dict["ext_pillar"].append(
                    {"cmd_yaml": "type {0}".format(os.path.join(FILES, "ext.yaml"))}
                )
            else:
                opts_dict["ext_pillar"].append(
                    {"cmd_yaml": "cat {0}".format(os.path.join(FILES, "ext.yaml"))}
                )

        # all read, only owner write
        autosign_file_permissions = (
            stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        )
        for opts_dict in (master_opts, sub_master_opts):
            # We need to copy the extension modules into the new master root_dir or
            # it will be prefixed by it
            new_extension_modules_path = os.path.join(
                opts_dict["root_dir"], "extension_modules"
            )
            if not os.path.exists(new_extension_modules_path):
                shutil.copytree(
                    os.path.join(INTEGRATION_TEST_DIR, "files", "extension_modules"),
                    new_extension_modules_path,
                )
            opts_dict["extension_modules"] = os.path.join(
                opts_dict["root_dir"], "extension_modules"
            )

            # Copy the autosign_file to the new  master root_dir
            new_autosign_file_path = os.path.join(
                opts_dict["root_dir"], "autosign_file"
            )
            shutil.copyfile(
                os.path.join(INTEGRATION_TEST_DIR, "files", "autosign_file"),
                new_autosign_file_path,
            )
            os.chmod(new_autosign_file_path, autosign_file_permissions)

        # Point the config values to the correct temporary paths
        for name in ("hosts", "aliases"):
            optname = "{0}.file".format(name)
            optname_path = os.path.join(TMP, name)
            master_opts[optname] = optname_path
            sub_master_opts[optname] = optname_path
            minion_opts[optname] = optname_path
            sub_minion_opts[optname] = optname_path

        master_opts["runtests_conn_check_port"] = get_unused_localhost_port()
        sub_master_opts["runtests_conn_check_port"] = get_unused_localhost_port()
        minion_opts["runtests_conn_check_port"] = get_unused_localhost_port()
        sub_minion_opts["runtests_conn_check_port"] = get_unused_localhost_port()

        for conf in (master_opts, sub_master_opts, minion_opts, sub_minion_opts):
            if "engines" not in conf:
                conf["engines"] = []
            conf["engines"].append({"salt_runtests": {}})

            if "engines_dirs" not in conf:
                conf["engines_dirs"] = []

            conf["engines_dirs"].insert(0, ENGINES_DIR)

            if "log_handlers_dirs" not in conf:
                conf["log_handlers_dirs"] = []
            conf["log_handlers_dirs"].insert(0, LOG_HANDLERS_DIR)
            conf["runtests_log_port"] = SALT_LOG_PORT
            conf["runtests_log_level"] = (
                os.environ.get("TESTS_MIN_LOG_LEVEL_NAME") or "debug"
            )

        # ----- Transcribe Configuration ---------------------------------------------------------------------------->
        computed_config = copy.deepcopy(master_opts)
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_MM_CONF_DIR, "master"), "w"
        ) as wfh:
            salt.utils.yaml.safe_dump(
                copy.deepcopy(master_opts), wfh, default_flow_style=False
            )
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR, "master"), "w"
        ) as wfh:
            salt.utils.yaml.safe_dump(
                copy.deepcopy(sub_master_opts), wfh, default_flow_style=False
            )
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_MM_CONF_DIR, "minion"), "w"
        ) as wfh:
            salt.utils.yaml.safe_dump(
                copy.deepcopy(minion_opts), wfh, default_flow_style=False
            )
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR, "minion"), "w"
        ) as wfh:
            salt.utils.yaml.safe_dump(
                copy.deepcopy(sub_minion_opts), wfh, default_flow_style=False
            )
        # <---- Transcribe Configuration -----------------------------------------------------------------------------

        # ----- Verify Environment ---------------------------------------------------------------------------------->
        master_opts = salt.config.master_config(
            os.path.join(RUNTIME_VARS.TMP_MM_CONF_DIR, "master")
        )
        sub_master_opts = salt.config.master_config(
            os.path.join(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR, "master")
        )
        minion_opts = salt.config.minion_config(
            os.path.join(RUNTIME_VARS.TMP_MM_CONF_DIR, "minion")
        )
        sub_minion_opts = salt.config.minion_config(
            os.path.join(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR, "minion")
        )

        RUNTIME_VARS.RUNTIME_CONFIGS["mm_master"] = freeze(master_opts)
        RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_master"] = freeze(sub_master_opts)
        RUNTIME_VARS.RUNTIME_CONFIGS["mm_minion"] = freeze(minion_opts)
        RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_minion"] = freeze(sub_minion_opts)

        verify_env(
            [
                os.path.join(master_opts["pki_dir"], "minions"),
                os.path.join(master_opts["pki_dir"], "minions_pre"),
                os.path.join(master_opts["pki_dir"], "minions_rejected"),
                os.path.join(master_opts["pki_dir"], "minions_denied"),
                os.path.join(master_opts["cachedir"], "jobs"),
                os.path.join(master_opts["cachedir"], "raet"),
                os.path.join(master_opts["root_dir"], "cache", "tokens"),
                os.path.join(master_opts["pki_dir"], "accepted"),
                os.path.join(master_opts["pki_dir"], "rejected"),
                os.path.join(master_opts["pki_dir"], "pending"),
                os.path.join(master_opts["cachedir"], "raet"),
                os.path.join(sub_master_opts["pki_dir"], "minions"),
                os.path.join(sub_master_opts["pki_dir"], "minions_pre"),
                os.path.join(sub_master_opts["pki_dir"], "minions_rejected"),
                os.path.join(sub_master_opts["pki_dir"], "minions_denied"),
                os.path.join(sub_master_opts["cachedir"], "jobs"),
                os.path.join(sub_master_opts["cachedir"], "raet"),
                os.path.join(sub_master_opts["root_dir"], "cache", "tokens"),
                os.path.join(sub_master_opts["pki_dir"], "accepted"),
                os.path.join(sub_master_opts["pki_dir"], "rejected"),
                os.path.join(sub_master_opts["pki_dir"], "pending"),
                os.path.join(sub_master_opts["cachedir"], "raet"),
                os.path.join(minion_opts["pki_dir"], "accepted"),
                os.path.join(minion_opts["pki_dir"], "rejected"),
                os.path.join(minion_opts["pki_dir"], "pending"),
                os.path.join(minion_opts["cachedir"], "raet"),
                os.path.join(sub_minion_opts["pki_dir"], "accepted"),
                os.path.join(sub_minion_opts["pki_dir"], "rejected"),
                os.path.join(sub_minion_opts["pki_dir"], "pending"),
                os.path.join(sub_minion_opts["cachedir"], "raet"),
                os.path.dirname(master_opts["log_file"]),
                minion_opts["extension_modules"],
                sub_minion_opts["extension_modules"],
                sub_minion_opts["pki_dir"],
                master_opts["sock_dir"],
                sub_master_opts["sock_dir"],
                sub_minion_opts["sock_dir"],
                minion_opts["sock_dir"],
            ],
            RUNTIME_VARS.RUNNING_TESTS_USER,
            root_dir=master_opts["root_dir"],
        )

        cls.mm_master_opts = master_opts
        cls.mm_sub_master_opts = sub_master_opts
        cls.mm_minion_opts = minion_opts
        cls.mm_sub_minion_opts = sub_minion_opts
        # <---- Verify Environment -----------------------------------------------------------------------------------

    @classmethod
    def config_location(cls):
        return (RUNTIME_VARS.TMP_MM_CONF_DIR, RUNTIME_VARS.TMP_MM_SUB_CONF_DIR)
