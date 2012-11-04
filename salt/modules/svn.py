'''
Subversion SCM
'''

import re
import shlex
from salt import utils, exceptions

_INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$", re.M)


def _check_svn():
    utils.check_or_die('svn')


def _run_svn(cmd, cwd, user, opts, **kwargs):
    """
    Execute svn
    return the output of the command

    cmd
        The command to run.

    cwd
        The path to the Subversion repository

    user
        Run svn as a user other than what the minion runs as

    opts
        Any additional options to add to the command line
    """
    cmd = "svn --non-interactive %s " % cmd
    if opts:
        cmd += '"' + '" "'.join([optstr.replace('"', r'\"') for optstr in opts]) + '"'

    result = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    else:
        raise exceptions.CommandExecutionError(result['stderr'] + '\n\n' + cmd)


def info(cwd, targets=None, user=None, username=None, fmt="str"):
    """
    Display the Subversion information from the checkout.
    cwd
        The path to the Subversion repository

    user : None
        Run svn as a user other than what the minion runs as

    fmt : str
        How to fmt the output from info.
        (str, xml, list, dict)
    """
    opts = list()
    if fmt == "xml":
        opts.append("--xml")
    if targets:
        opts.append(shlex.split(targets))
    infos = _run_svn("info", cwd, user, opts)

    if fmt in ("str", "xml"):
        return infos

    info_list = []
    for infosplit in infos.split("\n\n"):
        info_list.append(_INI_RE.findall(infosplit))

    if fmt == "list":
        return info_list
    if fmt == "dict":
        return [dict(tmp) for tmp in info_list]


def checkout(cwd, remote, target=None, user=None, username=None, *opts):
    opts += (remote,)
    if target:
        opts += (target,)
    return _run_svn("checkout", cwd, user, opts)


def update(cwd, targets=None, user=None, *opts):
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn("update", cwd, user, opts)


def commit(cwd, targets=None, user=None, msg=None, username=None, *opts):
    if msg:
        opts += ("-m", msg)
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn("commit", cwd, user, opts)


def add(cwd, targets, user=None, *opts):
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn("add", cwd, user, opts)


def remove(cwd, targets, user=None, username=None, *opts):
    """
    targets:
        This can either be a list of local files, or, a remote URL.
    """
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn("remove", cwd, user, opts)


def status(cwd, targets=None, user=None, username=None, *opts):
    if targets:
        opts += tuple(shlex.split(targets))
    return _run_svn("status", cwd, user, opts)
