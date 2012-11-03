'''
Subversion SCM
'''

import os
import re
from salt import utils

_kv_re = re.compile("^([^:]+):\s+(\S.*)$")

def _check_svn():
    utils.check_or_die('svn')

def _run_svn(cmd, cwd, user, opts):
    cmd = "svn --non-interactive %s " % cmd
    if opts:
        cmd += "'" + "' '".join(opts) + "'"

    return __salt__['cmd.run'](cmd, cwd=cwd, runas=user).rstrip()

def info(cwd, user, targets=None, format="str"):
    """
    format: str
        How to format the output from info.
        (str, xml, list, dict)
    """
    opts = []
    if format == "xml":
        opts.append("--xml")
    if targets:
        opts.append(targets)
    infos = _run_svn("info", cwd, user, opts)

    if format in ("str", "xml"):
        return infos

    for infosplit in infos.split("\n\n"):
        info_list = _kv_re(infosplit)

    if format == "list":
        return info_list
    if format == "dict":
        return [dict(tmp) for tmp in info_list]

def checkout(remote, cwd, user, target=None, opts=[]):
    opts.append(remote)
    if target:
        opts.append(target)
    return _run_svn("checkout", cwd, user, opts)

def update(cwd, user, files=None, opts=None):
    if files:
        opts.append(files)
    return _run_svn("update", cwd, user, opts)

def commit(cwd, user, files=None, msg=None, opts=[]):
    if msg:
        opts += ["-m", msg]
    if files:
        opts.append(files)
    return _run_svn("commit", cwd, user, opts)

def add(cwd, user, files, opts=[]):
    if files:
        opts.append(files)
    return _run_svn("add", cwd, user, opts)

def remove(cwd, user, files, opts=[]):
    if files:
        opts.append(files)
    return _run_svn("remove", cwd, user, opts)

def status(cwd, user, opts=[]):
    return _run_svn("status", cwd, user, opts)
