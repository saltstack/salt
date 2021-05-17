"""
Module for OpenSCAP Management
"""


import tempfile

import salt.utils.files
import salt.utils.path
from salt.exceptions import ArgumentValueError
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

_OSCAP_EXIT_CODES_MAP = {
    0: True,  # all rules pass
    1: False,  # there is an error during evaluation
    2: True,  # there is at least one rule with either fail or unknown result
}

# Kept in for compatibility
error = None


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
    """Upload given directory to Master

    Args:
        path (string): Path to upload to master

    Returns:
        boolean: True, if upload was successful.
    """
    if __salt__["cp.push_dir"](path):
        return True
    return False


def version(*args):
    """Show the version of installed oscap package

    Args:
        full: Show long version information output. 

    Returns:
        dict: Version information
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

    if "full" in args:
        return _resdict

    # Default return
    _bin = _oscap_cmd().split("/")[-1]
    return {"{}".format(_bin): _prep_version[0].split(" ")[-1]}


def xccdf(file="", operation="eval", upload=True, **kwargs):
    """[summary]

    Args:
        file (str): Target File with to evaluate the system.
        operation (str, optional): Operation of Module. Defaults to "eval".
        upload (bool, optional): Upload results to Master. Defaults to True.

    Returns:
        dict: {
            "success": _OSCAP_EXIT_CODES_MAP[_retcode],
            "upload_dir": _upload_path,
            "error": None,
            "returncode": _retcode
            }
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
