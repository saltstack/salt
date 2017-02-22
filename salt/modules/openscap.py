# -*- coding: utf-8 -*-
from __future__ import absolute_import
import tempfile
import shlex
import shutil
from subprocess import Popen, PIPE

from salt.client import Caller


ArgumentParser = object

try:
    import argparse  # pylint: disable=minimum-python-version
    ArgumentParser = argparse.ArgumentParser
    HAS_ARGPARSE = True
except ImportError:  # python 2.6
    HAS_ARGPARSE = False


_XCCDF_MAP = {
    'eval': {
        'parser_arguments': [
            (('--profile',), {'required': True}),
        ],
        'cmd_pattern': (
            "oscap xccdf eval "
            "--oval-results --results results.xml --report report.html "
            "--profile {0} {1}"
        )
    }
}


def __virtual__():
    return HAS_ARGPARSE, 'argparse module is required.'


class _ArgumentParser(ArgumentParser):

    def __init__(self, action=None, *args, **kwargs):
        super(_ArgumentParser, self).__init__(*args, prog='oscap', **kwargs)
        self.add_argument('action', choices=['eval'])
        add_arg = None
        for params, kwparams in _XCCDF_MAP['eval']['parser_arguments']:
            self.add_argument(*params, **kwparams)

    def error(self, message, *args, **kwargs):
        raise Exception(message)


_OSCAP_EXIT_CODES_MAP = {
    0: True,  # all rules pass
    1: False,  # there is an error during evaluation
    2: True  # there is at least one rule with either fail or unknown result
}


def xccdf(params):
    '''
    Run ``oscap xccdf`` commands on minions.
    It uses cp.push_dir to upload the generated files to the salt master
    in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)

    It needs ``file_recv`` set to ``True`` in the master configuration file.

    CLI Example:

    .. code-block:: bash

        salt '*'  openscap.xccdf "eval --profile Default /usr/share/openscap/scap-yast2sec-xccdf.xml"
    '''
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
    except Exception as err:
        success = False
        error = str(err)

    if success:
        cmd = _XCCDF_MAP[action]['cmd_pattern'].format(args.profile, policy)
        tempdir = tempfile.mkdtemp()
        proc = Popen(
            shlex.split(cmd), stdout=PIPE, stderr=PIPE, cwd=tempdir)
        (stdoutdata, error) = proc.communicate()
        success = _OSCAP_EXIT_CODES_MAP[proc.returncode]
        returncode = proc.returncode
        if success:
            caller = Caller()
            caller.cmd('cp.push_dir', tempdir)
            shutil.rmtree(tempdir, ignore_errors=True)
            upload_dir = tempdir

    return dict(
        success=success,
        upload_dir=upload_dir,
        error=error,
        returncode=returncode)
