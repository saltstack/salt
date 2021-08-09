"""
Module for OpenSCAP Management

"""


import os.path
import shlex
import shutil
import tempfile
from subprocess import PIPE, Popen

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


def __virtual__():
    return HAS_ARGPARSE, "argparse module is required."


class _ArgumentParser(ArgumentParser):
    def __init__(self, action=None, *args, **kwargs):
        super().__init__(*args, prog="oscap", **kwargs)
        self.add_argument("action", choices=["eval"])
        add_arg = None
        for params, kwparams in _XCCDF_MAP["eval"]["parser_arguments"]:
            self.add_argument(*params, **kwparams)

    def error(self, message, *args, **kwargs):
        raise Exception(message)


_OSCAP_EXIT_CODES_MAP = {
    0: True,  # all rules pass
    1: False,  # there is an error during evaluation
    2: True,  # there is at least one rule with either fail or unknown result
}


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
            error += "\nKilled by signal {}\n".format(proc.returncode).encode('ascii')
        returncode = proc.returncode
        if success:
            __salt__["cp.push_dir"](tempdir)
            upload_dir = tempdir
        shutil.rmtree(tempdir, ignore_errors=True)

    return dict(
        success=success, upload_dir=upload_dir, error=error, returncode=returncode
    )


def xccdf(params):
    """
    Run ``oscap xccdf`` commands on minions.
    It uses cp.push_dir to upload the generated files to the salt master
    in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)

    It needs ``file_recv`` set to ``True`` in the master configuration file.

    CLI Example:

    .. code-block:: bash

        salt '*'  openscap.xccdf "eval --profile Default /usr/share/openscap/scap-yast2sec-xccdf.xml"
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
            error += "\nKilled by signal {}\n".format(proc.returncode).encode('ascii')
        returncode = proc.returncode
        if success:
            __salt__["cp.push_dir"](tempdir)
            shutil.rmtree(tempdir, ignore_errors=True)
            upload_dir = tempdir

    return dict(
        success=success, upload_dir=upload_dir, error=error, returncode=returncode
    )
