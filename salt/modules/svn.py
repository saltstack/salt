'''
Subversion SCM
'''

import re
from salt import utils, exceptions

_INI_RE = re.compile(r"^([^:]+):\s+(\S.*)$")

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
    cmd = "svn --non-interactive %s" % cmd
    if opts:
        cmd += "'" + "' '".join(opts) + "'"

    result = __salt__['cmd.run_all'](cmd, cwd=cwd, runas=user)

    retcode = result['retcode']

    if retcode == 0:
        return result['stdout']
    else:
        raise exceptions.CommandExecutionError(result['stderr'])

def info(cwd, user=None, targets=None, fmt="str"):
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
        opts.append(targets)
    infos = _run_svn("info", cwd, user, opts)

    if fmt in ("str", "xml"):
        return infos

    for infosplit in infos.split("\n\n"):
        info_list = _INI_RE.findall(infosplit, re.M)

    if fmt == "list":
        return info_list
    if fmt == "dict":
        return [dict(tmp) for tmp in info_list]

def checkout(cwd, remote, user=None, target=None, *opts):
    opts += (remote,)
    if target:
        opts += (target,)
    return _run_svn("checkout", cwd, user, opts)

def update(cwd, user=None, targets=None, *opts):
    if targets:
        opts += (targets,)
    return _run_svn("update", cwd, user, opts)

def commit(cwd, user=None, targets=None, msg=None, *opts):
    if msg:
        opts += ("-m", msg)
    if targets:
        opts += (targets,)
    return _run_svn("commit", cwd, user, opts)

def add(cwd, targets, user=None, *opts):
    if targets:
        opts += (targets,)
    return _run_svn("add", cwd, user, opts)

def remove(cwd, targets, user=None, *opts):
    """
    targets:
        This can either be a list of local files, or, a remote URL.
    """
    if targets:
        opts += (targets,)
    return _run_svn("remove", cwd, user, opts)

def status(cwd, targets=None, user=None, *opts):
    if targets:
        opts += (targets,)
    return _run_svn("status", cwd, user, opts)
