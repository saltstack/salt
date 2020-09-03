"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    ====================================
    Custom Salt TestCase Implementations
    ====================================

    Custom reusable :class:`TestCase<python2:unittest.TestCase>`
    implementations.
"""

import errno
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import datetime, timedelta

import pytest
import salt.utils.files
from saltfactories.utils.processes import terminate_process
from tests.support.cli_scripts import ScriptPathMixin
from tests.support.helpers import RedirectStdStreams
from tests.support.mixins import (  # pylint: disable=unused-import
    AdaptedConfigurationTestCaseMixin,
    SaltClientTestCaseMixin,
    SaltMultimasterClientTestCaseMixin,
)
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

STATE_FUNCTION_RUNNING_RE = re.compile(
    r"""The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID """
    r"(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)"
)

log = logging.getLogger(__name__)


class ShellCase(TestCase, AdaptedConfigurationTestCaseMixin, ScriptPathMixin):
    """
    Execute a test for a shell command
    """

    RUN_TIMEOUT = 30

    def run_salt(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        timeout=None,
        popen_kwargs=None,
        config_dir=None,
    ):
        r'''
        Run the ``salt`` CLI tool with the provided arguments

        .. code-block:: python

            class MatchTest(ShellCase):
                def test_list(self):
                    """
                    test salt -L matcher
                    """
                    data = self.run_salt('-L minion test.ping')
                    data = '\n'.join(data)
                    self.assertIn('minion', data)
        '''
        if timeout is None:
            timeout = self.RUN_TIMEOUT

        arg_str = "-t {} {}".format(timeout, arg_str)
        return self.run_script(
            "salt",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            timeout=timeout,
            config_dir=config_dir,
        )

    def run_ssh(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        timeout=None,
        wipe=False,
        raw=False,
        roster_file=None,
        ssh_opts="",
        log_level="error",
        config_dir=None,
        **kwargs
    ):
        """
        Execute salt-ssh
        """
        if timeout is None:
            timeout = self.RUN_TIMEOUT
        if not roster_file:
            roster_file = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "roster")
        arg_str = (
            "{wipe} {raw} -l {log_level} --ignore-host-keys --priv {client_key} --roster-file "
            "{roster_file} {ssh_opts} localhost {arg_str} --out=json"
        ).format(
            wipe=" -W" if wipe else "",
            raw=" -r" if raw else "",
            log_level=log_level,
            client_key=os.path.join(RUNTIME_VARS.TMP_SSH_CONF_DIR, "client_key"),
            roster_file=roster_file,
            ssh_opts=ssh_opts,
            arg_str=arg_str,
        )
        ret = self.run_script(
            "salt-ssh",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            raw=True,
            timeout=timeout,
            config_dir=config_dir,
            **kwargs
        )
        log.debug("Result of run_ssh for command '%s %s': %s", arg_str, kwargs, ret)
        return ret

    def run_run(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        asynchronous=False,
        timeout=None,
        config_dir=None,
        **kwargs
    ):
        """
        Execute salt-run
        """
        if timeout is None:
            timeout = self.RUN_TIMEOUT
        asynchronous = kwargs.get("async", asynchronous)
        arg_str = "{async_flag} -t {timeout} {}".format(
            arg_str, timeout=timeout, async_flag=" --async" if asynchronous else "",
        )
        ret = self.run_script(
            "salt-run",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            timeout=timeout,
            config_dir=config_dir,
        )
        log.debug("Result of run_run for command '%s': %s", arg_str, ret)
        return ret

    def run_run_plus(self, fun, *arg, **kwargs):
        """
        Execute the runner function and return the return data and output in a dict
        """
        output = kwargs.pop("_output", None)
        ret = {"fun": fun}

        # Late import
        import salt.config
        import salt.output
        import salt.runner

        opts = salt.config.client_config(self.get_config_file_path("master"))

        opts_arg = list(arg)
        if kwargs:
            opts_arg.append({"__kwarg__": True})
            opts_arg[-1].update(kwargs)

        opts.update({"doc": False, "fun": fun, "arg": opts_arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret["return"] = runner.run()
            try:
                ret["jid"] = runner.jid
            except AttributeError:
                ret["jid"] = None

        # Compile output
        # TODO: Support outputters other than nested
        opts["color"] = False
        opts["output_file"] = io.StringIO()
        try:
            salt.output.display_output(ret["return"], opts=opts, out=output)
            out = opts["output_file"].getvalue()
            if output is None:
                out = out.splitlines()
            elif output == "json":
                out = json.loads(out)
            ret["out"] = out
        finally:
            opts["output_file"].close()
        log.debug(
            "Result of run_run_plus for fun '%s' with arg '%s': %s", fun, opts_arg, ret
        )
        return ret

    def run_key(self, arg_str, catch_stderr=False, with_retcode=False, config_dir=None):
        """
        Execute salt-key
        """
        return self.run_script(
            "salt-key",
            arg_str,
            catch_stderr=catch_stderr,
            with_retcode=with_retcode,
            config_dir=config_dir,
        )

    def run_cp(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        timeout=None,
        config_dir=None,
    ):
        """
        Execute salt-cp
        """
        if timeout is None:
            timeout = self.RUN_TIMEOUT
        # Note: not logging result of run_cp because it will log a bunch of
        # bytes which will not be very helpful.
        return self.run_script(
            "salt-cp",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            timeout=timeout,
            config_dir=config_dir,
        )

    def run_call(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        local=False,
        timeout=None,
        config_dir=None,
    ):
        if timeout is None:
            timeout = self.RUN_TIMEOUT
        if not config_dir:
            config_dir = RUNTIME_VARS.TMP_MINION_CONF_DIR
        arg_str = "{} {}".format("--local" if local else "", arg_str)
        ret = self.run_script(
            "salt-call",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            timeout=timeout,
            config_dir=config_dir,
        )
        log.debug("Result of run_call for command '%s': %s", arg_str, ret)
        return ret

    def run_function(
        self,
        function,
        arg=(),
        with_retcode=False,
        catch_stderr=False,
        local=False,
        timeout=RUN_TIMEOUT,
        **kwargs
    ):
        """
        Execute function with salt-call.

        This function is added for compatibility with ModuleCase. This makes it possible to use
        decorators like @with_system_user.
        """
        arg_str = "{} {} {}".format(
            function,
            " ".join(str(arg_) for arg_ in arg),
            " ".join("{}={}".format(*item) for item in kwargs.items()),
        )
        return self.run_call(arg_str, with_retcode, catch_stderr, local, timeout)

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None, config_dir=None):
        """
        Execute salt-cloud
        """
        if timeout is None:
            timeout = self.RUN_TIMEOUT

        ret = self.run_script(
            "salt-cloud", arg_str, catch_stderr, timeout=timeout, config_dir=config_dir
        )
        log.debug("Result of run_cloud for command '%s': %s", arg_str, ret)
        return ret

    def run_spm(
        self,
        arg_str,
        with_retcode=False,
        catch_stderr=False,
        timeout=None,
        config_dir=None,
    ):
        """
        Execute spm
        """
        if timeout is None:
            timeout = self.RUN_TIMEOUT
        ret = self.run_script(
            "spm",
            arg_str,
            with_retcode=with_retcode,
            catch_stderr=catch_stderr,
            timeout=timeout,
            config_dir=config_dir,
        )
        log.debug("Result of run_spm for command '%s': %s", arg_str, ret)
        return ret

    def run_script(
        self,
        script,
        arg_str,
        catch_stderr=False,
        with_retcode=False,
        catch_timeout=False,
        # FIXME A timeout of zero or disabling timeouts may not return results!
        timeout=15,
        raw=False,
        popen_kwargs=None,
        log_output=None,
        config_dir=None,
        **kwargs
    ):
        """
        Execute a script with the given argument string

        The ``log_output`` argument is ternary, it can be True, False, or None.
        If the value is boolean, then it forces the results to either be logged
        or not logged. If it is None, then the return code of the subprocess
        determines whether or not to log results.
        """

        import salt.utils.platform

        script_path = self.get_script_path(script)
        if not os.path.isfile(script_path):
            return False
        popen_kwargs = popen_kwargs or {}

        if salt.utils.platform.is_windows():
            cmd = "python "
            if "cwd" not in popen_kwargs:
                popen_kwargs["cwd"] = os.getcwd()
            if "env" not in popen_kwargs:
                popen_kwargs["env"] = os.environ.copy()
                popen_kwargs["env"]["PYTHONPATH"] = RUNTIME_VARS.CODE_DIR
        else:
            cmd = "PYTHONPATH="
            python_path = os.environ.get("PYTHONPATH", None)
            if python_path is not None:
                cmd += "{}:".format(python_path)

            if sys.version_info[0] < 3:
                cmd += "{} ".format(":".join(sys.path[1:]))
            else:
                cmd += "{} ".format(":".join(sys.path[0:]))
            cmd += "python{}.{} ".format(*sys.version_info)
        cmd += "{} --config-dir={} {} ".format(
            script_path, config_dir or RUNTIME_VARS.TMP_CONF_DIR, arg_str
        )
        if kwargs:
            # late import
            import salt.utils.json

            for key, value in kwargs.items():
                cmd += "'{}={} '".format(key, salt.utils.json.dumps(value))

        tmp_file = tempfile.SpooledTemporaryFile()

        popen_kwargs = dict(
            {"shell": True, "stdout": tmp_file, "universal_newlines": True},
            **popen_kwargs
        )

        if catch_stderr is True:
            popen_kwargs["stderr"] = subprocess.PIPE

        if not sys.platform.lower().startswith("win"):
            popen_kwargs["close_fds"] = True

            def detach_from_parent_group():
                # detach from parent group (no more inherited signals!)
                os.setpgrp()

            popen_kwargs["preexec_fn"] = detach_from_parent_group

        def format_return(retcode, stdout, stderr=None, timed_out=False):
            """
            DRY helper to log script result if it failed, and then return the
            desired output based on whether or not stderr was desired, and
            wither or not a retcode was desired.
            """
            log_func = log.debug
            if timed_out:
                log.error(
                    "run_script timed out after %d seconds (process killed)", timeout
                )
                log_func = log.error

            if log_output is True or timed_out or (log_output is None and retcode != 0):
                log_func(
                    "run_script results for: %s %s\n"
                    "return code: %s\n"
                    "stdout:\n"
                    "%s\n\n"
                    "stderr:\n"
                    "%s",
                    script,
                    arg_str,
                    retcode,
                    stdout,
                    stderr,
                )

            stdout = stdout or ""
            stderr = stderr or ""

            if not raw:
                stdout = stdout.splitlines()
                stderr = stderr.splitlines()

            ret = [stdout]
            if catch_stderr:
                ret.append(stderr)
            if with_retcode:
                ret.append(retcode)
            if catch_timeout:
                ret.append(timed_out)

            return ret[0] if len(ret) == 1 else tuple(ret)

        log.debug("Running Popen(%r, %r)", cmd, popen_kwargs)
        process = subprocess.Popen(cmd, **popen_kwargs)

        if timeout is not None:
            stop_at = datetime.now() + timedelta(seconds=timeout)
            term_sent = False
            while True:
                process.poll()
                time.sleep(0.1)
                if datetime.now() <= stop_at:
                    # We haven't reached the timeout yet
                    if process.returncode is not None:
                        break
                else:
                    terminate_process(process.pid, kill_children=True)
                    return format_return(
                        process.returncode, *process.communicate(), timed_out=True
                    )

        tmp_file.seek(0)

        try:
            out = tmp_file.read().decode(__salt_system_encoding__)
        except (NameError, UnicodeDecodeError):
            # Let's cross our fingers and hope for the best
            out = tmp_file.read().decode("utf-8")

        if catch_stderr:
            if sys.version_info < (2, 7):
                # On python 2.6, the subprocess'es communicate() method uses
                # select which, is limited by the OS to 1024 file descriptors
                # We need more available descriptors to run the tests which
                # need the stderr output.
                # So instead of .communicate() we wait for the process to
                # finish, but, as the python docs state "This will deadlock
                # when using stdout=PIPE and/or stderr=PIPE and the child
                # process generates enough output to a pipe such that it
                # blocks waiting for the OS pipe buffer to accept more data.
                # Use communicate() to avoid that." <- a catch, catch situation
                #
                # Use this work around were it's needed only, python 2.6
                process.wait()
                err = process.stderr.read()
            else:
                _, err = process.communicate()
            # Force closing stderr/stdout to release file descriptors
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

            # pylint: disable=maybe-no-member
            try:
                return format_return(process.returncode, out, err or "")
            finally:
                try:
                    if os.path.exists(tmp_file.name):
                        if isinstance(tmp_file.name, str):
                            # tmp_file.name is an int when using SpooledTemporaryFiles
                            # int types cannot be used with os.remove() in Python 3
                            os.remove(tmp_file.name)
                        else:
                            # Clean up file handles
                            tmp_file.close()
                    process.terminate()
                except OSError as err:
                    # process already terminated
                    pass
            # pylint: enable=maybe-no-member

        # TODO Remove this?
        process.communicate()
        if process.stdout is not None:
            process.stdout.close()

        try:
            return format_return(process.returncode, out)
        finally:
            try:
                if os.path.exists(tmp_file.name):
                    if isinstance(tmp_file.name, str):
                        # tmp_file.name is an int when using SpooledTemporaryFiles
                        # int types cannot be used with os.remove() in Python 3
                        os.remove(tmp_file.name)
                    else:
                        # Clean up file handles
                        tmp_file.close()
                process.terminate()
            except OSError as err:
                # process already terminated
                pass


class MultiMasterTestShellCase(ShellCase):
    """
    '''
    Execute a test for a shell command when running multi-master tests
    """

    @property
    def config_dir(self):
        return RUNTIME_VARS.TMP_MM_CONF_DIR


class SPMTestUserInterface:
    """
    Test user interface to SPMClient
    """

    def __init__(self):
        self._status = []
        self._confirm = []
        self._error = []

    def status(self, msg):
        self._status.append(msg)

    def confirm(self, action):
        self._confirm.append(action)

    def error(self, msg):
        self._error.append(msg)


class SPMCase(TestCase, AdaptedConfigurationTestCaseMixin):
    """
    Class for handling spm commands
    """

    def _spm_build_files(self, config):
        self.formula_dir = os.path.join(
            " ".join(config["file_roots"]["base"]), "formulas"
        )
        self.formula_sls_dir = os.path.join(self.formula_dir, "apache")
        self.formula_sls = os.path.join(self.formula_sls_dir, "apache.sls")
        self.formula_file = os.path.join(self.formula_dir, "FORMULA")

        dirs = [self.formula_dir, self.formula_sls_dir]
        for f_dir in dirs:
            os.makedirs(f_dir)

        with salt.utils.files.fopen(self.formula_sls, "w") as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     install-apache:
                       pkg.installed:
                         - name: apache2
                     """
                )
            )

        with salt.utils.files.fopen(self.formula_file, "w") as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     name: apache
                     os: RedHat, Debian, Ubuntu, Suse, FreeBSD
                     os_family: RedHat, Debian, Suse, FreeBSD
                     version: 201506
                     release: 2
                     summary: Formula for installing Apache
                     description: Formula for installing Apache
                     """
                )
            )

    def _spm_config(self, assume_yes=True):
        self._tmp_spm = tempfile.mkdtemp()
        config = self.get_temp_config(
            "minion",
            **{
                "spm_logfile": os.path.join(self._tmp_spm, "log"),
                "spm_repos_config": os.path.join(self._tmp_spm, "etc", "spm.repos"),
                "spm_cache_dir": os.path.join(self._tmp_spm, "cache"),
                "spm_build_dir": os.path.join(self._tmp_spm, "build"),
                "spm_build_exclude": ["apache/.git"],
                "spm_db_provider": "sqlite3",
                "spm_files_provider": "local",
                "spm_db": os.path.join(self._tmp_spm, "packages.db"),
                "extension_modules": os.path.join(self._tmp_spm, "modules"),
                "file_roots": {"base": [self._tmp_spm]},
                "formula_path": os.path.join(self._tmp_spm, "salt"),
                "pillar_path": os.path.join(self._tmp_spm, "pillar"),
                "reactor_path": os.path.join(self._tmp_spm, "reactor"),
                "assume_yes": True if assume_yes else False,
                "force": False,
                "verbose": False,
                "cache": "localfs",
                "cachedir": os.path.join(self._tmp_spm, "cache"),
                "spm_repo_dups": "ignore",
                "spm_share_dir": os.path.join(self._tmp_spm, "share"),
            }
        )

        import salt.utils.yaml

        if not os.path.isdir(config["formula_path"]):
            os.makedirs(config["formula_path"])

        with salt.utils.files.fopen(os.path.join(self._tmp_spm, "spm"), "w") as fp:
            salt.utils.yaml.safe_dump(config, fp)

        return config

    def _spm_create_update_repo(self, config):

        build_spm = self.run_spm("build", self.config, self.formula_dir)

        c_repo = self.run_spm("create_repo", self.config, self.config["spm_build_dir"])

        repo_conf_dir = self.config["spm_repos_config"] + ".d"
        os.makedirs(repo_conf_dir)

        with salt.utils.files.fopen(os.path.join(repo_conf_dir, "spm.repo"), "w") as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     local_repo:
                       url: file://{}
                     """.format(
                        self.config["spm_build_dir"]
                    )
                )
            )

        u_repo = self.run_spm("update_repo", self.config)

    def _spm_client(self, config):
        import salt.spm

        self.ui = SPMTestUserInterface()
        client = salt.spm.SPMClient(self.ui, config)
        return client

    def run_spm(self, cmd, config, arg=None):
        client = self._spm_client(config)
        client.run([cmd, arg])
        client._close()
        return self.ui._status


class ModuleCase(TestCase, SaltClientTestCaseMixin):
    """
    Execute a module function
    """

    def wait_for_all_jobs(self, minions=("minion", "sub_minion",), sleep=0.3):
        """
        Wait for all jobs currently running on the list of minions to finish
        """
        for minion in minions:
            while True:
                ret = self.run_function(
                    "saltutil.running", minion_tgt=minion, timeout=300
                )
                if ret:
                    log.debug("Waiting for minion's jobs: %s", minion)
                    time.sleep(sleep)
                else:
                    break

    def minion_run(self, _function, *args, **kw):
        """
        Run a single salt function on the 'minion' target and condition
        the return down to match the behavior of the raw function call
        """
        return self.run_function(_function, args, **kw)

    def run_function(
        self,
        function,
        arg=(),
        minion_tgt="minion",
        timeout=300,
        master_tgt=None,
        **kwargs
    ):
        """
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        """
        known_to_return_none = (
            "data.get",
            "file.chown",
            "file.chgrp",
            "pkg.refresh_db",
            "ssh.recv_known_host_entries",
            "time.sleep",
            "grains.delkey",
            "grains.delval",
        )
        if "f_arg" in kwargs:
            kwargs["arg"] = kwargs.pop("f_arg")
        if "f_timeout" in kwargs:
            kwargs["timeout"] = kwargs.pop("f_timeout")
        client = self.client if master_tgt is None else self.clients[master_tgt]
        log.debug(
            "Running client.cmd(minion_tgt=%r, function=%r, arg=%r, timeout=%r, kwarg=%r)",
            minion_tgt,
            function,
            arg,
            timeout,
            kwargs,
        )
        orig = client.cmd(minion_tgt, function, arg, timeout=timeout, kwarg=kwargs)

        if RUNTIME_VARS.PYTEST_SESSION:
            fail_or_skip_func = self.fail
        else:
            fail_or_skip_func = self.skipTest

        if minion_tgt not in orig:
            fail_or_skip_func(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply "
                "from the minion '{}'. Command output: {}".format(minion_tgt, orig)
            )
        elif orig[minion_tgt] is None and function not in known_to_return_none:
            fail_or_skip_func(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get '{}' from "
                "the minion '{}'. Command output: {}".format(function, minion_tgt, orig)
            )

        # Try to match stalled state functions
        orig[minion_tgt] = self._check_state_return(orig[minion_tgt])

        return orig[minion_tgt]

    def run_state(self, function, **kwargs):
        """
        Run the state.single command and return the state return structure
        """
        ret = self.run_function("state.single", [function], **kwargs)
        return self._check_state_return(ret)

    def _check_state_return(self, ret):
        if isinstance(ret, dict):
            # This is the supposed return format for state calls
            return ret

        if isinstance(ret, list):
            jids = []
            # These are usually errors
            for item in ret[:]:
                if not isinstance(item, str):
                    # We don't know how to handle this
                    continue
                match = STATE_FUNCTION_RUNNING_RE.match(item)
                if not match:
                    # We don't know how to handle this
                    continue
                jid = match.group("jid")
                if jid in jids:
                    continue

                jids.append(jid)

                job_data = self.run_function("saltutil.find_job", [jid])
                job_kill = self.run_function("saltutil.kill_job", [jid])
                msg = (
                    "A running state.single was found causing a state lock. "
                    "Job details: '{}'  Killing Job Returned: '{}'".format(
                        job_data, job_kill
                    )
                )
                ret.append(
                    "[TEST SUITE ENFORCED]{}" "[/TEST SUITE ENFORCED]".format(msg)
                )
        return ret


class MultimasterModuleCase(ModuleCase, SaltMultimasterClientTestCaseMixin):
    """
    Execute a module function
    """

    def run_function(
        self,
        function,
        arg=(),
        minion_tgt="mm-minion",
        timeout=300,
        master_tgt="mm-master",
        **kwargs
    ):
        """
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        """
        known_to_return_none = (
            "data.get",
            "file.chown",
            "file.chgrp",
            "pkg.refresh_db",
            "ssh.recv_known_host_entries",
            "time.sleep",
        )
        if minion_tgt == "mm-sub-minion":
            known_to_return_none += ("mine.update",)
        if "f_arg" in kwargs:
            kwargs["arg"] = kwargs.pop("f_arg")
        if "f_timeout" in kwargs:
            kwargs["timeout"] = kwargs.pop("f_timeout")
        if master_tgt is None:
            client = self.clients["mm-master"]
        elif isinstance(master_tgt, int):
            client = self.clients[list(self.clients)[master_tgt]]
        else:
            client = self.clients[master_tgt]
        orig = client.cmd(minion_tgt, function, arg, timeout=timeout, kwarg=kwargs)

        if RUNTIME_VARS.PYTEST_SESSION:
            fail_or_skip_func = self.fail
        else:
            fail_or_skip_func = self.skipTest

        if minion_tgt not in orig:
            fail_or_skip_func(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply "
                "from the minion '{}'. Command output: {}".format(minion_tgt, orig)
            )
        elif orig[minion_tgt] is None and function not in known_to_return_none:
            fail_or_skip_func(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get '{}' from "
                "the minion '{}'. Command output: {}".format(function, minion_tgt, orig)
            )

        # Try to match stalled state functions
        orig[minion_tgt] = self._check_state_return(orig[minion_tgt])

        return orig[minion_tgt]

    def run_function_all_masters(
        self, function, arg=(), minion_tgt="mm-minion", timeout=300, **kwargs
    ):
        """
        Run a single salt function from all the masters in multimaster environment
        and condition the return down to match the behavior of the raw function call
        """
        ret = []
        for master_id in self.clients:
            ret.append(
                self.run_function(
                    function,
                    arg=arg,
                    minion_tgt=minion_tgt,
                    timeout=timeout,
                    master_tgt=master_id,
                    **kwargs
                )
            )
        return ret


class SyndicCase(TestCase, SaltClientTestCaseMixin):
    """
    Execute a syndic based execution test
    """

    _salt_client_config_file_name_ = "syndic_master"

    def run_function(self, function, arg=(), timeout=90):
        """
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        """
        orig = self.client.cmd("minion", function, arg, timeout=timeout)
        if RUNTIME_VARS.PYTEST_SESSION:
            fail_or_skip_func = self.fail
        else:
            fail_or_skip_func = self.skipTest
        if "minion" not in orig:
            fail_or_skip_func(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply "
                "from the minion. Command output: {}".format(orig)
            )
        return orig["minion"]


@pytest.mark.usefixtures("salt_ssh_cli")
@pytest.mark.requires_sshd_server
class SSHCase(ShellCase):
    """
    Execute a command via salt-ssh
    """

    def _arg_str(self, function, arg):
        return "{} {}".format(function, " ".join(arg))

    # pylint: disable=arguments-differ
    def run_function(
        self, function, arg=(), timeout=180, wipe=True, raw=False, **kwargs
    ):
        """
        We use a 180s timeout here, which some slower systems do end up needing
        """
        ret = self.run_ssh(
            self._arg_str(function, arg), timeout=timeout, wipe=wipe, raw=raw, **kwargs
        )
        log.debug(
            "SSHCase run_function executed %s with arg %s and kwargs %s",
            function,
            arg,
            kwargs,
        )
        log.debug("SSHCase JSON return: %s", ret)

        # Late import
        import salt.utils.json

        try:
            return salt.utils.json.loads(ret)["localhost"]
        except Exception:  # pylint: disable=broad-except
            return ret

    # pylint: enable=arguments-differ
    def custom_roster(self, new_roster, data):
        """
        helper method to create a custom roster to use for a ssh test
        """
        roster = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "roster")

        with salt.utils.files.fopen(roster, "r") as fp_:
            conf = salt.utils.yaml.safe_load(fp_)

        conf["localhost"].update(data)

        with salt.utils.files.fopen(new_roster, "w") as fp_:
            salt.utils.yaml.safe_dump(conf, fp_)


class ClientCase(AdaptedConfigurationTestCaseMixin, TestCase):
    """
    A base class containing relevant options for starting the various Salt
    Python API entrypoints
    """

    def get_opts(self):
        # Late import
        import salt.config

        return salt.config.client_config(self.get_config_file_path("master"))

    def mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise
