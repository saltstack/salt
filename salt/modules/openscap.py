"""
Module for OpenSCAP Management

"""

import argparse
import os.path
import shlex
import shutil
import subprocess
import tempfile

import salt.utils.versions

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


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(self, action=None, *args, **kwargs):
        super().__init__(*args, prog="oscap", **kwargs)
        self.add_argument("action", choices=["eval"])
        for params, kwparams in _XCCDF_MAP["eval"]["parser_arguments"]:
            self.add_argument(*params, **kwparams)

    def error(self, message, *args, **kwargs):  # pylint: disable=arguments-differ
        raise Exception(message)


_OSCAP_EXIT_CODES_MAP = {
    0: True,  # all rules pass
    1: False,  # there is an error during evaluation
    2: True,  # there is at least one rule with either fail or unknown result
}


def xccdf_eval(
    xccdffile,
    ovalfiles=None,
    profile=None,
    rule=None,
    oval_results=None,
    results=None,
    report=None,
    fetch_remote_resources=None,
    tailoring_file=None,
    tailoring_id=None,
    remediate=None,
):
    """
    Run ``oscap xccdf eval`` commands on minions.

    .. versionadded:: 3007.0

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
    if oval_results:
        cmd_opts.append("--oval-results")
    if results:
        cmd_opts.append("--results")
        cmd_opts.append(results)
    if report:
        cmd_opts.append("--report")
        cmd_opts.append(report)
    if profile:
        cmd_opts.append("--profile")
        cmd_opts.append(profile)
    if rule:
        cmd_opts.append("--rule")
        cmd_opts.append(rule)
    if tailoring_file:
        cmd_opts.append("--tailoring-file")
        cmd_opts.append(tailoring_file)
    if tailoring_id:
        cmd_opts.append("--tailoring-id")
        cmd_opts.append(tailoring_id)
    if fetch_remote_resources:
        cmd_opts.append("--fetch-remote-resources")
    if remediate:
        cmd_opts.append("--remediate")
    cmd_opts.append(xccdffile)
    cmd_opts.extend(ovalfiles)

    if not os.path.exists(xccdffile):
        success = False
        error = f"XCCDF File '{xccdffile}' does not exist"
    for ofile in ovalfiles:
        if success and not os.path.exists(ofile):
            success = False
            error = f"Oval File '{ofile}' does not exist"

    if success:
        tempdir = tempfile.mkdtemp()
        proc = subprocess.Popen(
            cmd_opts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tempdir
        )
        (stdoutdata, error) = proc.communicate()
        success = _OSCAP_EXIT_CODES_MAP.get(proc.returncode, False)
        if proc.returncode < 0:
            error += f"\nKilled by signal {proc.returncode}\n".encode("ascii")
        returncode = proc.returncode
        if success:
            if not __salt__["cp.push_dir"](tempdir):
                success = False
                error = "There was an error uploading openscap results files to salt master. Please check logs."
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
    salt.utils.versions.warn_until(
        3009,
        "The 'xccdf' function has been deprecated, please use 'xccdf_eval' instead",
    )
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
        proc = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tempdir,
        )
        (stdoutdata, error) = proc.communicate()
        success = _OSCAP_EXIT_CODES_MAP.get(proc.returncode, False)
        if proc.returncode < 0:
            error += f"\nKilled by signal {proc.returncode}\n".encode("ascii")
        returncode = proc.returncode
        success = _OSCAP_EXIT_CODES_MAP.get(returncode, False)
        if success:
            if not __salt__["cp.push_dir"](tempdir):
                success = False
                error = "There was an error uploading openscap results files to salt master. Please check logs."
            shutil.rmtree(tempdir, ignore_errors=True)
            upload_dir = tempdir

    return dict(
        success=success, upload_dir=upload_dir, error=error, returncode=returncode
    )
