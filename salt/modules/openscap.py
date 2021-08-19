"""
Module for OpenSCAP Management
"""


import os.path
import shlex
import shutil
import tempfile
from subprocess import PIPE, Popen

import salt.utils.files
import salt.utils.path
from salt.exceptions import ArgumentValueError
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS
from salt.utils.decorators import is_deprecated, with_deprecated

# These pieces are kept in during the deprecation period.
ArgumentParser = object

try:
    import argparse  # pylint: disable=minimum-python-version

    ArgumentParser = argparse.ArgumentParser
    HAS_ARGPARSE = True
except ImportError:  # python 2.6
    HAS_ARGPARSE = False

_XCCDF_MAP = {
    "eval": {
        "parser_arguments": [(("--profile",), {"required": True})],
        "cmd_pattern": (
            "oscap xccdf eval "
            "--oval-results --results results.xml --report report.html "
            "--profile {0} {1}"
        ),
    }
}


class _ArgumentParser(ArgumentParser):
    def __init__(self, action=None, *args, **kwargs):
        super().__init__(*args, prog="oscap", **kwargs)
        self.add_argument("action", choices=["eval"])
        for params, kwparams in _XCCDF_MAP["eval"]["parser_arguments"]:
            self.add_argument(*params, **kwparams)

    def error(self, message, *args, **kwargs):
        raise Exception(message)


# End of deprecation compatibility.

# this has to stay after deprecated code is removed.
error = None


_OSCAP_EXIT_CODES_MAP = {
    0: True,  # all rules pass
    1: False,  # there is an error during evaluation
    2: True,  # there is at least one rule with either fail or unknown result
}


def __virtual__():
    """
    Only load the module if oscap is installed
    """
    if not salt.utils.path.which("oscap"):
        return (
            False,
            "The oscap execution module cannot be loaded: OpenSCAP not installed.",
        )

    return True


def _oscap_cmd():
    """Return correct command for openscap.

    Returns:
        string: Path of oscap binary
    """
    return salt.utils.path.which("oscap")


def _has_operation(module, operation):
    """Check if the given operation is supported by the module.

    Args:
        module (string): Name of the module.
        operation (string): Name of the operation

    Returns:
        boolean: Return true, if the operation is supported. Otherwhise false.
    """

    cmd = "{} {} -h".format(_oscap_cmd(), module)
    if operation in __salt__["cmd.run"](cmd, output_loglevel="quiet"):
        return True
    return False


def _has_param(mod_op, param):
    """Check if the given parameter is supported by the module.

    Args:
        module (string): Name if the Module
        operation (string): Name of the Modules Operation

    Returns:
        boolean: Value that determines, if an operation is available inside a module.
    """

    cmd = "{} {} -h".format(_oscap_cmd(), mod_op)
    if param in __salt__["cmd.run"](cmd, output_loglevel="quiet"):
        return True
    return False


def _build_cmd(module="", operation="", **kwargs):
    """Build a well-formed command to execute on the system.

    Args:
        module (str): Module Name.
        operation (str): Name of the operation.

    Returns:
        string: Command
    """
    for ignore in list(_STATE_INTERNAL_KEYWORDS) + ["--upload-to-master"]:
        if ignore in kwargs:
            del kwargs[ignore]

    cmd = "{}".format(_oscap_cmd())
    _mod_op = "{}".format(module)
    if len(operation) > 0:
        if not _has_operation(module, operation):
            raise ArgumentValueError(
                "'{}' does not support '{}' operation!".format(module, operation)
            )
        _mod_op = "{} {}".format(module, operation)
        cmd = cmd + " {}".format(_mod_op)
    else:
        cmd = cmd + " {}".format(_mod_op)

    for _key, _value in kwargs.items():
        if not _has_param(_mod_op, _key):
            raise ArgumentValueError(
                "'{}' does not support '{}' parameter!".format(_mod_op, _key)
            )

        if kwargs[_key] is True:
            cmd = cmd + " --{}".format(_key)
        else:
            cmd = cmd + " --{} {}".format(_key, _value)
    return cmd


def _upload_to_master(path):
    """
    Upload given directory to master

    Args:
        path (string): Path to upload to master

    Returns:
        boolean: True, if upload was successful.
    """
    if __salt__["cp.push_dir"](path):
        return True
    return False


def version(*args):
    """
    Show the version of the installed oscap package

    Usage:

    .. code-block:: bash

        salt '*' oscap.version

    :param full: Show full version information output.

    :return: a dict with the version information
    """
    cmd = "{} --version".format(_oscap_cmd())
    _version = __salt__["cmd.run"](cmd)

    # Output beautifications
    _resdict = {}
    _prep_version = _version.split("\n")
    while "" in _prep_version:
        _prep_version.remove("")

    _clean_version = _prep_version[2:]

    # Split the version information based on the section they are in.
    KEY_RULES = {
        "Supported specifications": {"split_at": ": "},
        "Capabilities added by auto-loaded plugins": {"split_at": ": "},
        "Paths": {"split_at": ": "},
        "Inbuilt CPE names": {"split_at": " - "},
    }

    for line in _clean_version:
        if line.startswith("===="):
            _head = line.strip("=")[1:-1]
            _resdict[_head] = {}
            continue

        if _head == "Supported OVAL objects and associated OpenSCAP probes":
            if line.startswith("OVAL") or line.startswith("---"):
                continue
            _line = line.split(" ")
            while "" in _line:
                _line.remove("")
            _resdict[_head][_line[0]] = {
                "OVAL object": _line[1],
                "OpenSCAP probe": _line[2],
            }
            continue

        _key = line.split(KEY_RULES[_head]["split_at"])[0]
        _value = line.split(KEY_RULES[_head]["split_at"])[1]
        _resdict[_head][_key] = _value

    _bin = _oscap_cmd().split("/")[-1]
    short_version = {"{}".format(_bin): _prep_version[0].split(" ")[-1]}
    if "full" in args:
        _resdict.update(short_version)
        return _resdict

    # Default return
    return short_version


@with_deprecated(globals(), "Phosphorus", with_name="_xccdf")
def xccdf(file="", operation="eval", upload=True, **kwargs):
    """
    Run ``oscap xccdf`` commands on minions.
    It uses ``cp.push_dir`` to upload the generated files to the salt master.
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)


    :param file: Target File to evaluate the system.
    :param operation: (Optional) Operation of ``xccdf`` Module. Defaults to "eval".
    :param upload: Upload results to Master. Defaults to True. It will automatically add and set the parameters 'oval-results', 'report' and, 'results'.

    :return: a dict with the execution results.

    CLI Example:

    `` salt '*' openscap.xccdf file="/usr/share/openscap/scap-yast2sec-xccdf.xml" profile="defautlt"``
    """
    if not file:
        return "A File must be defined!"

    _upload_flag = upload
    if _upload_flag is True:
        _tmp_path = tempfile.mkdtemp()
        if "oval-results" not in kwargs.keys():
            kwargs["oval-results"] = True

        kwargs["results"] = "{}/results.xml".format(_tmp_path)
        kwargs["report"] = "{}/report.html".format(_tmp_path)

    _cmd = _build_cmd("xccdf", operation, **kwargs)
    cmd = _cmd + " {}".format(file)

    _retcode = __salt__["cmd.retcode"](cmd)

    # No need to upload anything, if openscap itself failed.
    if _retcode == 1:
        _upload_flag = False

    _upload_path = None
    if _upload_flag and _upload_to_master(_tmp_path):
        _upload_path = _tmp_path

    _results = {
        "success": _OSCAP_EXIT_CODES_MAP[_retcode],
        "upload_dir": _upload_path,
        "error": None,
        "returncode": _retcode,
    }
    return _results


@is_deprecated(globals(), version="Phosphorus", with_successor="xccdf")
def _xccdf(params):
    """
    Run ``oscap xccdf`` commands on minions.
    It uses cp.push_dir to upload the generated files to the salt master
    in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)
    It needs ``file_recv`` set to ``True`` in the master configuration file.
    CLI Example:
    .. code-block:: bash
        salt '*' openscap.xccdf "eval --profile Default /usr/share/openscap/scap-yast2sec-xccdf.xml"
    """
    params = shlex.split(params)
    policy = params[-1]

    success = True
    error = None
    upload_dir = None
    action = None
    returncode = None

    try:
        parser = _ArgumentParser()
        action = parser.parse_known_args(params)[0].action
        args, argv = _ArgumentParser(action=action).parse_known_args(args=params)
    except Exception as err:  # pylint: disable=broad-except
        success = False
        error = str(err)

    if success:
        cmd = _XCCDF_MAP[action]["cmd_pattern"].format(args.profile, policy)
        tempdir = tempfile.mkdtemp()
        proc = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE, cwd=tempdir)
        (stdoutdata, error) = proc.communicate()
        success = _OSCAP_EXIT_CODES_MAP.get(proc.returncode, False)
        if proc.returncode < 0:
            error += "\nKilled by signal {}\n".format(proc.returncode).encode("ascii")
        returncode = proc.returncode
        if success:
            __salt__["cp.push_dir"](tempdir)
            shutil.rmtree(tempdir, ignore_errors=True)
            upload_dir = tempdir

    return dict(
        success=success, upload_dir=upload_dir, error=error, returncode=returncode
    )


def xccdf_eval(xccdffile, ovalfiles=None, **kwargs):
    """
    Run ``oscap xccdf eval`` commands on minions.
    It uses cp.push_dir to upload the generated files to the salt master
    in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)
    It needs ``file_recv`` set to ``True`` in the master configuration file.
    xccdffile
        the path to the xccdf file to evaluate
    ovalfiles
        additional oval definition files
    profile
        the name of Profile to be evaluated
    rule
        the name of a single rule to be evaluated
    oval_results
        save OVAL results as well (True or False)
    results
        write XCCDF Results into given file
    report
        write HTML report into given file
    fetch_remote_resources
        download remote content referenced by XCCDF (True or False)
    tailoring_file
        use given XCCDF Tailoring file
    tailoring_id
        use given DS component as XCCDF Tailoring file
    remediate
        automatically execute XCCDF fix elements for failed rules.
        Use of this option is always at your own risk. (True or False)
    CLI Example:
    .. code-block:: bash
        salt '*'  openscap.xccdf_eval /usr/share/openscap/scap-yast2sec-xccdf.xml profile=Default
    """
    success = True
    error = None
    upload_dir = None
    returncode = None
    if not ovalfiles:
        ovalfiles = []

    cmd_opts = ["oscap", "xccdf", "eval"]
    if kwargs.get("oval_results"):
        cmd_opts.append("--oval-results")
    if "results" in kwargs:
        cmd_opts.append("--results")
        cmd_opts.append(kwargs["results"])
    if "report" in kwargs:
        cmd_opts.append("--report")
        cmd_opts.append(kwargs["report"])
    if "profile" in kwargs:
        cmd_opts.append("--profile")
        cmd_opts.append(kwargs["profile"])
    if "rule" in kwargs:
        cmd_opts.append("--rule")
        cmd_opts.append(kwargs["rule"])
    if "tailoring_file" in kwargs:
        cmd_opts.append("--tailoring-file")
        cmd_opts.append(kwargs["tailoring_file"])
    if "tailoring_id" in kwargs:
        cmd_opts.append("--tailoring-id")
        cmd_opts.append(kwargs["tailoring_id"])
    if kwargs.get("fetch_remote_resources"):
        cmd_opts.append("--fetch-remote-resources")
    if kwargs.get("remediate"):
        cmd_opts.append("--remediate")
    cmd_opts.append(xccdffile)
    cmd_opts.extend(ovalfiles)

    if not os.path.exists(xccdffile):
        success = False
        error = "XCCDF File '{}' does not exist".format(xccdffile)
    for ofile in ovalfiles:
        if success and not os.path.exists(ofile):
            success = False
            error = "Oval File '{}' does not exist".format(ofile)

    if success:
        tempdir = tempfile.mkdtemp()
        proc = Popen(cmd_opts, stdout=PIPE, stderr=PIPE, cwd=tempdir)
        (stdoutdata, error) = proc.communicate()
        success = _OSCAP_EXIT_CODES_MAP.get(proc.returncode, False)
        if proc.returncode < 0:
            error += "\nKilled by signal {}\n".format(proc.returncode).encode("ascii")
        returncode = proc.returncode
        if success:
            __salt__["cp.push_dir"](tempdir)
            upload_dir = tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

    return dict(
        success=success, upload_dir=upload_dir, error=error, returncode=returncode
    )
